package billingjob

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Sentinel errors; Error() is the string Python raises in ValueError.
var (
	ErrBuyerMissing     = errors.New("buyer_missing")
	ErrNoPlan           = errors.New("no_plan")
	ErrBelowMinimum     = errors.New("below_minimum")
	ErrNotAnInvoice     = errors.New("not_an_invoice")
	ErrAlreadyVoided    = errors.New("already_voided")
	ErrPaid             = errors.New("paid")
	ErrWorkspaceDeleted = errors.New("workspace_deleted")
)

const (
	// DueDays is billing_invoices.DUE_DAYS.
	DueDays = 14
	// SupplementaryMinCZK is billing.SUPPLEMENTARY_MIN_CZK.
	SupplementaryMinCZK = 50
)

// Invoicer issues UbyHost's invoices to hosts.
type Invoicer struct {
	Pool *pgxpool.Pool
}

// item is one (description, whole Kč) line.
type item struct {
	Description string
	CZK         int64
}

type document struct {
	Kind        string // invoice, supplementary or storno
	PeriodFrom  string
	PeriodTo    string
	Items       []item
	IssueDate   time.Time
	CorrectsID  *int64
	Reason      string
	ClearCarry  bool
	BilledCarry int64 // carry_czk the items billed; subtracted, not zeroed
	OwnerUserID int64
}

// IssueForPeriod is issue_for_period: the period's invoice, issued once;
// asking again returns the same id.
func (v *Invoicer) IssueForPeriod(ctx context.Context, owner int64, periodFrom, periodTo string, today time.Time) (int64, error) {
	var existing int64
	err := v.Pool.QueryRow(ctx,
		`SELECT id FROM platform_invoice WHERE owner_user_id = $1 AND period_from = $2
		 AND period_to = $3 AND kind = 'invoice' AND voided = 0`,
		owner, periodFrom, periodTo).Scan(&existing)
	if err == nil {
		return existing, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return 0, err
	}
	acc, err := v.account(ctx, owner)
	if err != nil {
		return 0, err
	}
	if acc == nil || acc.Plan == nil || acc.Interval == nil {
		return 0, ErrNoPlan
	}
	items, err := periodItems(*acc)
	if err != nil {
		return 0, err
	}
	id, err := v.issue(ctx, document{
		Kind: "invoice", PeriodFrom: periodFrom, PeriodTo: periodTo, Items: items,
		IssueDate: today, ClearCarry: true, BilledCarry: acc.CarryCZK, OwnerUserID: owner,
	})
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		// A concurrent run issued the same period first: return its id.
		if qerr := v.Pool.QueryRow(ctx,
			`SELECT id FROM platform_invoice WHERE owner_user_id = $1 AND period_from = $2
			 AND period_to = $3 AND kind = 'invoice' AND voided = 0`,
			owner, periodFrom, periodTo).Scan(&existing); qerr == nil {
			return existing, nil
		}
	}
	return id, err
}

// IssueSupplementary is issue_supplementary: the difference for a rise during an
// annual period.
func (v *Invoicer) IssueSupplementary(ctx context.Context, owner int64, amountCZK int64, description, periodFrom, periodTo string, today time.Time) (int64, error) {
	if amountCZK < SupplementaryMinCZK {
		return 0, ErrBelowMinimum
	}
	return v.issue(ctx, document{
		Kind: "supplementary", PeriodFrom: periodFrom, PeriodTo: periodTo,
		Items: []item{{description, amountCZK}}, IssueDate: today, OwnerUserID: owner,
	})
}

// Storno is storno: cancel an unpaid invoice with a storno; its period can then
// be invoiced again. A paid invoice is not cancelled here.
func (v *Invoicer) Storno(ctx context.Context, invoiceID int64, reason string, today time.Time) (int64, error) {
	var (
		kind, periodFrom, periodTo, snapshot string
		voided                               int64
		paidOn                               *string
		owner                                *int64
	)
	err := v.Pool.QueryRow(ctx,
		`SELECT kind, voided, paid_on, owner_user_id, period_from, period_to, snapshot_json
		 FROM platform_invoice WHERE id = $1`, invoiceID,
	).Scan(&kind, &voided, &paidOn, &owner, &periodFrom, &periodTo, &snapshot)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && kind == "storno") {
		return 0, ErrNotAnInvoice
	}
	if err != nil {
		return 0, err
	}
	if voided != 0 {
		return 0, ErrAlreadyVoided
	}
	if paidOn != nil && *paidOn != "" { // Python: truthy paid_on
		return 0, ErrPaid
	}
	if owner == nil {
		return 0, ErrWorkspaceDeleted
	}
	var snap struct {
		Items []struct {
			Description string `json:"description"`
			GrossHaler  int64  `json:"gross_haler"`
		} `json:"items"`
	}
	if err := json.Unmarshal([]byte(snapshot), &snap); err != nil {
		return 0, fmt.Errorf("snapshot of invoice %d: %w", invoiceID, err)
	}
	items := make([]item, 0, len(snap.Items))
	for _, it := range snap.Items {
		items = append(items, item{it.Description, -floorDiv(it.GrossHaler, 100)})
	}
	id := invoiceID
	return v.issue(ctx, document{
		Kind: "storno", PeriodFrom: periodFrom, PeriodTo: periodTo, Items: items,
		IssueDate: today, CorrectsID: &id, Reason: reason, OwnerUserID: *owner,
	})
}

// floorDiv is Python's // for a positive divisor.
func floorDiv(a, b int64) int64 {
	q := a / b
	if a%b != 0 && (a < 0) != (b < 0) {
		q--
	}
	return q
}

