package billingweb

import (
	"context"
	"time"
)

// billingStates is the filter list of the page (routes/admin_billing.py line 51).
var billingStates = map[string]bool{
	"trial_pending": true, "trialing": true, "active": true, "overdue": true, "canceling": true, "paused": true,
}

// AdminPage is the context of billing_admin_page without rendering; the JSON
// keys are the keys of the Python context. posthog_url, signup_enabled and
// ads_export_days come from config and the page thread adds them; fmt_date
// and kc are functions (Kc is here).
type AdminPage struct {
	Month        string           `json:"month"`
	Invoices     []Invoice        `json:"invoices"`
	Unpaid       []UnpaidInvoice  `json:"unpaid"`
	UnpaidTotal  string           `json:"unpaid_total"`
	Payments     []BankPayment    `json:"payments"`
	Accounts     map[string]int64 `json:"accounts"`
	Today        string           `json:"today"`
	Q            string           `json:"q"`
	State        string           `json:"state"`
	Cockpit      Portfolio        `json:"cockpit"`
	Revenue      Revenue          `json:"revenue"`
	Watch        Watch            `json:"watch"`
	Aging        map[string]int64 `json:"aging"`
	Forecast     Forecast         `json:"forecast"`
	TrendRows    []TrendRow       `json:"trend_rows"`
	Movement     Movement         `json:"movement"`
	FunnelCounts Funnel           `json:"funnel_counts"`
	Discounts    Discounts        `json:"discounts"`
}

// AdminPageData is the context assembly of routes/admin_billing.billing_admin_page
// (lines 33-69). month is the raw `mesic` query value, qstr the raw `q`, state
// the raw `state`; the invalid ones fall back like the route does. q is the
// database. Only the Y-M-D of today is used (zero means now).
func AdminPageData(ctx context.Context, q DB, month, qstr, state string, today time.Time) (AdminPage, error) {
	day := dayOf(today)
	p := AdminPage{
		Month: MonthOrCurrent(month, day),
		Today: isoDay(day),
		Q:     cut(pyStrip(qstr), 120),
	}
	if billingStates[state] {
		p.State = state
	}
	var err error
	if p.Invoices, err = Invoices(ctx, q, p.Month); err != nil {
		return AdminPage{}, err
	}
	if p.Unpaid, err = Unpaid(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	var total int64
	for _, u := range p.Unpaid {
		total += u.TotalHaler
	}
	p.UnpaidTotal = Kc(total)
	if p.Payments, err = Unmatched(ctx, q); err != nil {
		return AdminPage{}, err
	}
	if p.Accounts, err = AccountsByStatus(ctx, q); err != nil {
		return AdminPage{}, err
	}
	if p.Cockpit, err = GetPortfolio(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	if p.Revenue, err = RevenueTotals(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	if p.Watch, err = Watchlists(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	if p.Aging, err = Aging(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	if p.Forecast, err = GetForecast(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	if p.TrendRows, err = Trend(ctx, q, 12); err != nil {
		return AdminPage{}, err
	}
	if p.Movement, err = GetMovement(ctx, q, p.Month); err != nil {
		return AdminPage{}, err
	}
	if p.FunnelCounts, err = GetFunnel(ctx, q); err != nil {
		return AdminPage{}, err
	}
	if p.Discounts, err = DiscountOverview(ctx, q, day); err != nil {
		return AdminPage{}, err
	}
	return p, nil
}
