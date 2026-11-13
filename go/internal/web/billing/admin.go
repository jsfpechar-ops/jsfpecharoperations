// Package billingweb is the read side of the operator billing page
// /admin/fakturace, ported from App/app/billing_admin.py, bank_import.py and
// billing_analytics.py. It registers no route and renders nothing: AdminPageData
// returns a typed struct, the others are the queries and pure helpers behind it.
// Python is the oracle; testdata/billing_admin_golden.json is written by
// App/scripts/billing_admin_golden.py and the tests compare against it.
package billingweb

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// DB is what the queries need; *pgxpool.Pool and pgx.Tx fit.
type DB interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// queryAll runs sql and scans every row. The result is never nil, so it
// marshals as [] like the Python list.
func queryAll[T any](ctx context.Context, q DB, scan func(pgx.Rows) (T, error), sql string, args ...any) ([]T, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []T{}
	for rows.Next() {
		v, err := scan(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

var monthRE = regexp.MustCompile(`^\d{4}-(0[1-9]|1[0-2])$`)

// CSVHeader is billing_admin.CSV_HEADER (lines 21-24).
var CSVHeader = []string{
	"Číslo", "Druh", "Opravuje", "Vystaveno", "Splatnost", "Období od", "Období do",
	"Odběratel", "IČO", "DIČ", "Částka Kč", "VS", "Zaplaceno", "Způsob úhrady", "Stornováno",
}

// KindCS is billing_admin.KIND_CS (line 25).
var KindCS = map[string]string{"invoice": "faktura", "supplementary": "doplatek", "storno": "storno"}

// ViaCS is billing_admin.VIA_CS (line 26).
var ViaCS = map[string]string{"bank_auto": "výpis", "bank_manual": "ručně"}

// MonthOrCurrent is billing_admin.month_or_current (lines 29-31): the trimmed
// value when it is YYYY-MM, else the month of today (zero means now).
func MonthOrCurrent(value string, today time.Time) string {
	text := pyStrip(value)
	if monthRE.MatchString(text) {
		return text
	}
	return dayOf(today).Format("2006-01")
}

// Buyer is the buyer as printed on the invoice (billing_admin._buyer).
type Buyer struct {
	Name string `json:"name"`
	ICO  string `json:"ico"`
	DIC  string `json:"dic"`
}

// buyerOf is billing_admin._buyer (lines 34-36). An empty snapshot reads as {}.
func buyerOf(snapshot string) (Buyer, error) {
	if snapshot == "" {
		snapshot = "{}"
	}
	var doc struct {
		Invoice map[string]any `json:"invoice"`
	}
	if err := json.Unmarshal([]byte(snapshot), &doc); err != nil {
		return Buyer{}, fmt.Errorf("invoice snapshot: %w", err)
	}
	get := func(key string) string {
		s, _ := doc.Invoice[key].(string)
		return s
	}
	return Buyer{Name: get("buyer_name"), ICO: get("buyer_ico"), DIC: get("buyer_dic")}, nil
}

// Invoice is one row of billing_admin.invoices; JSON keys are the Python dict keys.
type Invoice struct {
	ID             int64   `json:"id"`
	OwnerUserID    *int64  `json:"owner_user_id"`
	Kind           string  `json:"kind"`
	CorrectsID     *int64  `json:"corrects_id"`
	Number         string  `json:"number"`
	VS             string  `json:"vs"`
	IssueDate      string  `json:"issue_date"`
	DueDate        string  `json:"due_date"`
	PeriodFrom     string  `json:"period_from"`
	PeriodTo       string  `json:"period_to"`
	TotalHaler     int64   `json:"total_haler"`
	Voided         int64   `json:"voided"`
	PaidOn         *string `json:"paid_on"`
	PaidVia        *string `json:"paid_via"`
	CorrectsNumber *string `json:"corrects_number"`
	Buyer          Buyer   `json:"buyer"`
}

const invoicesSQL = `SELECT i.id, i.owner_user_id, i.kind, i.corrects_id, i.number, i.vs, i.issue_date, i.due_date,
	i.period_from, i.period_to, i.total_haler, i.voided, i.paid_on, i.paid_via, i.snapshot_json,
	c.number AS corrects_number FROM platform_invoice i
	LEFT JOIN platform_invoice c ON c.id = i.corrects_id
	WHERE i.issue_date >= $1 AND i.issue_date < $2 ORDER BY i.issue_date, i.id`

// nextMonth is billing_admin._next_month (lines 59-61): the first day after the month.
func nextMonth(month string) (string, error) {
	if len(month) < 7 {
		return "", fmt.Errorf("bad month %q", month)
	}
	year, err1 := strconv.Atoi(month[:4])
	mon, err2 := strconv.Atoi(month[5:7])
	if err1 != nil || err2 != nil {
		return "", fmt.Errorf("bad month %q", month)
	}
	if mon == 12 {
		return fmt.Sprintf("%d-01-01", year+1), nil
	}
	return fmt.Sprintf("%d-%02d-01", year, mon+1), nil
}

// Invoices is billing_admin.invoices (lines 39-56): the month's documents by
// issue date, oldest first, with the buyer as printed. month is YYYY-MM.
func Invoices(ctx context.Context, q DB, month string) ([]Invoice, error) {
	next, err := nextMonth(month)
	if err != nil {
		return nil, err
	}
	var snaps []string
	rows, err := queryAll(ctx, q, func(r pgx.Rows) (Invoice, error) {
		var i Invoice
		var snap string
		err := r.Scan(&i.ID, &i.OwnerUserID, &i.Kind, &i.CorrectsID, &i.Number, &i.VS, &i.IssueDate,
			&i.DueDate, &i.PeriodFrom, &i.PeriodTo, &i.TotalHaler, &i.Voided, &i.PaidOn, &i.PaidVia,
			&snap, &i.CorrectsNumber)
		snaps = append(snaps, snap)
		return i, err
	}, invoicesSQL, month+"-01", next)
	if err != nil {
		return nil, err
	}
	for n := range rows {
		if rows[n].Buyer, err = buyerOf(snaps[n]); err != nil {
			return nil, err
		}
	}
	return rows, nil
}

// UnpaidInvoice is one row of billing_admin.unpaid.
type UnpaidInvoice struct {
	ID          int64  `json:"id"`
	OwnerUserID *int64 `json:"owner_user_id"`
	Kind        string `json:"kind"`
	Number      string `json:"number"`
	VS          string `json:"vs"`
	IssueDate   string `json:"issue_date"`
	DueDate     string `json:"due_date"`
	TotalHaler  int64  `json:"total_haler"`
	Buyer       Buyer  `json:"buyer"`
	Overdue     bool   `json:"overdue"`
}

// Unpaid is billing_admin.unpaid (lines 64-77): every unpaid invoice of any
// month, due date order (the id breaks ties). Overdue means due before today.
func Unpaid(ctx context.Context, q DB, today time.Time) ([]UnpaidInvoice, error) {
	day := isoDay(dayOf(today))
	var snaps []string
	rows, err := queryAll(ctx, q, func(r pgx.Rows) (UnpaidInvoice, error) {
		var u UnpaidInvoice
		var snap string
		err := r.Scan(&u.ID, &u.OwnerUserID, &u.Kind, &u.Number, &u.VS, &u.IssueDate, &u.DueDate,
			&u.TotalHaler, &snap)
		snaps = append(snaps, snap)
		return u, err
	}, `SELECT id, owner_user_id, kind, number, vs, issue_date, due_date, total_haler, snapshot_json
		FROM platform_invoice WHERE kind IN ('invoice', 'supplementary') AND voided = 0 AND paid_on IS NULL
		ORDER BY due_date, id`)
	if err != nil {
		return nil, err
	}
	for n := range rows {
		if rows[n].Buyer, err = buyerOf(snaps[n]); err != nil {
			return nil, err
		}
		rows[n].Overdue = cut(rows[n].DueDate, 10) < day
	}
	return rows, nil
}

// AccountsByStatus is billing_admin.accounts_by_status (lines 80-82).
func AccountsByStatus(ctx context.Context, q DB) (map[string]int64, error) {
	type pair struct {
		status string
		n      int64
	}
	pairs, err := queryAll(ctx, q, func(r pgx.Rows) (pair, error) {
		var p pair
		return p, r.Scan(&p.status, &p.n)
	}, "SELECT status, COUNT(*) AS n FROM billing_account GROUP BY status")
	if err != nil {
		return nil, err
	}
	out := map[string]int64{}
	for _, p := range pairs {
		out[p.status] = p.n
	}
	return out, nil
}

// KcCSV is billing_admin._kc (lines 85-86) and billing_analytics._cz (lines
// 189-190): haler as "1234,50" for the CSV files.
func KcCSV(haler int64) string {
	return strings.Replace(strconv.FormatFloat(float64(haler)/100, 'f', 2, 64), ".", ",", 1)
}

// Kc is the page's formatter, routes/admin_billing._kc (lines 25-26): whole
// crowns (floored) with a space between thousands, 1234567 haler -> "12 345".
func Kc(haler int64) string {
	n := floorDiv(haler, 100)
	neg := n < 0
	var digits string
	if neg {
		digits = strconv.FormatUint(uint64(-n), 10)
	} else {
		digits = strconv.FormatUint(uint64(n), 10)
	}
	var b strings.Builder
	if neg {
		b.WriteString("-")
	}
	for i, c := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			b.WriteString(" ")
		}
		b.WriteRune(c)
	}
	return b.String()
}

// ExportCSV is billing_admin.export_csv (lines 89-102): the month's documents
// with semicolons, \r\n and a BOM, so Czech Excel opens it straight away.
func ExportCSV(ctx context.Context, q DB, month string) ([]byte, error) {
	invs, err := Invoices(ctx, q, month)
	if err != nil {
		return nil, err
	}
	var rows [][]string
	for _, r := range invs {
		kind, ok := KindCS[r.Kind]
		if !ok {
			return nil, fmt.Errorf("unknown invoice kind %q", r.Kind)
		}
		voided := ""
		if r.Voided != 0 {
			voided = "ano"
		}
		rows = append(rows, []string{
			r.Number, kind, deref(r.CorrectsNumber), cut(r.IssueDate, 10), cut(r.DueDate, 10),
			cut(r.PeriodFrom, 10), cut(r.PeriodTo, 10), r.Buyer.Name, r.Buyer.ICO, r.Buyer.DIC,
			KcCSV(r.TotalHaler), r.VS, cut(deref(r.PaidOn), 10), ViaCS[deref(r.PaidVia)], voided,
		})
	}
	return csvBytes(CSVHeader, rows), nil
}
