package billingweb

import (
	"archive/zip"
	"bytes"
	"context"
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
)

// mrrStates is billing_analytics.MRR_STATES (line 18): the states that count as
// a paying customer for MRR.
var mrrStates = map[string]bool{"active": true, "overdue": true, "canceling": true}

var (
	customersCSVHeader = []string{
		"Uzivatel", "Email", "Stav", "Plan", "Interval", "Byty", "Zaklad Kc",
		"Max Kc", "TTLock Kc", "Whitelabel Kc", "Zaloha Kc", "Cistea Kc",
		"Mesicni Kc", "Zacatek obdobi", "Konec obdobi", "Zrusit ke konci",
	}
	invoicesCSVHeader = []string{
		"Cislo", "Druh", "Opravuje", "Vystaveno", "Splatnost", "Obdobi od", "Obdobi do",
		"Uzivatel", "Castka Kc", "VS", "Zaplaceno", "Zpusob uhrady", "Stornovana",
	}
	paymentsCSVHeader = []string{"Nadpis", "Prijato", "Castka Kc", "VS", "Protiucet", "Zprava", "Stav"}
)

// Customer is one portfolio entry: the account row plus its priced fields.
type Customer struct {
	OwnerUserID       int64         `json:"owner_user_id"`
	Status            string        `json:"status"`
	Plan              string        `json:"plan"`
	BillingInterval   string        `json:"billing_interval"`
	ApartmentsBilled  int64         `json:"apartments_billed"`
	AddonTTLock       int64         `json:"addon_ttlock"`
	AddonWhitelabel   int64         `json:"addon_whitelabel"`
	CarryCZK          int64         `json:"carry_czk"`
	CancelAtPeriodEnd int64         `json:"cancel_at_period_end"`
	DiscountPercent   int64         `json:"discount_percent"`
	DiscountReason    *string       `json:"discount_reason"`
	TrialEndsAt       *string       `json:"trial_ends_at"`
	PeriodStart       *string       `json:"period_start"`
	PeriodEnd         *string       `json:"period_end"`
	DisplayName       *string       `json:"display_name"`
	Email             *string       `json:"email"`
	Username          string        `json:"username"`
	Quote             billing.Price `json:"quote"`
	NetCZK            int64         `json:"net_czk"`
	MonthlyCZK        int64         `json:"monthly_czk"`
	TrialEnds         string        `json:"trial_ends"`
	TrialDaysLeft     *int          `json:"trial_days_left"`
}

// Portfolio is billing_analytics.portfolio's dict.
type Portfolio struct {
	Customers []Customer       `json:"customers"`
	MRRCZK    int64            `json:"mrr_czk"`
	ARRCZK    int64            `json:"arr_czk"`
	ByStatus  map[string]int64 `json:"by_status"`
	Today     string           `json:"today"`
}

