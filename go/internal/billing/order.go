package billing

import (
	"context"
	"fmt"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Ordering and changing a plan: a port of App/app/billing_order.py (without
// form_values and quote) and of billing_trial.period_end.

// BuyerFields is billing_order.BUYER_FIELDS, in order.
var BuyerFields = []string{
	"buyer_name", "buyer_street", "buyer_city", "buyer_zip", "buyer_ico", "buyer_dic", "buyer_email",
}

// Orderable is billing_order.ORDERABLE: the statuses in which the host orders a
// plan; after that, changes go through ApplyChange.
var Orderable = []string{"trial_pending", "trialing", "paused"}

// HostActor is the actor Python writes for the host's own order rows.
const HostActor = "host"

// OrderValues is the dict billing_order.read_form returns (json keys as Python).
type OrderValues struct {
	Plan            string `json:"plan"`
	BillingInterval string `json:"billing_interval"`
	AddonTTLock     bool   `json:"addon_ttlock"`
	AddonWhitelabel bool   `json:"addon_whitelabel"`
	BuyerName       string `json:"buyer_name"`
	BuyerStreet     string `json:"buyer_street"`
	BuyerCity       string `json:"buyer_city"`
	BuyerZip        string `json:"buyer_zip"`
	BuyerICO        string `json:"buyer_ico"`
	BuyerDIC        string `json:"buyer_dic"`
	BuyerEmail      string `json:"buyer_email"`
}

// buyer returns the value of one BuyerFields entry.
func (v OrderValues) buyer(field string) string {
	switch field {
	case "buyer_name":
		return v.BuyerName
	case "buyer_street":
		return v.BuyerStreet
	case "buyer_city":
		return v.BuyerCity
	case "buyer_zip":
		return v.BuyerZip
	case "buyer_ico":
		return v.BuyerICO
	case "buyer_dic":
		return v.BuyerDIC
	case "buyer_email":
		return v.BuyerEmail
	}
	return ""
}

// ICOOK is validation.ico_ok: a Czech IC, 8 ASCII digits whose last is the
// mod-11 check digit. (Python also accepts non-ASCII decimal digits; Go does
// not, a known gap.)
func ICOOK(ico string) bool {
	text := pyStrip(ico)
	if len(text) != 8 {
		return false
	}
	weights := []int{8, 7, 6, 5, 4, 3, 2}
	total := 0
	for i, w := range weights {
		d := text[i]
		if d < '0' || d > '9' {
			return false
		}
		total += int(d-'0') * w
	}
	last := text[7]
	if last < '0' || last > '9' {
		return false
	}
	rem := total % 11
	check := 11 - rem
	if rem == 0 {
		check = 1
	} else if rem == 1 {
		check = 0
	}
	return int(last-'0') == check
}

// ReadForm is billing_order.read_form: the posted order and its errors as
// {field: copy key}. The email check is ubyport.NormaliseEmail, which the
// ubyport golden tests keep equal to mail.normalise_email.
func ReadForm(form map[string]string) (OrderValues, map[string]string) {
	v := OrderValues{
		Plan:            form["plan"],
		BillingInterval: form["billing_interval"],
		AddonTTLock:     form["addon_ttlock"] == "1",
		AddonWhitelabel: form["addon_whitelabel"] == "1",
		BuyerName:       pyStrip(form["buyer_name"]),
		BuyerStreet:     pyStrip(form["buyer_street"]),
		BuyerCity:       pyStrip(form["buyer_city"]),
		BuyerZip:        strings.ReplaceAll(pyStrip(form["buyer_zip"]), " ", ""),
		BuyerICO:        pyStrip(form["buyer_ico"]),
		BuyerDIC:        pyStrip(form["buyer_dic"]),
		BuyerEmail:      pyStrip(form["buyer_email"]),
	}
	errs := map[string]string{}
	if !contains(Plans, v.Plan) {
		errs["plan"] = "billing.order.error.plan"
	}
	if !contains(Intervals, v.BillingInterval) {
		errs["billing_interval"] = "billing.order.error.plan"
	}
	for _, f := range []string{"buyer_name", "buyer_street", "buyer_city"} {
		if v.buyer(f) == "" {
			errs[f] = "billing.order.error.required"
		}
	}
	if !zipOK(v.BuyerZip) {
		errs["buyer_zip"] = "billing.order.error.zip"
	}
	if v.BuyerICO != "" && !ICOOK(v.BuyerICO) {
		errs["buyer_ico"] = "billing.order.error.ico"
	}
	email := ubyport.NormaliseEmail(v.BuyerEmail)
	if email == "" {
		errs["buyer_email"] = "billing.order.error.email"
	} else {
		v.BuyerEmail = email
	}
	return v, errs
}

// zipOK is len(zip) == 5 and zip.isdigit().
func zipOK(zip string) bool {
	if utf8.RuneCountInString(zip) != 5 {
		return false
	}
	for _, r := range zip {
		if !unicode.IsDigit(r) {
			return false
		}
	}
	return true
}

// Apartments is billing_order.apartments: the active ones, at least one.
func Apartments(ctx context.Context, q DB, owner int64) (int, error) {
	n, err := ApartmentCount(ctx, q, owner)
	if err != nil {
		return 0, err
	}
	if n < 1 {
		n = 1
	}
	return n, nil
}

// PeriodEnd is billing_trial.period_end: the last day of a month or year that
// starts on start.
func PeriodEnd(start time.Time, interval string) time.Time {
	start = dayOf(start)
	var year int
	var month time.Month
	if interval == "year" {
		year, month = start.Year()+1, start.Month()
	} else {
		year, month = start.Year()+int(start.Month())/12, time.Month(int(start.Month())%12+1)
	}
	last := time.Date(year, month+1, 0, 0, 0, 0, 0, time.UTC).Day()
	if start.Day() > last {
		// 31 January runs to the end of February.
		return time.Date(year, month, last, 0, 0, 0, 0, time.UTC)
	}
	return time.Date(year, month, start.Day(), 0, 0, 0, 0, time.UTC).AddDate(0, 0, -1)
}

// PlaceResult is the dict of billing_order.place (InvoiceID 0 = none).
type PlaceResult struct {
	Starts    string `json:"starts"` // trial_end or now
	Date      string `json:"date"`
	InvoiceID int64  `json:"invoice_id"`
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// Place is billing_order.place: save the order. In a trial it starts when the
// trial ends; when paused it starts today and the first invoice is issued and
// mailed at once. actor is written on the order and status audit rows (Python
// writes "host"; pass HostActor or the signed-in username).
func Place(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, v OrderValues,
	today time.Time, actor string) (PlaceResult, error) {
	acc, err := Account(ctx, pool, owner)
	if err != nil {
		return PlaceResult{}, err
	}
	if acc == nil {
		return PlaceResult{}, ErrNoAccount
	}
	if !contains(Orderable, acc.Status) {
		return PlaceResult{}, ErrAlreadyOrdered
	}
	if v.AddonWhitelabel && !acc.AddonWhitelabel {
		return PlaceResult{}, ErrWhitelabelUnavailable
	}
	day := dayOf(today)
	apartments, err := Apartments(ctx, pool, owner)
	if err != nil {
		return PlaceResult{}, err
	}
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET plan = $1, billing_interval = $2, addon_ttlock = $3,
		addon_whitelabel = $4, apartments_billed = $5, pending_change_json = NULL,
		buyer_name = $6, buyer_street = $7, buyer_city = $8, buyer_zip = $9, buyer_ico = $10,
		buyer_dic = $11, buyer_email = $12, updated_at = $13 WHERE owner_user_id = $14`,
		v.Plan, v.BillingInterval, flag(v.AddonTTLock), flag(acc.AddonWhitelabel), apartments,
		nullable(v.BuyerName), nullable(v.BuyerStreet), nullable(v.BuyerCity), nullable(v.BuyerZip),
		nullable(v.BuyerICO), nullable(v.BuyerDIC), nullable(v.BuyerEmail), ubyport.UTCNow(), owner); err != nil {
		return PlaceResult{}, err
	}
	if err := audit(ctx, pool, actor, "billing_order", v.Plan+" "+v.BillingInterval, owner); err != nil {
		return PlaceResult{}, err
	}
	if acc.Status != "paused" {
		return PlaceResult{Starts: "trial_end", Date: first10(acc.TrialEndsAt)}, nil
	}
	end := PeriodEnd(day, v.BillingInterval)
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET period_start = $1, period_end = $2, updated_at = $3
		WHERE owner_user_id = $4`, isoDay(day), isoDay(end), ubyport.UTCNow(), owner); err != nil {
		return PlaceResult{}, err
	}
	if _, err := SetStatus(ctx, pool, owner, "active", actor); err != nil {
		return PlaceResult{}, err
	}
	id, err := inv.IssueForPeriod(ctx, owner, isoDay(day), isoDay(end), day)
	if err != nil {
		return PlaceResult{}, err
	}
	if err := inv.Send(ctx, id); err != nil {
		return PlaceResult{}, err
	}
	return PlaceResult{Starts: "now", Date: isoDay(day), InvoiceID: id}, nil
}

// Change is billing_order.change: preview or save one change; a rise on an
// annual plan may issue and send a supplementary invoice (ChangeResult.InvoiceID).
func Change(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, field string, value any,
	confirm bool, today time.Time, actor string) (ChangeResult, error) {
	day := dayOf(today)
	result, err := ApplyChange(ctx, pool, owner, field, value, day, confirm, actor)
	if err != nil {
		return ChangeResult{}, err
	}
	if !confirm || result.SupplementaryCZK == 0 {
		return result, nil
	}
	acc, err := Account(ctx, pool, owner)
	if err != nil {
		return ChangeResult{}, err
	}
	if acc == nil {
		return ChangeResult{}, fmt.Errorf("billing account %d vanished", owner)
	}
	periodTo := first10(acc.PeriodEnd)
	if periodTo == "" {
		periodTo = isoDay(day)
	}
	id, err := inv.IssueSupplementary(ctx, owner, int64(result.SupplementaryCZK),
		"Doplatek za změnu předplatného od "+day.Format("02.01.2006"), isoDay(day), periodTo, day)
	if err != nil {
		return ChangeResult{}, err
	}
	result.InvoiceID = id
	if err := inv.Send(ctx, id); err != nil {
		return ChangeResult{}, err
	}
	return result, nil
}

// Cancel is billing_order.cancel: end at the period's end, active -> canceling.
func Cancel(ctx context.Context, pool *pgxpool.Pool, owner int64, actor string) (bool, error) {
	return setCancelFlag(ctx, pool, owner, "canceling", 1, actor)
}

// Resume is billing_order.resume: take a cancellation back, canceling -> active.
func Resume(ctx context.Context, pool *pgxpool.Pool, owner int64, actor string) (bool, error) {
	return setCancelFlag(ctx, pool, owner, "active", 0, actor)
}

func setCancelFlag(ctx context.Context, pool *pgxpool.Pool, owner int64, status string, flagValue int, actor string) (bool, error) {
	moved, err := SetStatus(ctx, pool, owner, status, actor)
	if err != nil || !moved {
		return false, err
	}
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET cancel_at_period_end = $1, updated_at = $2 WHERE owner_user_id = $3`,
		flagValue, ubyport.UTCNow(), owner); err != nil {
		return false, err
	}
	return true, nil
}

// PlaceForOperator is billing_order.place_for_operator: assign a plan to a host
// who has none (0448). It creates the account if needed, pauses it through
// OperatorPause, places the order starting today with the first invoice issued
// at once, and writes the "(operator assign)" audit row with actor.
//
// Python's inner place() writes actor "host"; with WithAuditActor on ctx the
// audit replaces it by the signed-in username, as db.audit does. Go writes
// HostActor for those two rows (order, status active) and actor for the pause
// and "(operator assign)" rows.
func PlaceForOperator(ctx context.Context, pool *pgxpool.Pool, inv Invoicer, owner int64, v OrderValues,
	today time.Time, actor string) (PlaceResult, error) {
	day := dayOf(today)
	acc, err := EnsureAccount(ctx, pool, owner)
	if err != nil {
		return PlaceResult{}, err
	}
	if acc.Plan != "" {
		return PlaceResult{}, ErrAlreadyOrdered
	}
	if v.AddonWhitelabel && !acc.AddonWhitelabel {
		return PlaceResult{}, ErrWhitelabelUnavailable
	}
	if _, err := OperatorPause(ctx, pool, owner, actor); err != nil {
		return PlaceResult{}, err
	}
	result, err := Place(ctx, pool, inv, owner, v, day, HostActor)
	if err != nil {
		return PlaceResult{}, err
	}
	if err := audit(ctx, pool, actor, "billing_order", v.Plan+" "+v.BillingInterval+" (operator assign)", owner); err != nil {
		return PlaceResult{}, err
	}
	return result, nil
}

// ExtendTrial is billing_order.extend_trial: move a running trial's end date
// (0448). It returns the new YYYY-MM-DD, or "" when refused (no account, not
// trialing, no end date). days outside 1..365 is ErrBadDays.
func ExtendTrial(ctx context.Context, pool *pgxpool.Pool, owner int64, days int, actor string,
	today time.Time) (string, error) {
	day := dayOf(today)
	if days <= 0 || days > 365 {
		return "", ErrBadDays
	}
	acc, err := Account(ctx, pool, owner)
	if err != nil {
		return "", err
	}
	if acc == nil || acc.Status != "trialing" || acc.TrialEndsAt == "" {
		return "", nil
	}
	current, err := parseDay(acc.TrialEndsAt)
	if err != nil {
		return "", err
	}
	if day.After(current) {
		current = day
	}
	newEnd := isoDay(current.AddDate(0, 0, days))
	if _, err := pool.Exec(ctx, `UPDATE billing_account SET trial_ends_at = $1, updated_at = $2 WHERE owner_user_id = $3`,
		newEnd, ubyport.UTCNow(), owner); err != nil {
		return "", err
	}
	if err := audit(ctx, pool, actor, "billing_trial_extended", fmt.Sprintf("+%dd -> %s", days, newEnd), owner); err != nil {
		return "", err
	}
	return newEnd, nil
}
