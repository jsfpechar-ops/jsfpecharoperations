package billingweb

// GET /admin/fakturace: the operator's billing page (routes/admin_billing.py
// billing_admin_page, lines 33-69, template admin_billing.html), brief 1560.
// The data comes from AdminPageData (brief 1341); this file adds the config
// values and the rows the template prints.

import (
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
)

// adminStates is the `states` list of the template, in its order.
var adminStates = []string{"trial_pending", "trialing", "active", "overdue", "canceling", "paused"}

// pyNone is how Jinja prints a missing text: None.
func pyNone(p *string) string {
	if p == nil {
		return "None"
	}
	return *p
}

func orEmpty(p *string) string { return deref(p) }

// minus is the template's `kc(x) if x >= 0 else '−' ~ kc(-x)`: a real minus sign, U+2212.
func minusKc(haler int64) string {
	if haler >= 0 {
		return Kc(haler)
	}
	return "−" + Kc(-haler)
}

// minusWhole is `(n ~ ' Kč') if n >= 0 else ('−' ~ (0 - n) ~ ' Kč')`.
func minusWhole(n int64) string {
	if n >= 0 {
		return strconv.FormatInt(n, 10) + " Kč"
	}
	return "−" + strconv.FormatInt(-n, 10) + " Kč"
}

type unpaidRow struct {
	ID                     int64
	Number, VS, Buyer, Amt string
	Overdue                bool
	Due                    string
}
type monthRow struct {
	ID                         int64
	Number, Issued, Buyer, Amt string
	StateKind, StateText       string
}
type watchRow struct {
	Index           int
	Kind, Who, When string
}
type portfolioRow struct {
	Owner                                   int64
	Name, Email, Plan, BadgeKind, BadgeText string
	Net, Monthly, PeriodEnd                 string
}
type paymentRow struct {
	Received, Message, VS, Amt, BadgeKind, BadgeText string
}
type trendRowView struct{ Month, Billed, Collected string }
type discountRow struct {
	Owner                          int64
	Name, Percent, Reason, Monthly string
}

// adminView is the data of admin_billing.tmpl.
type adminView struct {
	Month, Today, Q, State     string
	Unpaid                     []unpaidRow
	UnpaidCols, MonthCols      [][]any
	Invoices                   []monthRow
	WatchRows                  []watchRow
	WatchFirst                 bool // watch_rows: the card sits above the reports
	WatchCols                  [][]any
	StateOptions               [][]any
	Portfolio                  []portfolioRow
	PortfolioCols              [][]any
	Payments                   []paymentRow
	PaymentCols                [][]any
	RevenueFacts               [][]any
	TrendCols                  [][]any
	Trend                      []trendRowView
	MovementFacts, FunnelFacts [][]any
	DiscountFacts              [][]any
	DiscountCols               [][]any
	Discounts                  []discountRow
	AccountLines               []string
	PostHogURL                 string
	SignupEnabled              bool
	AdsDays                    int
	Tabs                       [][]any
}

// posthogURL is `config.POSTHOG_APP_URL if analytics.enabled() else ""`: the
// project key set and both PostHog hosts https and not the US ones.
func posthogURL(getenv func(string) string) string {
	trim := func(s string) string { return strings.TrimRight(strings.TrimSpace(s), "/") }
	or := func(v, def string) string {
		if v == "" {
			return def
		}
		return v
	}
	allowed := func(raw string) bool {
		u, err := url.Parse(raw)
		if err != nil || u.Scheme != "https" || u.Hostname() == "" {
			return false
		}
		host := u.Hostname()
		if u.Port() != "" {
			host += ":" + u.Port()
		}
		lower := strings.ToLower("https://" + host)
		return !strings.Contains(lower, "us.i.posthog.com") && !strings.Contains(lower, "us-assets.i.posthog.com")
	}
	key := strings.TrimSpace(getenv("POSTHOG_PROJECT_API_KEY"))
	if key == "" || !allowed(or(trim(getenv("POSTHOG_HOST")), "https://eu.i.posthog.com")) ||
		!allowed(or(trim(getenv("POSTHOG_ASSETS_HOST")), "https://eu-assets.i.posthog.com")) {
		return ""
	}
	return or(trim(getenv("POSTHOG_APP_URL")), "https://eu.posthog.com")
}