// GetPortfolio is billing_analytics.portfolio (lines 46-90): every billing
// account that has a plan, priced by billing.Quote so the cockpit can never
// disagree with an issued invoice.
func GetPortfolio(ctx context.Context, q DB, today time.Time) (Portfolio, error) {
	day := dayOf(today)
	customers, err := queryAll(ctx, q, func(r pgx.Rows) (Customer, error) {
		var c Customer
		var interval *string
		err := r.Scan(&c.OwnerUserID, &c.Status, &c.Plan, &interval, &c.ApartmentsBilled,
			&c.AddonTTLock, &c.AddonWhitelabel, &c.CarryCZK, &c.CancelAtPeriodEnd,
			&c.DiscountPercent, &c.DiscountReason, &c.TrialEndsAt, &c.PeriodStart, &c.PeriodEnd,
			&c.DisplayName, &c.Email, &c.Username)
		c.BillingInterval = deref(interval)
		return c, err
	}, `SELECT b.owner_user_id, b.status, b.plan, b.billing_interval, b.apartments_billed,
		b.addon_ttlock, b.addon_whitelabel, b.carry_czk, b.cancel_at_period_end,
		b.discount_percent, b.discount_reason,
		b.trial_ends_at, b.period_start, b.period_end,
		u.display_name, u.email, u.username
		FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id
		WHERE b.plan IS NOT NULL ORDER BY b.owner_user_id`)
	if err != nil {
		return Portfolio{}, err
	}
	out := Portfolio{Customers: customers, ByStatus: map[string]int64{}, Today: isoDay(day)}
	for n := range out.Customers {
		c := &out.Customers[n]
		c.Quote, err = billing.Quote(int(c.ApartmentsBilled), c.Plan, c.BillingInterval,
			c.AddonTTLock != 0, c.AddonWhitelabel != 0, int(c.DiscountPercent))
		if err != nil {
			return Portfolio{}, err
		}
		c.NetCZK = int64(c.Quote.Total) + c.CarryCZK
		c.MonthlyCZK = int64(billing.Monthly(int(c.NetCZK), c.BillingInterval))
		if mrrStates[c.Status] {
			out.MRRCZK += c.MonthlyCZK
			if c.BillingInterval == "year" {
				out.ARRCZK += c.NetCZK
			} else {
				out.ARRCZK += c.MonthlyCZK * 12
			}
		}
		out.ByStatus[c.Status]++
		c.TrialEnds = cut(deref(c.TrialEndsAt), 10)
		if c.Status == "trialing" && c.TrialEnds != "" {
			ends, err := parseDay(c.TrialEnds)
			if err != nil {
				return Portfolio{}, fmt.Errorf("trial_ends_at of owner %d: %w", c.OwnerUserID, err)
			}
			left := daysBetween(ends, day)
			c.TrialDaysLeft = &left
		}
	}
	return out, nil
}

// NextMonthStart is billing_analytics.next_month_start (lines 93-97).
func NextMonthStart(day time.Time) string {
	d := dayOf(day)
	return isoDay(time.Date(d.Year(), d.Month()+1, 1, 0, 0, 0, 0, time.UTC))
}

// Revenue is billing_analytics.revenue_totals' dict.
type Revenue struct {
	BilledCZK    int64 `json:"billed_czk"`
	CollectedCZK int64 `json:"collected_czk"`
}

// RevenueTotals is billing_analytics.revenue_totals (lines 100-116): billed
// vs collected this month, separate figures, never summed. Whole crowns are
// floored, as Python's // is.
func RevenueTotals(ctx context.Context, q DB, today time.Time) (Revenue, error) {
	day := dayOf(today)
	start := day.Format("2006-01") + "-01"
	end := NextMonthStart(day)
	var billed, collected int64
	if err := q.QueryRow(ctx, `SELECT COALESCE(SUM(total_haler), 0)::bigint FROM platform_invoice
		WHERE voided = 0 AND issue_date >= $1 AND issue_date < $2`, start, end).Scan(&billed); err != nil {
		return Revenue{}, err
	}
	if err := q.QueryRow(ctx, `SELECT COALESCE(SUM(total_haler), 0)::bigint FROM platform_invoice
		WHERE voided = 0 AND paid_on >= $1 AND paid_on < $2`, start, end).Scan(&collected); err != nil {
		return Revenue{}, err
	}
	return Revenue{BilledCZK: floorDiv(billed, 100), CollectedCZK: floorDiv(collected, 100)}, nil
}

// TrialEnding, OverdueInvoice and EndingAccount are the watchlist rows.
type TrialEnding struct {
	OwnerUserID int64   `json:"owner_user_id"`
	TrialEndsAt *string `json:"trial_ends_at"`
	DisplayName *string `json:"display_name"`
	Email       *string `json:"email"`
}

type OverdueInvoice struct {
	ID          int64   `json:"id"`
	Number      string  `json:"number"`
	TotalHaler  int64   `json:"total_haler"`
	DueDate     string  `json:"due_date"`
	OwnerUserID int64   `json:"owner_user_id"`
	DisplayName *string `json:"display_name"`
	DaysLate    int     `json:"days_late"`
}