// issue is issue(): number, render and store one document; its id. One
// transaction; the audit row follows the commit.
func (v *Invoicer) issue(ctx context.Context, d document) (int64, error) {
	acc, err := v.account(ctx, d.OwnerUserID)
	if err != nil {
		return 0, err
	}
	if acc == nil || strings.TrimSpace(acc.BuyerName) == "" {
		return 0, ErrBuyerMissing
	}
	var total int64
	rows := make([]pdf.Item, 0, len(d.Items))
	for _, it := range d.Items {
		total += it.CZK * 100
		rows = append(rows, pdf.Item{Description: it.Description, Quantity: 1, GrossHaler: it.CZK * 100})
	}
	due := d.IssueDate
	if d.Kind != "storno" {
		due = d.IssueDate.AddDate(0, 0, DueDays)
	}
	year := d.IssueDate.Year()

	tx, err := v.Pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after commit

	var seq int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO platform_invoice_sequence (year, last_no) VALUES ($1, 1)
		 ON CONFLICT(year) DO UPDATE SET last_no = platform_invoice_sequence.last_no + 1
		 RETURNING last_no`, year).Scan(&seq); err != nil {
		return 0, err
	}
	number := fmt.Sprintf("UBY-%d-%04d", year, seq)
	vs := fmt.Sprintf("%d%04d", year, seq)
	correctsNumber := ""
	if d.CorrectsID != nil {
		if err := tx.QueryRow(ctx, `SELECT number FROM platform_invoice WHERE id = $1`, *d.CorrectsID).Scan(&correctsNumber); err != nil {
			return 0, err
		}
	}
	// The renderer knows invoice / storno / corrective; a supplementary invoice is
	// an ordinary invoice on paper.
	printKind := "invoice"
	if d.Kind == "storno" {
		printKind = "storno"
	}
	inv := invoiceDoc{
		seller: sellerFromEnv(), buyer: *acc, Kind: printKind, Number: number, VS: vs,
		IssueDate: d.IssueDate.Format("2006-01-02"), DueDate: due.Format("2006-01-02"),
		TotalHaler: total, Note: "Období: " + fmtDateRange(d.PeriodFrom, d.PeriodTo),
		CorrectsNumber: correctsNumber, CorrectionReason: d.Reason,
	}
	pdfBytes, err := pdf.Render(inv.pdfInvoice(), rows, "cs", false, false)
	if err != nil {
		return 0, fmt.Errorf("render invoice %s: %w", number, err)
	}
	sum := sha256.Sum256(pdfBytes)
	now := ubyport.UTCNow()
	var newID int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO platform_invoice (owner_user_id, kind, corrects_id, seq_year, seq_no,
		   number, vs, issue_date, due_date, period_from, period_to, total_haler,
		   snapshot_json, pdf_blob, pdf_sha256, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
		 RETURNING id`,
		d.OwnerUserID, d.Kind, d.CorrectsID, year, seq, number, vs,
		inv.IssueDate, inv.DueDate, d.PeriodFrom, d.PeriodTo, total,
		snapshotJSON(inv, d.Items), pdfBytes, hex.EncodeToString(sum[:]), now,
	).Scan(&newID); err != nil {
		return 0, err
	}
	if d.Kind == "storno" {
		// Guard inside the transaction: a concurrent storno or payment wins and
		// this one rolls back (its sequence number with it).
		tag, err := tx.Exec(ctx,
			`UPDATE platform_invoice SET voided = 1 WHERE id = $1 AND voided = 0 AND (paid_on IS NULL OR paid_on = '')`,
			*d.CorrectsID)
		if err != nil {
			return 0, err
		}
		if tag.RowsAffected() == 0 {
			return 0, ErrAlreadyVoided
		}
	}
	if d.ClearCarry {
		// Subtract what was billed, so carry added meanwhile is kept.
		if _, err := tx.Exec(ctx,
			`UPDATE billing_account SET carry_czk = carry_czk - $1, updated_at = $2 WHERE owner_user_id = $3`,
			d.BilledCarry, now, d.OwnerUserID); err != nil {
			return 0, err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return 0, err
	}
	if _, err := v.Pool.Exec(ctx,
		`INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		 VALUES ($1, 'system', 'platform_invoice_issued', $2, $3, NULL, NULL)`,
		ubyport.UTCNow(), number+" "+d.Kind, d.OwnerUserID); err != nil {
		// The document is committed: report it as issued so no caller retries.
		slog.Error("platform_invoice_issued audit failed", "number", number, "err", err)
	}
	return newID, nil
}

// sellerFromEnv is _seller(): operator.details() and the billing settings, read
// from the environment as config.py reads them.
func sellerFromEnv() seller {
	get := func(k string) string { return strings.TrimSpace(os.Getenv(k)) }
	vat := get("UBYHOST_BILLING_VAT_STATUS")
	if vat == "" {
		vat = "non_payer"
	}
	return seller{
		Name: get("UBYHOST_OPERATOR_NAME"), Seat: get("UBYHOST_OPERATOR_ADDRESS"),
		ICO: get("UBYHOST_OPERATOR_ICO"), DIC: get("UBYHOST_OPERATOR_DIC"),
		Email: OperatorEmail(), IBAN: get("UBYHOST_BILLING_IBAN"),
		BankAccount: get("UBYHOST_BILLING_BANK_ACCOUNT"), VATStatus: vat,
	}
}

// OperatorEmail is config.OPERATOR_EMAIL: the variable, else support@ubyhost.com.
func OperatorEmail() string {
	if e := strings.TrimSpace(os.Getenv("UBYHOST_OPERATOR_EMAIL")); e != "" {
		return e
	}
	return "support@ubyhost.com"
}
