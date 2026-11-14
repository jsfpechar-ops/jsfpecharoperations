package billingweb

// The write side of the bank statement and of "mark paid" (brief 1558):
// bank_import.record, import_statement and mark_paid_manually, billing_invoices.mark_paid,
// billing_jobs.settle and mail_notify.billing_paid. Every statement is its own
// commit, as in Python (no statement-wide transaction there either).

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// payer is one operator request that records payments: who acts (db.set_current_actor),
// the workspace (db.set_current_owner, the owner of audit rows that name none) and today.
type payer struct {
	pool         *pgxpool.Pool
	username     string
	userID       int64
	impersonator *int64
	workspace    int64
	today        time.Time
}

// ImportCounts is the dict of bank_import.import_statement.
type ImportCounts struct{ Matched, Unmatched, Partial, Overpaid, Seen, Ignored int }

// Params are the counts as flash parameters.
func (c ImportCounts) Params() map[string]any {
	return map[string]any{"matched": c.Matched, "unmatched": c.Unmatched, "partial": c.Partial,
		"overpaid": c.Overpaid, "seen": c.Seen, "ignored": c.Ignored}
}

// detail is " ".join(f"{k}={v}") in the dict's order.
func (c ImportCounts) detail() string {
	return fmt.Sprintf("matched=%d unmatched=%d partial=%d overpaid=%d seen=%d ignored=%d",
		c.Matched, c.Unmatched, c.Partial, c.Overpaid, c.Seen, c.Ignored)
}