type EndingAccount struct {
	OwnerUserID int64   `json:"owner_user_id"`
	PeriodEnd   *string `json:"period_end"`
	DisplayName *string `json:"display_name"`
	Email       *string `json:"email"`
}

// Watch is billing_analytics.watchlists' dict.
type Watch struct {
	TrialsEnding []TrialEnding    `json:"trials_ending"`
	Overdue      []OverdueInvoice `json:"overdue"`
	Ending       []EndingAccount  `json:"ending"`
}

// Watchlists is billing_analytics.watchlists (lines 119-146): the operator's
// morning list. Trials end within seven days; the text comparison of
// trial_ends_at with the day after the week is the Python one, so a trial
// ending on day 7 with a time is not listed. Ties in the order break by id.
func Watchlists(ctx context.Context, q DB, today time.Time) (Watch, error) {
	day := dayOf(today)
	week := isoDay(day.AddDate(0, 0, 7))
	var w Watch
	var err error
	w.TrialsEnding, err = queryAll(ctx, q, func(r pgx.Rows) (TrialEnding, error) {
		var t TrialEnding
		return t, r.Scan(&t.OwnerUserID, &t.TrialEndsAt, &t.DisplayName, &t.Email)
	}, `SELECT b.owner_user_id, b.trial_ends_at, u.display_name, u.email
		FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id
		WHERE b.status = 'trialing' AND b.trial_ends_at >= $1 AND b.trial_ends_at <= $2
		ORDER BY b.trial_ends_at, b.owner_user_id`, isoDay(day), week)
	if err != nil {
		return Watch{}, err
	}
	w.Overdue, err = queryAll(ctx, q, func(r pgx.Rows) (OverdueInvoice, error) {
		var o OverdueInvoice
		return o, r.Scan(&o.ID, &o.Number, &o.TotalHaler, &o.DueDate, &o.OwnerUserID, &o.DisplayName)
	}, `SELECT i.id, i.number, i.total_haler, i.due_date, i.owner_user_id, u.display_name
		FROM platform_invoice i JOIN user_account u ON u.id = i.owner_user_id
		WHERE i.voided = 0 AND i.paid_on IS NULL AND i.due_date < $1
		ORDER BY i.due_date, i.id`, isoDay(day))
	if err != nil {
		return Watch{}, err
	}
	w.Ending, err = queryAll(ctx, q, func(r pgx.Rows) (EndingAccount, error) {
		var e EndingAccount
		return e, r.Scan(&e.OwnerUserID, &e.PeriodEnd, &e.DisplayName, &e.Email)
	}, `SELECT b.owner_user_id, b.period_end, u.display_name, u.email
		FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id
		WHERE b.cancel_at_period_end = 1 ORDER BY b.period_end, b.owner_user_id`)
	if err != nil {
		return Watch{}, err
	}
	for n := range w.Overdue {
		due, err := parseDay(w.Overdue[n].DueDate)
		if err != nil {
			return Watch{}, fmt.Errorf("due_date of invoice %d: %w", w.Overdue[n].ID, err)
		}
		w.Overdue[n].DaysLate = daysBetween(day, due)
	}
	return w, nil
}

// Unverified is one signup waiting for its email link.
type Unverified struct {
	ID          int64   `json:"id"`
	DisplayName *string `json:"display_name"`
	Email       *string `json:"email"`
	CreatedAt   string  `json:"created_at"`
}

// Queue is billing_analytics.operator_queue's dict.
type Queue struct {
	Overdue      []OverdueInvoice `json:"overdue"`
	TrialsEnding []TrialEnding    `json:"trials_ending"`
	Ending       []EndingAccount  `json:"ending"`
	Unverified   []Unverified     `json:"unverified"`
}

func first[T any](s []T, n int) []T {
	if len(s) > n {
		return s[:n]
	}
	return s
}