func signupOn(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_SIGNUP_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}

func badgeKindFor(status string) string {
	switch status {
	case "active":
		return "done"
	case "overdue", "canceling":
		return "action"
	}
	return "neutral"
}

func buildAdminView(lang tr, p AdminPage, getenv func(string) string) adminView {
	v := adminView{Month: p.Month, Today: p.Today, Q: p.Q, State: p.State,
		PostHogURL: posthogURL(getenv), SignupEnabled: signupOn(getenv), AdsDays: signup.GoogleExportDays}
	v.UnpaidCols = [][]any{{lang.t("billing.admin.col.number"), ""}, {lang.t("billing.admin.col.buyer"), ""},
		{lang.t("billing.admin.col.amount"), "r"}, {lang.t("billing.admin.col.due"), "r"}}
	for _, u := range p.Unpaid {
		v.Unpaid = append(v.Unpaid, unpaidRow{ID: u.ID, Number: u.Number, VS: u.VS, Buyer: u.Buyer.Name,
			Amt: Kc(u.TotalHaler), Overdue: u.Overdue, Due: fmtDate(u.DueDate)})
	}
	v.MonthCols = [][]any{{lang.t("billing.admin.col.number"), ""}, {lang.t("billing.admin.col.buyer"), ""},
		{lang.t("billing.admin.col.amount"), "r"}, {lang.t("billing.admin.col.state"), "r"}}
	for _, i := range p.Invoices {
		r := monthRow{ID: i.ID, Number: i.Number, Issued: fmtDate(i.IssueDate), Buyer: i.Buyer.Name, Amt: minusKc(i.TotalHaler)}
		switch {
		case i.Voided != 0 || i.Kind == "storno":
			r.StateKind, r.StateText = "neutral", lang.t("billing.invoices.state.void")
		case i.PaidOn != nil && *i.PaidOn != "":
			r.StateKind, r.StateText = "done", lang.t("billing.invoices.state.paid")
		default:
			r.StateKind, r.StateText = "action", lang.t("billing.invoices.state.open")
		}
		v.Invoices = append(v.Invoices, r)
	}
	// The watch card: trials ending, overdue invoices, ending accounts.
	add := func(kind, who, when string) {
		v.WatchRows = append(v.WatchRows, watchRow{Index: len(v.WatchRows) + 1, Kind: kind, Who: who, When: when})
	}
	for _, t := range p.Watch.TrialsEnding {
		add(lang.t("billing.admin.watch.trial"), pyNone(t.DisplayName), cut(pyNone(t.TrialEndsAt), 10))
	}
	for _, o := range p.Watch.Overdue {
		add(lang.t("billing.admin.watch.overdue"),
			pyNone(o.DisplayName)+" · "+o.Number+" · "+Kc(o.TotalHaler)+" Kč · "+strconv.Itoa(o.DaysLate), cut(o.DueDate, 10))
	}
	for _, e := range p.Watch.Ending {
		add(lang.t("billing.admin.watch.ending"), pyNone(e.DisplayName), cut(orEmpty(e.PeriodEnd), 10))
	}
	v.WatchFirst = len(p.Watch.TrialsEnding) > 0 || len(p.Watch.Overdue) > 0 || len(p.Watch.Ending) > 0
	v.WatchCols = [][]any{{lang.t("billing.admin.watch.kind"), ""}, {lang.t("billing.admin.watch.customer"), ""},
		{lang.t("billing.admin.watch.date"), "r"}}
	v.StateOptions = [][]any{{"", lang.t("billing.admin.portfolio.all")}}
	for _, s := range adminStates {
		v.StateOptions = append(v.StateOptions, []any{s, lang.t("billing.plan.state." + s)})
	}
	v.PortfolioCols = [][]any{{lang.t("billing.admin.col.buyer"), ""}, {lang.t("billing.admin.portfolio.plan"), ""},
		{lang.t("billing.admin.portfolio.state_col"), ""}, {lang.t("billing.admin.portfolio.price"), "r"},
		{lang.t("billing.admin.portfolio.monthly"), "r"}, {lang.t("billing.admin.portfolio.period_end"), "r"}}
	needle := strings.ToLower(p.Q)
	for _, c := range p.Cockpit.Customers {
		hay := strings.ToLower(orEmpty(c.DisplayName) + " " + orEmpty(c.Email) + " " + c.Username)
		if (p.Q != "" && !strings.Contains(hay, needle)) || (p.State != "" && c.Status != p.State) {
			continue
		}
		name := orEmpty(c.DisplayName)
		if name == "" {
			name = c.Username
		}
		end := cut(orEmpty(c.PeriodEnd), 10)
		if c.CancelAtPeriodEnd != 0 {
			end += " · " + lang.t("billing.admin.watch.ending")
		}
		if c.TrialDaysLeft != nil {
			end += " · " + lang.t("billing.admin.portfolio.trial_left") + " " + strconv.Itoa(*c.TrialDaysLeft)
		}
		v.Portfolio = append(v.Portfolio, portfolioRow{Owner: c.OwnerUserID, Name: name, Email: orEmpty(c.Email),
			Plan:      lang.t("billing.plan.name."+c.Plan) + " · " + lang.t("billing.interval."+c.BillingInterval) + " · " + strconv.FormatInt(c.ApartmentsBilled, 10),
			BadgeKind: badgeKindFor(c.Status), BadgeText: lang.t("billing.plan.state." + c.Status),
			Net: strconv.FormatInt(c.NetCZK, 10), Monthly: strconv.FormatInt(c.MonthlyCZK, 10), PeriodEnd: end})
	}
	v.PaymentCols = [][]any{{lang.t("billing.admin.col.received"), ""}, {lang.t("billing.admin.col.vs"), ""},
		{lang.t("billing.admin.col.amount"), "r"}, {lang.t("billing.admin.col.state"), "r"}}
	for _, b := range p.Payments {
		vs := orEmpty(b.VS)
		if vs == "" {
			vs = "—"
		}
		kind := "action"
		if b.Status == "overpaid" {
			kind = "done"
		}
		v.Payments = append(v.Payments, paymentRow{Received: fmtDate(b.ReceivedOn), Message: orEmpty(b.Message), VS: vs,
			Amt: Kc(b.AmountHaler), BadgeKind: kind, BadgeText: lang.t("billing.admin.payment." + b.Status)})
	}
	czk := func(n int64) string { return strconv.FormatInt(n, 10) + " Kč" }
	v.RevenueFacts = [][]any{
		{lang.t("billing.admin.revenue.mrr"), czk(p.Cockpit.MRRCZK)},
		{lang.t("billing.admin.revenue.arr"), czk(p.Cockpit.ARRCZK)},
		{lang.t("billing.admin.revenue.billed"), czk(p.Revenue.BilledCZK)},
		{lang.t("billing.admin.revenue.collected"), czk(p.Revenue.CollectedCZK)},
		{lang.t("billing.admin.revenue.forecast"), czk(p.Forecast.Next30DaysCZK)},
		{lang.t("billing.admin.unpaid_total"), p.UnpaidTotal + " Kč"},
	}
	v.TrendCols = [][]any{{lang.t("billing.admin.trend.month"), ""}, {lang.t("billing.admin.revenue.billed"), "r"},
		{lang.t("billing.admin.revenue.collected"), "r"}}
	for _, r := range p.TrendRows {
		v.Trend = append(v.Trend, trendRowView{r.Month, strconv.FormatInt(r.BilledCZK, 10), strconv.FormatInt(r.CollectedCZK, 10)})
	}
	m := p.Movement
	v.MovementFacts = [][]any{
		{lang.t("billing.admin.movement.change"), minusWhole(m.TotalChange)},
		{lang.t("billing.admin.movement.new"), czk(m.Parts.New)},
		{lang.t("billing.admin.movement.expansion"), czk(m.Parts.Expansion)},
		{lang.t("billing.admin.movement.contraction"), czk(m.Parts.Contraction)},
		{lang.t("billing.admin.movement.churn"), czk(m.Parts.Churn)},
	}
	f := p.FunnelCounts
	v.FunnelFacts = [][]any{
		{lang.t("billing.admin.funnel.hosts"), f.Hosts}, {lang.t("billing.admin.funnel.verified"), f.Verified},
		{lang.t("billing.admin.funnel.trialed"), f.Trialed}, {lang.t("billing.admin.funnel.converted"), f.Converted},
		{lang.t("billing.admin.funnel.rate"), strconv.FormatInt(f.TrialConversion, 10) + " %"},
	}
	d := p.Discounts
	v.DiscountFacts = [][]any{
		{lang.t("billing.admin.discounts.list_mrr"), czk(d.ListMRRCZK)},
		{lang.t("billing.admin.revenue.mrr"), czk(d.NetMRRCZK)},
		{lang.t("billing.admin.discounts.giveaway"), czk(d.GiveawayMRRCZK)},
	}
	v.DiscountCols = [][]any{{lang.t("billing.admin.col.buyer"), ""}, {lang.t("billing.admin.discounts.percent"), "r"},
		{lang.t("billing.admin.discounts.reason"), ""}, {lang.t("billing.admin.portfolio.monthly"), "r"}}
	for _, c := range d.Customers {
		name := orEmpty(c.DisplayName)
		if name == "" {
			name = c.Username
		}
		v.Discounts = append(v.Discounts, discountRow{Owner: c.OwnerUserID, Name: name,
			Percent: strconv.FormatInt(c.DiscountPercent, 10), Reason: orEmpty(c.DiscountReason), Monthly: strconv.FormatInt(c.MonthlyCZK, 10)})
	}
	for _, s := range adminStates {
		v.AccountLines = append(v.AccountLines, lang.t("billing.plan.state."+s)+": "+strconv.FormatInt(p.Accounts[s], 10))
	}
	return v
}