// audit is db.audit: actor_user_id and impersonator_user_id from the request's
// actor, an owner that falls back to the workspace, "host" replaced by the username.
func (p payer) audit(ctx context.Context, actor, action, detail string, owner *int64) error {
	if owner == nil {
		w := p.workspace
		owner = &w
	}
	if actor == "host" {
		actor = p.username
	}
	_, err := p.pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`, ubyport.UTCNow(), actor, action, detail, owner, p.userID, p.impersonator)
	return err
}

type invoiceMatch struct {
	ID         int64
	Owner      *int64
	PaidOn     string
	TotalHaler int64
}

// invoiceFor is bank_import._invoice_for (lines 177-184): the open invoice with this variable symbol.
func (p payer) invoiceFor(ctx context.Context, vs string) (*invoiceMatch, error) {
	if vs == "" {
		return nil, nil
	}
	var m invoiceMatch
	var paid *string
	err := p.pool.QueryRow(ctx, `SELECT id, owner_user_id, paid_on, total_haler FROM platform_invoice
		WHERE vs = $1 AND kind IN ('invoice', 'supplementary') AND voided = 0 ORDER BY id LIMIT 1`, vs).
		Scan(&m.ID, &m.Owner, &paid, &m.TotalHaler)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	m.PaidOn = deref(paid)
	return &m, nil
}

// record is bank_import.record (lines 187-211): store one payment and match it.
// ok is false when the transaction was imported before.
func (p payer) record(ctx context.Context, row Payment) (status string, ok bool, err error) {
	inv, err := p.invoiceFor(ctx, row.VS)
	if err != nil {
		return "", false, err
	}
	status = "unmatched"
	if inv != nil && inv.PaidOn == "" {
		switch {
		case row.AmountHaler == inv.TotalHaler:
			status = "matched"
		case row.AmountHaler > inv.TotalHaler:
			status = "overpaid"
		default:
			status = "partial"
		}
	}
	var matched any
	if inv != nil && status != "unmatched" {
		matched = inv.ID
	}
	tag, err := p.pool.Exec(ctx, `INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, vs, counter_account, message,
		matched_invoice_id, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (bank_tx_id) DO NOTHING`,
		row.BankTxID, row.ReceivedOn, row.AmountHaler, nullable(row.VS), nullable(row.CounterAccount), nullable(row.Message), matched, status)
	if err != nil {
		return "", false, err
	}
	if tag.RowsAffected() == 0 {
		return "", false, nil
	}
	if status == "matched" || status == "overpaid" {
		if _, err := p.markPaid(ctx, inv.ID, row.ReceivedOn, "bank_auto"); err != nil {
			return "", false, err
		}
		if inv.Owner != nil {
			if _, err := p.settle(ctx, *inv.Owner); err != nil {
				return "", false, err
			}
		}
	}
	return status, true, nil
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// importStatement is bank_import.import_statement (lines 214-226): record every
// credit that could pay an invoice. A statement the parser refuses is its error.
func (p payer) importStatement(ctx context.Context, data []byte) (ImportCounts, error) {
	var c ImportCounts
	rows, err := Parse(data)
	if err != nil {
		return c, err
	}
	for _, row := range rows {
		if !InvoiceVS(row.VS) {
			c.Ignored++
			continue
		}
		status, ok, err := p.record(ctx, row)
		if err != nil {
			return c, err
		}
		switch {
		case !ok:
			c.Seen++
		case status == "matched":
			c.Matched++
		case status == "unmatched":
			c.Unmatched++
		case status == "partial":
			c.Partial++
		case status == "overpaid":
			c.Overpaid++
		}
	}
	return c, p.audit(ctx, p.username, "bank_statement_import", c.detail(), nil)
}

// markPaid is billing_invoices.mark_paid (lines 220-240): the payment once; false
// when the invoice was already paid, voided or a storno.
func (p payer) markPaid(ctx context.Context, id int64, paidOn, via string) (bool, error) {
	tag, err := p.pool.Exec(ctx, `UPDATE platform_invoice SET paid_on = $1, paid_via = $2
		WHERE id = $3 AND paid_on IS NULL AND voided = 0 AND kind != 'storno'`, paidOn, via, id)
	if err != nil {
		return false, err
	}
	if tag.RowsAffected() == 0 {
		return false, nil
	}
	var number string
	var owner *int64
	var total int64
	if err := p.pool.QueryRow(ctx, `SELECT number, owner_user_id, total_haler FROM platform_invoice WHERE id = $1`, id).
		Scan(&number, &owner, &total); err != nil {
		return false, err
	}
	if err := p.audit(ctx, p.username, "platform_invoice_paid", number+" "+via, owner); err != nil {
		return false, err
	}
	if owner != nil {
		if err := p.paidMail(ctx, id, *owner, number, total, paidOn); err != nil {
			return false, err
		}
	}
	return true, nil
}

// markPaidManually is bank_import.mark_paid_manually (lines 229-236): paid, then the account settles.
func (p payer) markPaidManually(ctx context.Context, id int64, paidOn string) (bool, error) {
	ok, err := p.markPaid(ctx, id, paidOn, "bank_manual")
	if err != nil || !ok {
		return false, err
	}
	var owner *int64
	if err := p.pool.QueryRow(ctx, `SELECT owner_user_id FROM platform_invoice WHERE id = $1`, id).Scan(&owner); err != nil {
		return false, err
	}
	if owner != nil {
		if _, err := p.settle(ctx, *owner); err != nil {
			return false, err
		}
	}
	return true, nil
}

// settle is billing_jobs.settle (lines 141-163): after a payment, back to
// active once nothing is overdue. true when the status changed.
func (p payer) settle(ctx context.Context, owner int64) (bool, error) {
	acc, err := billing.Account(ctx, p.pool, owner)
	if err != nil {
		return false, err
	}
	if acc == nil || (acc.Status != "overdue" && acc.Status != "paused") || acc.Plan == "" {
		return false, nil
	}
	day := isoDay(p.today)
	var one int
	err = p.pool.QueryRow(ctx, `SELECT 1 FROM platform_invoice WHERE owner_user_id = $1 AND kind IN ('invoice', 'supplementary')
		AND voided = 0 AND paid_on IS NULL AND due_date < $2 LIMIT 1`, owner, day).Scan(&one)
	if err == nil {
		return false, nil // still something overdue
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	if acc.Status == "paused" {
		// Only an account the dunning paused comes back: its current period was invoiced and is now paid.
		err = p.pool.QueryRow(ctx, `SELECT 1 FROM platform_invoice WHERE owner_user_id = $1 AND kind = 'invoice' AND voided = 0
			AND paid_on IS NOT NULL AND period_to >= $2 LIMIT 1`, owner, day).Scan(&one)
		if errors.Is(err, pgx.ErrNoRows) {
			return false, nil
		}
		if err != nil {
			return false, err
		}
	}
	return billing.SetStatus(billing.WithAuditActor(ctx, p.userID, p.username, p.impersonator), p.pool, owner, "active", "system")
}

// paidMail is mail_notify.billing_paid (lines 3126-3156): one copy to the invoice
// buyer address and one to the account address (one when they are the same),
// key billing-paid-<invoice>-<buyer|account>, a copy to the operator. Nothing
// is queued while mail is off.
func (p payer) paidMail(ctx context.Context, invoiceID, owner int64, number string, totalHaler int64, paidOn string) error {
	if !billingjob.MailEnabled() {
		return nil
	}
	inv := &billingjob.Invoicer{Pool: p.pool}
	buyer, err := inv.Recipient(ctx, owner)
	if err != nil {
		return err
	}
	var email *string
	if err := p.pool.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, owner).Scan(&email); err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	account := strings.TrimSpace(deref(email))
	content := mail.BuildBillingPaid(billingjob.AppBaseURL(), billingjob.PublicBaseURL(), billingjob.OperatorEmail(),
		number, floorDiv(totalHaler, 100), fmtDate(paidOn))
	payload := fmt.Sprintf(`{"text": %s, "html": %s, "lang": "cs", "reply_to": %s}`,
		ubyport.PyString(content.Text), ubyport.PyString(content.HTML), ubyport.PyString(billingjob.OperatorEmail()))
	for _, r := range []struct{ tag, to string }{{"buyer", buyer}, {"account", account}} {
		if r.to == "" || (r.tag == "account" && r.to == buyer) {
			continue
		}
		to := ubyport.NormaliseEmail(r.to)
		if to == "" {
			continue
		}
		if _, err := ubyport.EnqueueMail(ctx, p.pool, ubyport.OutboxMail{
			Kind: "billing_paid", Key: "billing-paid-" + strconv.FormatInt(invoiceID, 10) + "-" + r.tag, OwnerUserID: &owner,
			To: to, CC: ubyport.NormaliseEmail(billingjob.OperatorEmail()), Subject: content.Subject, Payload: payload,
		}); err != nil {
			// Python logs an insert failure and carries on.
			continue
		}
	}
	return nil
}