// OperatorQueue is billing_analytics.operator_queue (lines 149-170): what needs
// attention today, 25 rows per card.
func OperatorQueue(ctx context.Context, q DB, today time.Time) (Queue, error) {
	lists, err := Watchlists(ctx, q, today)
	if err != nil {
		return Queue{}, err
	}
	unverified, err := queryAll(ctx, q, func(r pgx.Rows) (Unverified, error) {
		var u Unverified
		return u, r.Scan(&u.ID, &u.DisplayName, &u.Email, &u.CreatedAt)
	}, `SELECT u.id, u.display_name, u.email, u.created_at FROM user_account u
		WHERE u.role = 'host' AND u.signup_at IS NOT NULL AND u.email_verified_at IS NULL
		AND u.active = 0 ORDER BY u.created_at DESC, u.id LIMIT 25`)
	if err != nil {
		return Queue{}, err
	}
	return Queue{
		Overdue: first(lists.Overdue, 25), TrialsEnding: first(lists.TrialsEnding, 25),
		Ending: first(lists.Ending, 25), Unverified: unverified,
	}, nil
}

// Aging is billing_analytics.aging (lines 173-185): unpaid, unvoided invoices
// by days past due, whole crowns floored per invoice.
func Aging(ctx context.Context, q DB, today time.Time) (map[string]int64, error) {
	day := dayOf(today)
	type late struct {
		due   string
		haler int64
	}
	rows, err := queryAll(ctx, q, func(r pgx.Rows) (late, error) {
		var l late
		return l, r.Scan(&l.due, &l.haler)
	}, `SELECT due_date, total_haler FROM platform_invoice
		WHERE voided = 0 AND paid_on IS NULL AND due_date < $1`, isoDay(day))
	if err != nil {
		return nil, err
	}
	buckets := map[string]int64{"0-7": 0, "8-30": 0, "31-90": 0, "90+": 0}
	for _, r := range rows {
		due, err := parseDay(r.due)
		if err != nil {
			return nil, err
		}
		days := daysBetween(day, due)
		key := "90+"
		switch {
		case days <= 7:
			key = "0-7"
		case days <= 30:
			key = "8-30"
		case days <= 90:
			key = "31-90"
		}
		buckets[key] += floorDiv(r.haler, 100)
	}
	return buckets, nil
}

// Forecast is billing_analytics.forecast (lines 232-241).
type Forecast struct {
	Next30DaysCZK int64 `json:"next_30_days_czk"`
}

// GetForecast is billing_analytics.forecast: open invoices due in the next 30 days.
func GetForecast(ctx context.Context, q DB, today time.Time) (Forecast, error) {
	day := dayOf(today)
	var h int64
	err := q.QueryRow(ctx, `SELECT COALESCE(SUM(total_haler), 0)::bigint FROM platform_invoice
		WHERE voided = 0 AND paid_on IS NULL AND due_date >= $1 AND due_date <= $2`,
		isoDay(day), isoDay(day.AddDate(0, 0, 30))).Scan(&h)
	return Forecast{Next30DaysCZK: floorDiv(h, 100)}, err
}

// MovementParts and Movement are billing_analytics.movement's dict.
type MovementParts struct {
	New          int64 `json:"new"`
	Expansion    int64 `json:"expansion"`
	Contraction  int64 `json:"contraction"`
	Churn        int64 `json:"churn"`
	Reactivation int64 `json:"reactivation"`
}

type Movement struct {
	Month       string        `json:"month"`
	Previous    string        `json:"previous"`
	TotalChange int64         `json:"total_change"`
	Parts       MovementParts `json:"parts"`
	CurrentMRR  int64         `json:"current_mrr"`
}

