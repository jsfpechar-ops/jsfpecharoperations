package billingweb

// GET /predplatne: the host's plan page (routes/billing.py plan_page and _page,
// template billing_plan.html), brief 1556. The POST routes of the same path
// render the same page through renderPlan.

import (
	"embed"
	"html"
	"html/template"
	"net/http"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

// pages is the layout shell with this package's page templates and funcs.
var pages = layout.MustParseFuncs(catalog, template.FuncMap{
	"sec_head":     secHead,
	"card_head":    cardHead,
	"change_open":  changeOpen,
	"sec_head_raw": secHeadRaw,
}, templateFS, "templates/*.tmpl")

// tr translates with the request's language.
type tr string

func (lang tr) t(key string, pairs ...any) string {
	var p map[string]any
	if len(pairs) > 0 {
		p = map[string]any{}
		for i := 0; i+1 < len(pairs); i += 2 {
			p[pairs[i].(string)] = pairs[i+1]
		}
	}
	return catalog.T(string(lang), key, p)
}

// rsplitTitle is the h2 of ui_section with a tip: the title up to its last space,
// then the last word in a nowrap span that also holds the tip.
func rsplitTitle(title string, tip template.HTML) string {
	head, last := "", title
	if i := strings.LastIndex(title, " "); i >= 0 {
		head, last = html.EscapeString(title[:i])+" ", title[i+1:]
	}
	return head + `<span class="tip-nowrap">` + html.EscapeString(last) + `</span>` + string(tip)
}

func tipHTML(tip any) template.HTML {
	switch x := tip.(type) {
	case template.HTML:
		return x
	case string:
		return template.HTML(html.EscapeString(x))
	}
	return ""
}

// secHead opens a ui_section (macro ui_section in _ui_layout.html): the page
// writes the body and </section>. tip is a ui_tip result or "".
func secHead(title, id string, tip any) template.HTML {
	idAttr := ""
	if id != "" {
		idAttr = ` id="` + html.EscapeString(id) + `"`
	}
	h2 := html.EscapeString(title)
	if t := tipHTML(tip); t != "" {
		h2 = rsplitTitle(title, t)
	}
	return template.HTML(`<section class="ui-section"` + idAttr + `><div class="ui-section-h"><h2>` + h2 + `</h2></div>`)
}

// cardHead opens the invoices section of billing_plan.html, written out there.
func cardHead(title string, tip any) template.HTML {
	return template.HTML(`<section class="ui-section ui-section-card"><div class="ui-section-h"><h2>` +
		rsplitTitle(title, tipHTML(tip)) + `</h2></div>`)
}

// changeOpen is the change_form macro of billing_plan.html up to {{ caller() }}.
func changeOpen(csrf, field, value string) template.HTML {
	return template.HTML(`<form method="post" action="/predplatne/zmena">
<input type="hidden" name="_csrf" value="` + html.EscapeString(csrf) + `">
<input type="hidden" name="field" value="` + html.EscapeString(field) + `"><input type="hidden" name="value" value="` + html.EscapeString(value) + `">`)
}

// secHeadRaw opens a ui_section whose title is already markup (tip_label).
func secHeadRaw(title template.HTML, id string) template.HTML {
	return template.HTML(`<section class="ui-section" id="` + html.EscapeString(id) + `"><div class="ui-section-h"><h2>` + string(title) + `</h2></div>`)
}

func badge(kind, label string) template.HTML {
	return template.HTML(`<span class="ui-badge ui-badge-` + html.EscapeString(kind) + `">` + html.EscapeString(label) + `</span>`)
}

// choiceCard is one radio card: its label, whether it is checked and the line under it.
type choiceCard struct {
	Value, Label string
	Checked      bool
	Extra        template.HTML
}

// invoiceRow is one row of the invoices table.
type invoiceRow struct {
	ID                 int64
	Number, Date, Amt  string
	StateKind, StateTx string
}

// Preview is the dict of plan_change's preview (lines 134-137), with the
// whole-crown amounts already grouped.
type Preview struct {
	When, Field, Value, Before, After, Supplementary string
	SupplementaryCZK                                 int
}

// planView is the data of billing_plan.tmpl.
type planView struct {
	Note           string
	HasAcc         bool
	Orderable      bool
	Status         string
	Plan, Interval string
	CanChange      bool // status active or overdue
	IsMax          bool
	Canceling      bool
	Values         billing.OrderValues
	Errors         map[string]string // translated
	ApartmentCount int
	StatusLine     string
	OrderedLine    string
	PlanCards      []choiceCard
	IntervalCards  []choiceCard
	TotalFact      [][]any
	CurrentFacts   [][]any
	Preview        *Preview
	PreviewLine    string
	Upgrade        *Upgrade
	UpgradePerLine string
	SaveLine       string
	TTLockLine     string
	TTLockLabel    string // aria-label of the add/remove button
	TTLockButton   string
	TTLockValue    string
	OtherPlan      string
	PeriodEnd      string
	CancelTip      string
	CancelConfirm  string
	Invoices       []invoiceRow
	InvoiceColumns [][]any
	HasWhitelabel  bool
}

// planPage is the context of _page: the host's account, the form values and
// what the page may show. Errors holds copy keys; note is already translated.
type planPage struct {
	Values  billing.OrderValues
	Errors  map[string]string
	Note    string
	Preview *Preview
	Status  int
}

func buildPlanView(c *call, owner int64, pg planPage) (planView, error) {
	ctx := c.r.Context()
	lang := tr(c.lang)
	acc, err := billing.Account(ctx, c.pool, owner)
	if err != nil {
		return planView{}, err
	}
	count, err := billing.Apartments(ctx, c.pool, owner)
	if err != nil {
		return planView{}, err
	}
	v := planView{Note: pg.Note, Values: pg.Values, ApartmentCount: count, HasAcc: acc != nil,
		Errors: map[string]string{}, Preview: pg.Preview}
	for field, key := range pg.Errors {
		v.Errors[field] = lang.t(key)
	}
	// quote: only when both choices are valid; otherwise the total prints as "".
	total := ""
	if inList(billing.Plans, pg.Values.Plan) && inList(billing.Intervals, pg.Values.BillingInterval) {
		white := acc != nil && acc.AddonWhitelabel
		q, err := billing.Quote(count, pg.Values.Plan, pg.Values.BillingInterval, pg.Values.AddonTTLock, white, 0)
		if err != nil {
			return planView{}, err
		}
		total = kcWhole(q.Total)
	}
	v.TotalFact = [][]any{{lang.t("billing.order.total_" + pg.Values.BillingInterval),
		template.HTML(`<strong class="ui-num" data-billing-total>` + total + ` Kč</strong>`)}}
	if acc == nil {
		return v, nil
	}
	v.Status, v.Plan, v.Interval = acc.Status, acc.Plan, acc.BillingInterval
	v.Orderable = inList(billing.Orderable, acc.Status)
	trialEnds := fmtDate(acc.TrialEndsAt)
	v.PeriodEnd = fmtDate(acc.PeriodEnd)
	if v.Orderable {
		v.StatusLine = lang.t("billing.plan.status."+acc.Status, "date", trialEnds)
		if acc.Plan != "" {
			v.OrderedLine = lang.t("billing.plan.ordered", "plan", lang.t("billing.plan.name."+acc.Plan),
				"interval", lang.t("billing.interval."+acc.BillingInterval))
		}
		for _, p := range []string{"standard", "max"} {
			v.PlanCards = append(v.PlanCards, choiceCard{Value: p, Label: lang.t("billing.plan.name." + p),
				Checked: pg.Values.Plan == p,
				Extra:   template.HTML(`<p class="ui-sub">` + html.EscapeString(lang.t("billing.order.plan_"+p)) + `</p>`)})
		}
		for _, i := range []string{"year", "month"} {
			v.IntervalCards = append(v.IntervalCards, choiceCard{Value: i, Label: lang.t("billing.interval." + i),
				Checked: pg.Values.BillingInterval == i})
		}
		return v, nil
	}
	// The ordered plan: facts, preview, changes, cancel, invoices.
	var addons []string
	if acc.AddonTTLock && acc.Plan != "max" {
		addons = append(addons, lang.t("billing.order.ttlock"))
	}
	if acc.AddonWhitelabel {
		addons = append(addons, lang.t("billing.order.whitelabel"))
	}
	addonText := strings.Join(addons, ", ")
	if addonText == "" {
		addonText = "—"
	}
	kind := "neutral"
	switch acc.Status {
	case "active":
		kind = "done"
	case "overdue", "canceling":
		kind = "action"
	}
	v.CurrentFacts = [][]any{
		{lang.t("billing.plan.fact.plan"), lang.t("billing.plan.name." + acc.Plan)},
		{lang.t("billing.plan.fact.interval"), lang.t("billing.interval." + acc.BillingInterval)},
		{lang.t("billing.plan.fact.apartments"), strconv.Itoa(acc.ApartmentsBilled)},
		{lang.t("billing.plan.fact.addons"), addonText},
		{lang.t("billing.plan.fact.period_end"), v.PeriodEnd},
		{lang.t("billing.plan.fact.status"), badge(kind, lang.t("billing.plan.state."+acc.Status))},
	}
	if p := pg.Preview; p != nil {
		key := "billing.change.when_" + p.When
		if p.SupplementaryCZK != 0 {
			key += "_extra"
		}
		v.PreviewLine = lang.t(key, "before", p.Before, "after", p.After, "extra", p.Supplementary)
	}
	v.CanChange = acc.Status == "active" || acc.Status == "overdue"
	v.IsMax = acc.Plan == "max"
	v.HasWhitelabel = acc.AddonWhitelabel
	v.Canceling = acc.Status == "canceling"
	if v.CanChange {
		if v.Upgrade, err = UpgradeFor(ctx, c.pool, owner, acc); err != nil {
			return planView{}, err
		}
		if v.Upgrade != nil {
			v.UpgradePerLine = lang.t("billing.change.upgrade_per_"+acc.BillingInterval, "price", v.Upgrade.Price)
			if v.Upgrade.SavePct > 0 {
				v.SaveLine = lang.t("billing.change.yearly_save", "pct", v.Upgrade.SavePct)
			}
			v.TTLockLine = lang.t("billing.change.ttlock_line", "price", v.Upgrade.TTLockPrice)
		}
		v.TTLockValue = "1"
		v.TTLockButton, v.TTLockLabel = "billing.change.add", "billing.change.ttlock_on"
		if acc.AddonTTLock {
			v.TTLockValue = "0"
			v.TTLockButton, v.TTLockLabel = "billing.change.remove", "billing.change.ttlock_off"
		}
		v.OtherPlan = "standard"
		if acc.Plan != "max" {
			v.OtherPlan = "max"
		}
	}
	v.CancelTip = lang.t("billing.cancel.body", "date", v.PeriodEnd)
	v.CancelConfirm = lang.t("billing.cancel.confirm", "date", v.PeriodEnd)
	list, err := ForOwner(ctx, c.pool, owner)
	if err != nil {
		return planView{}, err
	}
	v.InvoiceColumns = [][]any{{lang.t("billing.invoices.col.number"), ""}, {lang.t("billing.invoices.col.amount"), "r"},
		{lang.t("billing.invoices.col.state"), "r"}}
	for _, inv := range list {
		row := invoiceRow{ID: inv.ID, Number: inv.Number, Date: cut(inv.IssueDate, 10), Amt: Kc(inv.TotalHaler)}
		switch {
		case inv.Voided != 0 || inv.Kind == "storno":
			row.StateKind, row.StateTx = "neutral", lang.t("billing.invoices.state.void")
		case inv.PaidOn != "":
			row.StateKind, row.StateTx = "done", lang.t("billing.invoices.state.paid")
		default:
			row.StateKind, row.StateTx = "action", lang.t("billing.invoices.state.open")
		}
		v.Invoices = append(v.Invoices, row)
	}
	return v, nil
}

// renderPlan is _page: render billing_plan.html with the status pg.Status (200 when 0).
func (c *call) renderPlan(owner int64, pg planPage) {
	view, err := buildPlanView(c, owner, pg)
	if err != nil {
		fail(c.w, err)
		return
	}
	lang := tr(c.lang)
	p := layout.Page{
		Title: lang.t("billing.plan.title") + " · UbyHost", Nav: "settings", BodyKind: "settings",
		V2: true, BackURL: "/settings", Status: pg.Status,
	}
	if err := layout.Render(c.w, c.r, layout.Env{Pool: c.pool, Getenv: c.getenv, Now: c.at}, c.h, p, pages, "billing_plan", view); err != nil {
		fail(c.w, err)
	}
}

// hostPlanPage serves GET /predplatne (plan_page, lines 69-81). The POST of the
// same path is hostPlanOrder (brief 1557).
func (d deps) hostPlanPage(w http.ResponseWriter, r *http.Request) {
	c := d.enter(w, r, gate{open: true})
	if c == nil {
		return
	}
	owner := c.h.Workspace.ID
	if !billingOn(d.getenv) {
		c.back("/settings", hostweb.Flash{}, hostweb.Flash{})
		return
	}
	query := map[string]string{"plan": lastQuery(r, "plan"), "interval": lastQuery(r, "interval")}
	values, err := FormValues(r.Context(), d.pool, owner, query)
	if err != nil {
		fail(w, err)
		return
	}
	c.renderPlan(owner, planPage{Values: values})
}

// lastQuery is request.query_params.get: the last value, "" when missing.
func lastQuery(r *http.Request, key string) string {
	vals := r.URL.Query()[key]
	if len(vals) == 0 {
		return ""
	}
	return vals[len(vals)-1]
}