// adminTabs is ui_section_tabs() on an /admin page: the Money tab is open.
func adminTabs(lang tr) [][]any {
	items := [][3]string{
		{"/admin", "admin.tab.today", ""},
		{"/admin/customers", "customers.title", ""},
		{"/admin/fakturace", "admin.tab.money", "current"},
		{"/admin/operations", "admin.tab.system", ""},
	}
	out := make([][]any, len(items))
	for i, it := range items {
		out[i] = []any{it[0], lang.t(it[1]), it[2] != ""}
	}
	return out
}

// adminPageHandler serves GET /admin/fakturace (billing_admin_page).
func (d deps) adminPageHandler(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{admin: true})
	if c == nil {
		return
	}
	data, err := AdminPageData(r.Context(), d.pool, lastQuery(r, "mesic"), lastQuery(r, "q"), lastQuery(r, "state"), c.today())
	if err != nil {
		fail(w, err)
		return
	}
	lang := tr(c.lang)
	view := buildAdminView(lang, data, d.getenv)
	view.Tabs = adminTabs(lang)
	p := layout.Page{Title: lang.t("billing.admin.title"), Nav: "billing_admin", BodyKind: "detail", V2: true, AdminWorkspace: true}
	if err := layout.Render(w, r, layout.Env{Pool: d.pool, Getenv: d.getenv, Now: c.at}, c.h, p, pages, "admin_billing", view); err != nil {
		fail(w, err)
	}
}