// GetMovement is billing_analytics.movement (lines 285-322): the month over
// month MRR change decomposed, from billing_month_snapshot. month is YYYY-MM.
func GetMovement(ctx context.Context, q DB, month string) (Movement, error) {
	if len(month) < 7 {
		return Movement{}, fmt.Errorf("bad month %q", month)
	}
	var year, mon int
	if _, err := fmt.Sscanf(month[:4], "%d", &year); err != nil {
		return Movement{}, fmt.Errorf("bad month %q", month)
	}
	if _, err := fmt.Sscanf(month[5:7], "%d", &mon); err != nil {
		return Movement{}, fmt.Errorf("bad month %q", month)
	}
	prev := fmt.Sprintf("%d-%02d", year, mon-1)
	if mon == 1 {
		prev = fmt.Sprintf("%d-12", year-1)
	}
	monthMRR := func(m string) (int64, error) {
		var s int64
		err := q.QueryRow(ctx, `SELECT COALESCE(SUM(monthly_czk), 0)::bigint FROM billing_month_snapshot
			WHERE month = $1 AND status IN ('active', 'overdue', 'canceling')`, m).Scan(&s)
		return s, err
	}
	cur, err := monthMRR(month)
	if err != nil {
		return Movement{}, err
	}
	before, err := monthMRR(prev)
	if err != nil {
		return Movement{}, err
	}
	type row struct {
		status     string
		monthly    int64
		prevCZK    *int64
		prevStatus *string
	}
	rows, err := queryAll(ctx, q, func(r pgx.Rows) (row, error) {
		var x row
		var owner int64
		return x, r.Scan(&owner, &x.status, &x.monthly, &x.prevCZK, &x.prevStatus)
	}, `SELECT s.owner_user_id, s.status, s.monthly_czk, p.monthly_czk AS prev_czk, p.status AS prev_status
		FROM billing_month_snapshot s LEFT JOIN billing_month_snapshot p
		ON p.owner_user_id = s.owner_user_id AND p.month = $1 WHERE s.month = $2`, prev, month)
	if err != nil {
		return Movement{}, err
	}
	var parts MovementParts
	for _, r := range rows {
		was := r.prevCZK != nil
		var prevCZK int64
		if was {
			prevCZK = *r.prevCZK
		}
		paying := mrrStates[r.status]
		wasPaying := was && r.prevStatus != nil && mrrStates[*r.prevStatus]
		switch {
		case paying && !wasPaying:
			parts.New += r.monthly
		case !paying && wasPaying:
			parts.Churn -= prevCZK
		case paying && wasPaying:
			if r.monthly > prevCZK {
				parts.Expansion += r.monthly - prevCZK
			} else if r.monthly < prevCZK {
				parts.Contraction -= prevCZK - r.monthly
			}
		}
	}
	return Movement{Month: month, Previous: prev, TotalChange: cur - before, Parts: parts, CurrentMRR: cur}, nil
}

// Funnel is billing_analytics.funnel's dict.
type Funnel struct {
	Hosts           int64 `json:"hosts"`
	Verified        int64 `json:"verified"`
	Trialed         int64 `json:"trialed"`
	Converted       int64 `json:"converted"`
	TrialConversion int64 `json:"trial_conversion"`
}

// GetFunnel is billing_analytics.funnel (lines 325-338): signup, verified,
// trial started, converted. trial_conversion rounds half to even.
func GetFunnel(ctx context.Context, q DB) (Funnel, error) {
	var f Funnel
	for _, one := range []struct {
		dst *int64
		sql string
	}{
		{&f.Hosts, "SELECT COUNT(*) FROM user_account WHERE role = 'host'"},
		{&f.Verified, "SELECT COUNT(*) FROM user_account WHERE role = 'host' AND email_verified_at IS NOT NULL"},
		{&f.Trialed, "SELECT COUNT(DISTINCT owner_user_id) FROM billing_account WHERE trial_started_at IS NOT NULL"},
		{&f.Converted, `SELECT COUNT(DISTINCT owner_user_id) FROM billing_month_snapshot
			WHERE status IN ('active', 'overdue', 'canceling')`},
	} {
		if err := q.QueryRow(ctx, one.sql).Scan(one.dst); err != nil {
			return Funnel{}, err
		}
	}
	if f.Trialed != 0 {
		f.TrialConversion = int64(math.RoundToEven(float64(100*f.Converted) / float64(f.Trialed)))
	}
	return f, nil
}

