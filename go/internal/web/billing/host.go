package billingweb

// The host's plan page data (routes/billing.py _page, billing_order.form_values
// and billing_invoices.for_owner), brief 1556.

import (
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/url"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// querier is billing.DB: *pgxpool.Pool and pgx.Tx fit.
type querier = billing.DB

// fmtDate is validation.fmt_date: DD.MM.YYYY, or the input unchanged.
func fmtDate(value string) string {
	if t, ok := validation.ParseISODate(value); ok {
		return t.Format("02.01.2006")
	}
	return value
}

// kcWhole is routes/billing._kc: whole crowns with a space between thousands.
func kcWhole(czk int) string { return Kc(int64(czk) * 100) }

func inList(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

// signupSelection is signup_selection.for_owner: the bounded pricing choices
// the host picked before signing up (plan, interval, ttlock, apartments).
func signupSelection(ctx context.Context, q querier, owner int64) (map[string]string, error) {
	var raw *string
	err := q.QueryRow(ctx, `SELECT signup_selection_json FROM user_account WHERE id = $1`, owner).Scan(&raw)
	if errors.Is(err, pgx.ErrNoRows) {
		return map[string]string{}, nil
	}
	if err != nil {
		return nil, err
	}
	text := "{}"
	if raw != nil && *raw != "" {
		text = *raw
	}
	var stored map[string]any
	if json.Unmarshal([]byte(text), &stored) != nil || stored == nil {
		return map[string]string{}, nil
	}
	// Python's clean() keeps a choice only when the value is a str in the
	// allowed set; a number or list never is, so only strings go on.
	values := url.Values{}
	for k, v := range stored {
		if s, ok := v.(string); ok {
			values.Set(k, s)
		}
	}
	return signup.CleanSelection(values), nil
}

// FormValues is billing_order.form_values (lines 25-59): what the order form
// starts with, the saved order, else the host's first legal entity. query
// carries plan and interval from the /cenik buttons.
func FormValues(ctx context.Context, q querier, owner int64, query map[string]string) (billing.OrderValues, error) {
	acc, err := billing.Account(ctx, q, owner)
	if err != nil {
		return billing.OrderValues{}, err
	}
	if acc == nil {
		acc = &billing.BillingAccount{}
	}
	merged := map[string]string{}
	if acc.Plan == "" {
		// Preferences prefill an unordered account only.
		if merged, err = signupSelection(ctx, q, owner); err != nil {
			return billing.OrderValues{}, err
		}
	}
	for k, v := range query {
		if v != "" {
			merged[k] = v
		}
	}
	plan := acc.Plan
	if inList(billing.Plans, merged["plan"]) {
		plan = merged["plan"]
	} else if plan == "" {
		plan = "standard"
	}
	interval := acc.BillingInterval
	if inList(billing.Intervals, merged["interval"]) {
		interval = merged["interval"]
	} else if interval == "" {
		interval = "year"
	}
	ttlock := merged["ttlock"] == "1"
	if acc.Plan != "" {
		ttlock = acc.AddonTTLock
	}
	v := billing.OrderValues{
		Plan: plan, BillingInterval: interval, AddonTTLock: ttlock, AddonWhitelabel: acc.AddonWhitelabel,
		BuyerName: acc.BuyerName, BuyerStreet: acc.BuyerStreet, BuyerCity: acc.BuyerCity, BuyerZip: acc.BuyerZip,
		BuyerICO: acc.BuyerICO, BuyerDIC: acc.BuyerDIC, BuyerEmail: acc.BuyerEmail,
	}
	if v.BuyerName == "" {
		var name, ico, dic, email *string
		err := q.QueryRow(ctx,
			`SELECT name, ico, dic, contact_email FROM legal_entity WHERE owner_user_id = $1 ORDER BY id LIMIT 1`, owner,
		).Scan(&name, &ico, &dic, &email)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return billing.OrderValues{}, err
		}
		if err == nil {
			v.BuyerName, v.BuyerICO, v.BuyerDIC, v.BuyerEmail = deref(name), deref(ico), deref(dic), deref(email)
		}
	}
	if v.BuyerEmail == "" {
		var email *string
		err := q.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, owner).Scan(&email)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return billing.OrderValues{}, err
		}
		v.BuyerEmail = deref(email)
	}
	return v, nil
}

// OwnerInvoice is one row of billing_invoices.for_owner.
type OwnerInvoice struct {
	ID         int64
	Kind       string
	Number     string
	IssueDate  string
	TotalHaler int64
	Voided     int64
	PaidOn     string
}

// ForOwner is billing_invoices.for_owner (lines 248-257): the host's
// documents, newest first, without the PDF bytes.
func ForOwner(ctx context.Context, q querier, owner int64) ([]OwnerInvoice, error) {
	rows, err := q.Query(ctx,
		`SELECT id, kind, number, issue_date, total_haler, voided, paid_on FROM platform_invoice
		 WHERE owner_user_id = $1 ORDER BY id DESC`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []OwnerInvoice{}
	for rows.Next() {
		var i OwnerInvoice
		var paid *string
		if err := rows.Scan(&i.ID, &i.Kind, &i.Number, &i.IssueDate, &i.TotalHaler, &i.Voided, &paid); err != nil {
			return nil, err
		}
		i.PaidOn = deref(paid)
		out = append(out, i)
	}
	return out, rows.Err()
}

// Upgrade is the `upgrade` dict of _page (lines 49-60): the other plan's price
// per period, the saving of a year over twelve months, and the lock add-on's
// monthly price.
type Upgrade struct {
	Price       string
	SavePct     int
	TTLockPrice int
}

// ttlockMonthly is billing.TTLOCK["month"]; the test pins it to the engine's table.
const ttlockMonthly = 49

// UpgradeFor is the upgrade block of _page for an ordered account.
func UpgradeFor(ctx context.Context, q querier, owner int64, acc *billing.BillingAccount) (*Upgrade, error) {
	if acc == nil || !inList(billing.Plans, acc.Plan) || !inList(billing.Intervals, acc.BillingInterval) {
		return nil, nil
	}
	n, err := billing.Apartments(ctx, q, owner)
	if err != nil {
		return nil, err
	}
	lock, brand := acc.AddonTTLock, acc.AddonWhitelabel
	other := "max"
	if acc.Plan == "max" {
		other = "standard"
	}
	month, err := billing.Quote(n, acc.Plan, "month", lock, brand, 0)
	if err != nil {
		return nil, err
	}
	year, err := billing.Quote(n, acc.Plan, "year", lock, brand, 0)
	if err != nil {
		return nil, err
	}
	next, err := billing.Quote(n, other, acc.BillingInterval, lock && other != "max", brand, 0)
	if err != nil {
		return nil, err
	}
	u := &Upgrade{Price: kcWhole(next.Total), TTLockPrice: ttlockMonthly}
	u.SavePct = savePct(month.Total, year.Total)
	return u, nil
}

// savePct is round(100 * (12 * month - year) / (12 * month)) if month else 0
// (routes/billing.py line 56): true division, then Python's half-to-even round.
func savePct(month, year int) int {
	if month == 0 {
		return 0
	}
	return int(math.RoundToEven(float64(100*(12*month-year)) / float64(12*month)))
}