// TrendRow is one month of billing_analytics.trend.
type TrendRow struct {
	Month        string `json:"month"`
	BilledCZK    int64  `json:"billed_czk"`
	CollectedCZK int64  `json:"collected_czk"`
}

// Trend is billing_analytics.trend (lines 341-353): billed and collected per
// issue/paid month, the last `months` of them (the page passes 12).
func Trend(ctx context.Context, q DB, months int) ([]TrendRow, error) {
	type pair struct {
		m string
		h int64
	}
	scan := func(r pgx.Rows) (pair, error) {
		var p pair
		return p, r.Scan(&p.m, &p.h)
	}
	billed, err := queryAll(ctx, q, scan, `SELECT substr(issue_date, 1, 7) AS m, COALESCE(SUM(total_haler), 0)::bigint AS h
		FROM platform_invoice WHERE voided = 0 GROUP BY substr(issue_date, 1, 7)`)
	if err != nil {
		return nil, err
	}
	paidRows, err := queryAll(ctx, q, scan, `SELECT substr(paid_on, 1, 7) AS m, COALESCE(SUM(total_haler), 0)::bigint AS h
		FROM platform_invoice WHERE voided = 0 AND paid_on IS NOT NULL GROUP BY substr(paid_on, 1, 7)`)
	if err != nil {
		return nil, err
	}
	paid := map[string]int64{}
	for _, p := range paidRows {
		paid[p.m] = floorDiv(p.h, 100)
	}
	out := []TrendRow{}
	for _, b := range billed {
		out = append(out, TrendRow{Month: b.m, BilledCZK: floorDiv(b.h, 100), CollectedCZK: paid[b.m]})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Month < out[j].Month })
	if months >= 0 && len(out) > months {
		out = out[len(out)-months:]
	}
	return out, nil
}

// Discounts is billing_analytics.discount_overview's dict.
type Discounts struct {
	ListMRRCZK     int64      `json:"list_mrr_czk"`
	NetMRRCZK      int64      `json:"net_mrr_czk"`
	GiveawayMRRCZK int64      `json:"giveaway_mrr_czk"`
	ListTotalCZK   int64      `json:"list_total_czk"`
	NetTotalCZK    int64      `json:"net_total_czk"`
	Customers      []Customer `json:"customers"`
}

// DiscountOverview is billing_analytics.discount_overview (lines 356-370):
// list vs net across the portfolio, and who has a discount.
func DiscountOverview(ctx context.Context, q DB, today time.Time) (Discounts, error) {
	data, err := GetPortfolio(ctx, q, today)
	if err != nil {
		return Discounts{}, err
	}
	d := Discounts{NetMRRCZK: data.MRRCZK, Customers: []Customer{}}
	for _, c := range data.Customers {
		d.ListTotalCZK += int64(c.Quote.List)
		d.NetTotalCZK += c.NetCZK
		if mrrStates[c.Status] {
			d.ListMRRCZK += int64(billing.Monthly(c.Quote.List, c.BillingInterval))
			d.GiveawayMRRCZK += int64(billing.Monthly(c.Quote.Discount, c.BillingInterval))
		}
		if c.DiscountPercent > 0 {
			d.Customers = append(d.Customers, c)
		}
	}
	return d, nil
}

// exportFile is one CSV of the bulk export.
type exportFile struct {
	Name string
	Data []byte
}

// exportAllFiles builds the three CSV files of billing_analytics.export_all_zip
// (lines 199-229): zakaznici.csv, faktury.csv and platby.csv.
func exportAllFiles(ctx context.Context, q DB, today time.Time) ([]exportFile, error) {
	data, err := GetPortfolio(ctx, q, today)
	if err != nil {
		return nil, err
	}
	var customers [][]string
	for _, c := range data.Customers {
		cancel := ""
		if c.CancelAtPeriodEnd != 0 {
			cancel = "ano"
		}
		customers = append(customers, []string{
			deref(c.DisplayName), deref(c.Email), c.Status, c.Plan, c.BillingInterval,
			itoa(c.ApartmentsBilled), itoa(int64(c.Quote.Base)), itoa(int64(c.Quote.Max)),
			itoa(int64(c.Quote.TTLock)), itoa(int64(c.Quote.Whitelabel)), itoa(c.CarryCZK),
			itoa(c.NetCZK), itoa(c.MonthlyCZK), cut(deref(c.PeriodStart), 10),
			cut(deref(c.PeriodEnd), 10), cancel,
		})
	}
	type inv struct {
		number, kind, corrects, issue, due, from, to string
		owner                                        *int64
		total                                        int64
		voided                                       int64
		paidOn, paidVia                              *string
		vs                                           string
	}
	invs, err := queryAll(ctx, q, func(r pgx.Rows) (inv, error) {
		var i inv
		return i, r.Scan(&i.number, &i.kind, &i.corrects, &i.issue, &i.due, &i.from, &i.to, &i.owner,
			&i.total, &i.voided, &i.paidOn, &i.paidVia, &i.vs)
	}, `SELECT i.number, i.kind, COALESCE(c.number, ''), i.issue_date, i.due_date,
		i.period_from, i.period_to, i.owner_user_id, i.total_haler, i.voided, i.paid_on,
		i.paid_via, i.vs FROM platform_invoice i
		LEFT JOIN platform_invoice c ON c.id = i.corrects_id ORDER BY i.id`)
	if err != nil {
		return nil, err
	}
	var invoices [][]string
	for _, r := range invs {
		kind := r.kind
		if cs, ok := KindCS[kind]; ok {
			kind = cs
		}
		owner := ""
		if r.owner != nil {
			owner = itoa(*r.owner)
		}
		voided := ""
		if r.voided != 0 {
			voided = "ano"
		}
		invoices = append(invoices, []string{
			r.number, kind, r.corrects, cut(r.issue, 10), cut(r.due, 10), cut(r.from, 10), cut(r.to, 10),
			owner, KcCSV(r.total), r.vs, cut(deref(r.paidOn), 10), ViaCS[deref(r.paidVia)], voided,
		})
	}
	type pay struct {
		id, received string
		amount       int64
		vs, account  *string
		message      *string
		status       string
	}
	pays, err := queryAll(ctx, q, func(r pgx.Rows) (pay, error) {
		var p pay
		return p, r.Scan(&p.id, &p.received, &p.amount, &p.vs, &p.account, &p.message, &p.status)
	}, `SELECT bank_tx_id, received_on, amount_haler, vs, counter_account, message, status
		FROM bank_payment ORDER BY received_on, bank_tx_id`)
	if err != nil {
		return nil, err
	}
	var payments [][]string
	for _, p := range pays {
		payments = append(payments, []string{
			p.id, cut(p.received, 10), KcCSV(p.amount), deref(p.vs), deref(p.account),
			deref(p.message), p.status,
		})
	}
	return []exportFile{
		{"zakaznici.csv", csvBytes(customersCSVHeader, customers)},
		{"faktury.csv", csvBytes(invoicesCSVHeader, invoices)},
		{"platby.csv", csvBytes(paymentsCSVHeader, payments)},
	}, nil
}

// ExportAllZip is billing_analytics.export_all_zip: the bulk export, full
// history, three CSV files and no PDF, Excel-ready.
func ExportAllZip(ctx context.Context, q DB, today time.Time) ([]byte, error) {
	files, err := exportAllFiles(ctx, q, today)
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	for _, f := range files {
		w, err := zw.Create(f.Name)
		if err != nil {
			return nil, err
		}
		if _, err := w.Write(f.Data); err != nil {
			return nil, err
		}
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
