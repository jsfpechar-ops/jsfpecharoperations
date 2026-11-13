package layout

import (
	"fmt"
	"html/template"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// Ports of the most-used macros in App/app/templates/_components.html. Not
// ported yet: next_action, housebook_csv_menu, the onboarding_* macros and
// v2_status_pill. page_header has no page_tabs() fallback: pass tabs.

// Progress is the part of a stay's progress dict (reporting.progress) that
// guest_count reads. Expected nil is "not declared".
type Progress struct {
	Expected *int
	Filled   int
	Guests   int // len(progress.guests)
}

// DeadlineCell is reporting.deadline_cell for deadline_badge. CheckIn nil is
// "no check-in date". FiledAt is shown as given (Python prints the stored value).
type DeadlineCell struct {
	State     string // countdown | filed_on_time | filed_late | none
	Level     string
	CheckIn   *time.Time
	FiledAt   time.Time
	LateHours int
	ByHand    bool
}

var (
	uiKinds           = map[string]string{"red": "action", "amber": "action", "blue": "action", "teal": "neutral", "green": "done", "grey": "neutral"}
	uiSubmissionKinds = map[string]string{"red": "action", "amber": "attention", "blue": "action", "teal": "neutral", "green": "done", "grey": "neutral"}
	uiDeadlineKinds   = map[string]string{"overdue": "action", "urgent": "attention", "soon": "attention", "done": "done", "late": "neutral"}
)

func kindOf(m map[string]string, k string) string {
	if v, ok := m[k]; ok {
		return v
	}
	return "neutral"
}

func (c *reqCtx) helpTip(in ...any) (template.HTML, error) {
	a, err := bind("help_tip", []string{"id", "text", "guide_href", "label", "svg"}, in)
	if err != nil {
		return "", err
	}
	svg := a.b("svg", false)
	cls := "help-tip"
	if svg {
		cls += " help-tip-svg"
	}
	label := escText(c.t("help.tip.label"))
	if a.b("label", false) {
		label = escText(c.t("help.tip.label_for", "topic", a.s("label", "")))
	}
	glyph := "?"
	if svg {
		glyph = mustIcon("circle-help", 18)
	}
	id := a.e("id", "")
	more := ""
	if a.b("guide_href", false) {
		ml := escText(c.t("help.tip.more"))
		more = ` <a href="` + a.href("guide_href") + `" aria-label="` + ml + `: ` + escText(truncate(striptags(a.s("text", "")), 50)) + `">` + ml + `</a>`
	}
	return html(`<span class="` + cls + `" data-help-tip><button type="button" class="help-tip-btn" aria-label="` + label + `" aria-expanded="false" aria-controls="` + id + `">` + glyph + `</button><span class="help-tip-body" id="` + id + `" role="tooltip">` + a.e("text", "") + more + `</span></span>`), nil
}

var howAnchors = map[string]string{"dashboard": "overview", "stays": "stays", "stay": "guests", "properties": "setup", "property": "setup", "reports": "reporting", "invoices": "invoices", "stay_fees": "stay_fee", "housebook": "housebook"}

func (c *reqCtx) pageHelp(how any) template.HTML {
	h := pyStr(how)
	anchor, ok := howAnchors[h]
	if !ok {
		anchor = "overview"
	}
	var b strings.Builder
	b.WriteString(`<span class="page-help-wrap"><details class="page-help" data-how="` + escText(h) + `" data-lint-ignore><summary class="page-help-btn" aria-label="` + escText(c.t("how.toggle")) + `"><span class="page-help-dot" aria-hidden="true">?</span></summary><div class="page-help-body"><ol class="page-help-steps">`)
	for n := 1; n <= 3; n++ {
		b.WriteString(`<li>` + escText(c.t(fmt.Sprintf("how.%s.%d", h, n))) + `</li>`)
	}
	b.WriteString(`</ol><a class="page-help-more" href="/guide#` + escText(anchor) + `">` + escText(c.t("how.more")) + `</a></div></details></span>`)
	return html(b.String())
}

func (c *reqCtx) tipLabel(in ...any) (template.HTML, error) {
	a, err := bind("tip_label", []string{"text", "id", "help", "tag"}, in)
	if err != nil {
		return "", err
	}
	tag := a.e("tag", "strong")
	words := rsplit1(a.s("text", ""))
	tip, err := c.helpTip(a.v("id", ""), a.v("help", ""), "", a.v("text", ""))
	if err != nil {
		return "", err
	}
	head := ""
	if len(words) > 1 {
		head = escText(words[0]) + " "
	}
	return html(`<` + tag + ` class="tip-label">` + head + `<span class="tip-nowrap">` + escText(words[len(words)-1]) + string(tip) + `</span></` + tag + `>`), nil
}

func (c *reqCtx) choiceCard(in ...any) (template.HTML, error) {
	a, err := bind("choice_card", []string{"name", "value", "label", "checked", "help_id", "help_text", "type"}, in)
	if err != nil {
		return "", err
	}
	chk := ""
	if a.b("checked", false) {
		chk = " checked"
	}
	label := `<strong>` + a.e("label", "") + `</strong>`
	if a.b("help_text", false) {
		h, err := c.tipLabel(a.v("label", ""), a.v("help_id", ""), a.v("help_text", ""), "strong")
		if err != nil {
			return "", err
		}
		label = string(h)
	}
	extra := ""
	if a.has("caller") {
		extra = `<div class="ui-choice-card-extra">` + a.raw("caller") + `</div>`
	}
	return html(`<div class="ui-choice-card"><label class="ui-choice-card-label"><input type="` + a.e("type", "radio") + `" name="` + a.e("name", "") + `" value="` + a.e("value", "") + `"` + chk + `>` + label + `</label>` + extra + `</div>`), nil
}

func (c *reqCtx) fieldLabel(in ...any) (template.HTML, error) {
	a, err := bind("field_label", []string{"for", "text", "help_text", "optional", "guide_href", "required", "svg"}, in)
	if err != nil {
		return "", err
	}
	req := ""
	if a.b("required", false) {
		req = `<span class="req-star" aria-hidden="true">*</span>`
	}
	tip := ""
	if a.b("help_text", false) {
		h, err := c.helpTip(a.s("for", "")+"-help", a.v("help_text", ""), a.v("guide_href", ""), "", a.v("svg", false))
		if err != nil {
			return "", err
		}
		tip = string(h)
	}
	return html(`<div class="field-label-row"><label for="` + a.e("for", "") + `">` + a.e("text", "") + req + tip + `</label></div>`), nil
}

func (c *reqCtx) subTabs(in ...any) (template.HTML, error) {
	a, err := bind("sub_tabs", []string{"items", "label"}, in)
	if err != nil {
		return "", err
	}
	rows := items(a.v("items", nil))
	if len(rows) == 0 {
		return "", nil
	}
	label := a.e("label", "")
	if !a.b("label", false) {
		label = escText(c.t("host.section_navigation"))
	}
	var b strings.Builder
	b.WriteString(`<nav class="sub-tabs host-local-nav" aria-label="` + label + `" data-sub-tabs>`)
	for _, row := range rows {
		cur := ""
		if truthy(cell(row, 2)) {
			cur = ` aria-current="page"`
		}
		b.WriteString(`<a class="sub-tab" href="` + safeHref(cell(row, 0)) + `"` + cur + `>` + escText(c.t(pyStr(cell(row, 1)))) + `</a>`)
	}
	b.WriteString(`</nav>`)
	return html(b.String()), nil
}

func (c *reqCtx) pageHeader(in ...any) (template.HTML, error) {
	a, err := bind("page_header", []string{"title", "description", "back_url", "back_label", "eyebrow", "actions", "tabs"}, in)
	if err != nil {
		return "", err
	}
	tabs := a.v("tabs", nil)
	cls := "page-header"
	if truthy(tabs) {
		cls += " has-tabs"
	}
	var b strings.Builder
	b.WriteString(`<header class="` + cls + `"><div class="page-header-main">`)
	if a.b("back_url", false) {
		bl := a.e("back_label", "")
		if !a.b("back_label", false) {
			bl = escText(c.t("common.back"))
		}
		b.WriteString(`<a class="back-link" href="` + a.href("back_url") + `"> ` + bl + `</a>`)
	}
	if a.b("eyebrow", false) {
		b.WriteString(`<div class="eyebrow">` + a.e("eyebrow", "") + `</div>`)
	}
	b.WriteString(`<h1>` + a.e("title", "") + `</h1>`)
	if a.b("description", false) {
		b.WriteString(`<p class="lede">` + a.e("description", "") + `</p>`)
	}
	b.WriteString(`</div>`)
	if a.b("actions", false) {
		b.WriteString(`<div class="page-actions">` + a.raw("actions") + `</div>`)
	}
	b.WriteString(`</header>`)
	st, err := c.subTabs(tabs)
	if err != nil {
		return "", err
	}
	b.WriteString(string(st))
	return html(b.String()), nil
}

func (c *reqCtx) progressPill(in ...any) (template.HTML, error) {
	a, err := bind("progress_pill", []string{"status", "automation_mode", "compact", "is_demo", "step"}, in)
	if err != nil {
		return "", err
	}
	status := a.s("status", "")
	mode := ""
	if m := a.v("automation_mode", nil); m != nil {
		mode = pyStr(m)
	}
	labels := map[string]string{
		"failed": "status.failed", "reported": "status.reported", "ready": "status.ready",
		"incomplete": "status.incomplete", "not_required": "status.not_required",
		"awaiting_guest": "status.awaiting_guest_short", "awaiting_verification": "status.awaiting_verification",
	}
	tones := map[string]string{
		"failed": "red", "reported": "green", "ready": "blue", "incomplete": "amber",
		"not_required": "grey", "awaiting_guest": "teal", "awaiting_verification": "blue",
	}
	tone, ok := tones[status]
	if !ok {
		tone = "grey"
	}
	readyish := status == "ready" || status == "awaiting_verification"
	var label, tip string
	switch {
	case a.b("is_demo", false) && readyish:
		label, tip, tone = c.t("status.demo_preview"), c.t("status.demo_preview_tip"), "grey"
	case mode == "immediate" && (status == "awaiting_guest" || status == "incomplete"):
		label, tip, tone = c.t("status.waiting_guest"), c.t("status.waiting_guest_tip"), "teal"
	case readyish && mode == "immediate":
		label, tip, tone = c.t("status.ready_immediate"), c.t("status.ready_immediate_tip"), "blue"
	case readyish && mode == "scheduled":
		label, tip, tone = c.t("status.ready_scheduled"), c.t("status.ready_scheduled_tip"), "blue"
	case status == "awaiting_verification":
		label, tip = c.t("status.awaiting_verification"), c.t("status.awaiting_verification_tip")
	case status == "ready" && mode == "manual":
		label, tip = c.t("status.ready_manual"), c.t("status.ready_manual_tip")
	default:
		if key, ok := labels[status]; ok {
			label = c.t(key)
		} else {
			label = status
		}
	}
	over := ""
	if tone == "red" {
		over = " ui-badge-overdue"
	}
	title := ""
	if tip != "" {
		title = ` title="` + escText(tip) + `"`
	}
	step := ""
	if a.b("step", false) {
		step = `<span class="ui-badge-step" data-journey-step="` + a.e("step", "") + `">` + escText(c.t("workflow.step_of", "n", a.v("step", nil), "total", 5)) + ` · </span>`
	}
	return html(`<span class="ui-badge ui-badge-` + kindOf(uiKinds, tone) + over + `" data-tone="` + tone + `"` + title + `>` + step + escText(label) + `</span>`), nil
}

func (c *reqCtx) guestCount(progress Progress, rest ...any) (template.HTML, error) {
	a, err := bind("guest_count", []string{"placeholder"}, rest)
	if err != nil {
		return "", err
	}
	label := escText(c.t("stays.table.guests"))
	if progress.Expected != nil || progress.Guests > 0 {
		var n string
		if progress.Expected != nil {
			n = escText(c.t("stays.table.guests_of", "filled", progress.Filled, "expected", *progress.Expected))
		} else {
			n = fmt.Sprint(progress.Guests)
		}
		return html(`<span class="guest-count" title="` + label + `">` + mustIcon("users", 16) + `<span class="sr-only">` + label + `:</span> ` + n + `</span>`), nil
	}
	if a.b("placeholder", false) {
		return html(`<span class="muted" aria-hidden="true">–</span><span class="sr-only">` + escText(c.t("common.guests_unknown")) + `</span>`), nil
	}
	return "", nil
}

func (c *reqCtx) bulkSendReady(count, returnTo any) template.HTML {
	dis := ""
	n := ""
	if !truthy(count) {
		dis = " disabled"
	} else {
		n = " (" + esc(count) + ")"
	}
	return html(`<form method="post" action="/reservations/submit-ready" class="inline send-all-form"><input type="hidden" name="return_to" value="` + esc(returnTo) + `"><button class="ui-btn ui-btn-secondary send-all" type="submit"` + dis + ` title="` + escText(c.t("send.all_ready_hint")) + `">` + mustIcon("send", 16) + `<span>` + escText(c.t("send.all_ready")) + n + `</span></button></form>`)
}

func (c *reqCtx) syncCalendarsButton(in ...any) (template.HTML, error) {
	a, err := bind("sync_calendars_button", []string{"return_to", "last_sync", "label_key", "primary"}, in)
	if err != nil {
		return "", err
	}
	meta := a.b("last_sync", false)
	cls := "sync-cta"
	if meta {
		cls += " has-meta"
	}
	variant := "secondary"
	if a.b("primary", false) {
		variant = "primary"
	}
	var b strings.Builder
	b.WriteString(`<div class="` + cls + `"><form method="post" action="/sync" class="sync-cta-form"><input type="hidden" name="return_to" value="` + a.e("return_to", "/") + `"><button class="ui-btn ui-btn-` + variant + ` sync-btn" type="submit">` + mustIcon("refresh-cw", 16) + `<span>` + escText(c.t(a.s("label_key", "dashboard.sync_calendars"))) + `</span></button></form>`)
	if meta {
		b.WriteString(`<p class="small muted sync-cta-meta">` + escText(c.t("dashboard.last_synced", "when", datetimeLocal(a.v("last_sync", nil)))) + `</p>`)
	}
	b.WriteString(`</div>`)
	return html(b.String()), nil
}

var navIcons = map[string]string{
	"overview":   `<rect x="2.5" y="2.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/><rect x="11.5" y="2.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/><rect x="2.5" y="11.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/><rect x="11.5" y="11.5" width="6" height="6" rx="1.5" stroke="currentColor" stroke-width="1.5"/>`,
	"calendar":   `<rect x="3" y="4.5" width="14" height="12.5" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M3 8.5h14M7 2.5v3M13 2.5v3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"report":     `<path d="M5.5 3.5h6l3.5 3.5v9.5a1 1 0 0 1-1 1h-8.5a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.5"/><path d="M11.5 3.5v4h4M7.5 11h5M7.5 14h3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"book":       `<rect x="4.5" y="3.5" width="11" height="13" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M8 3.5v13" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 8h4M10.5 11h3M10.5 14h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"property":   `<path d="M3.5 9 10 3.5 16.5 9V16a1 1 0 0 1-1 1H4.5a1 1 0 0 1-1-1V9Z" stroke="currentColor" stroke-width="1.5"/><path d="M8 17v-5h4v5" stroke="currentColor" stroke-width="1.5"/>`,
	"entity":     `<rect x="3.5" y="5.5" width="13" height="11" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M7 5.5V4.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M7.5 10h5M7.5 13h3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"automation": `<path d="M4 7.5A6.5 6.5 0 0 1 15.2 5L17 7M16 12.5A6.5 6.5 0 0 1 4.8 15L3 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M17 3v4h-4M3 17v-4h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
	"lock":       `<rect x="4" y="8.5" width="12" height="9" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M7 8.5V6a3 3 0 0 1 6 0v2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="10" cy="13" r="1.2" fill="currentColor"/>`,
	"link":       `<path d="m8 12 4-4M6.5 13.5l-1 1a2.8 2.8 0 0 1-4-4l2.3-2.3a2.8 2.8 0 0 1 4 0M13.5 6.5l1-1a2.8 2.8 0 1 1 4 4l-2.3 2.3a2.8 2.8 0 0 1-4 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"settings":   `<circle cx="10" cy="10" r="2.5" stroke="currentColor" stroke-width="1.5"/><path d="M10 3.5v1.6M10 14.9v1.6M4.2 6.2l1.1 1.1M14.7 14.7l1.1 1.1M3.5 10h1.6M14.9 10h1.6M4.2 13.8l1.1-1.1M14.7 5.3l1.1-1.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"users":      `<circle cx="10" cy="7" r="2.75" stroke="currentColor" stroke-width="1.5"/><path d="M4.5 16.5c0-2.8 2.2-4.5 5.5-4.5s5.5 1.7 5.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"guide":      `<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M10 13.5v.5M10 7.5a2 2 0 1 1 1.2 3.6c-.7.4-1.2 1-1.2 1.9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"invoice":    `<path d="M5 2.5h10v15l-2.5-1.5-2.5 1.5-2.5-1.5L5 17.5v-15Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.5 7h5M7.5 10h5M7.5 13h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
	"coins":      `<circle cx="8" cy="8.5" r="4.75" stroke="currentColor" stroke-width="1.5"/><path d="M11.6 6.1a4.75 4.75 0 1 1-2.1 9.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
}

// navIcon is nav_icon(name); an unknown name renders nothing, as in Jinja.
func navIcon(name any) template.HTML {
	p, ok := navIcons[pyStr(name)]
	if !ok {
		return ""
	}
	return html(`<svg class="nav-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">` + p + `</svg>`)
}

func (c *reqCtx) csvActionsMenu(in ...any) (template.HTML, error) {
	a, err := bind("csv_actions_menu", []string{"export_params", "compact", "scope_label"}, in)
	if err != nil {
		return "", err
	}
	cls := "ui-btn ui-btn-quiet"
	if a.b("compact", false) {
		cls += " ui-btn-compact csv-in-filter"
	}
	return html(`<button class="` + cls + `" type="button" data-csv-export="/reservations.csv" data-csv-params="` + a.e("export_params", "") + `" data-csv-scope-label="` + a.e("scope_label", "") + `">` + escText(c.t("csv.export_stays")) + `</button>`), nil
}

func (c *reqCtx) submissionPill(state any) template.HTML {
	s := pyStr(state)
	labels := map[string]string{
		"ok": "submission.accepted", "ok_duplicate": "submission.duplicate", "partial": "submission.partial",
		"error": "submission.rejected", "failed": "submission.rejected", "transport_error": "submission.not_delivered",
		"outcome_unknown": "submission.outcome_unknown", "not_configured": "submission.setup_incomplete",
		"running": "submission.in_progress", "noop": "submission.nothing_to_send",
	}
	tones := map[string]string{
		"ok": "green", "ok_duplicate": "green", "partial": "amber", "error": "red", "failed": "red",
		"transport_error": "red", "outcome_unknown": "red", "not_configured": "amber", "running": "teal", "noop": "grey",
	}
	tone, ok := tones[s]
	if !ok {
		tone = "red"
	}
	label := s
	if key, ok := labels[s]; ok {
		label = c.t(key)
	}
	over := ""
	if tone == "red" {
		over = " ui-badge-overdue"
	}
	return html(`<span class="ui-badge ui-badge-` + kindOf(uiSubmissionKinds, tone) + over + `" data-tone="` + tone + `">` + escText(label) + `</span>`)
}

// describeTimeLeft is templating._template_time_left.
func (c *reqCtx) describeTimeLeft(checkIn time.Time) string {
	kind, amount := deadlines.TimeLeftParts(checkIn, deadlines.LocalNow(c.now))
	key := "deadline." + kind
	if kind == "arrives_days" || kind == "days_left" || kind == "overdue_days" {
		key = pluralKey(key, amount)
	}
	return c.t(key, "n", amount)
}

func (c *reqCtx) deadlineBadge(cl DeadlineCell, rest ...any) (template.HTML, error) {
	a, err := bind("deadline_badge", []string{"tag", "extra_class"}, rest)
	if err != nil {
		return "", err
	}
	tag := a.e("tag", "span")
	classes := ""
	if a.b("extra_class", false) {
		classes = " " + a.e("extra_class", "")
	}
	when := cl.FiledAt.Format("02.01. 15:04")
	open := func(cls, data, extra string) string {
		return `<` + tag + ` class="ui-badge ` + cls + classes + `" data-deadline="` + escText(data) + `"` + extra + `>`
	}
	closeTag := `</` + tag + `>`
	filed := cl.State == "filed_on_time" || cl.State == "filed_late"
	switch {
	case cl.ByHand && filed:
		return html(open("ui-badge-"+kindOf(uiDeadlineKinds, cl.Level), cl.Level, "") + escText(c.t("deadline.filed_by_hand", "when", when)) + closeTag), nil
	case cl.State == "filed_on_time":
		return html(open("ui-badge-done", "done", "") + escText(c.t("deadline.filed_at", "when", when)) + closeTag), nil
	case cl.State == "filed_late":
		text := c.t("deadline.filed_late_hours", "n", cl.LateHours)
		if cl.LateHours >= 48 {
			text = c.tp("deadline.filed_late_days", cl.LateHours/24)
		}
		return html(open("ui-badge-neutral", "neutral", ` title="`+escText(c.t("deadline.filed_at", "when", when))+`"`) + escText(text) + closeTag), nil
	case cl.State == "countdown":
		over := ""
		if cl.Level == "overdue" {
			over = " ui-badge-overdue"
		}
		text := "—"
		if cl.CheckIn != nil {
			text = c.describeTimeLeft(*cl.CheckIn)
		}
		return html(`<` + tag + ` class="ui-badge ui-badge-` + kindOf(uiDeadlineKinds, cl.Level) + over + classes + `" data-deadline="` + escText(cl.Level) + `">` + escText(text) + closeTag), nil
	}
	return "", nil
}

func (c *reqCtx) emptyState(in ...any) (template.HTML, error) {
	a, err := bind("empty_state", []string{"title", "body", "action_url", "action_label", "primary"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`<div class="ui-empty" data-empty-state>`)
	if a.b("title", false) {
		b.WriteString(`<h2>` + a.e("title", "") + `</h2>`)
	}
	if a.b("body", false) {
		b.WriteString(`<p>` + a.e("body", "") + `</p>`)
	}
	if a.b("action_url", false) {
		variant := "secondary"
		if a.b("primary", true) {
			variant = "primary"
		}
		b.WriteString(`<div class="ui-btn-group"><a class="ui-btn ui-btn-` + variant + `" href="` + a.href("action_url") + `">` + a.e("action_label", "") + `</a></div>`)
	}
	b.WriteString(a.raw("caller") + `</div>`)
	return html(b.String()), nil
}

func propertyIdentity(in ...any) (template.HTML, error) {
	a, err := bind("property_identity", []string{"id", "name", "compact", "truncate"}, in)
	if err != nil {
		return "", err
	}
	trunc := a.b("truncate", false)
	cls, title, nameCls := "property-identity", "", ""
	if trunc {
		cls += " truncate"
		title = ` title="` + a.e("name", "") + `"`
	}
	if a.b("compact", false) {
		nameCls = "small"
	}
	if trunc {
		nameCls += " property-identity-name"
	}
	return html(fmt.Sprintf(`<span class="%s"%s><span class="ui-pdot" data-property="%d" aria-hidden="true"></span> <span class="%s">%s</span></span>`,
		cls, title, pyMod(toInt(a.v("id", 0)), 4)+1, nameCls, a.e("name", ""))), nil
}

func (c *reqCtx) successNotice(in ...any) (template.HTML, error) {
	a, err := bind("success_notice", []string{"text", "next_href", "next_label"}, in)
	if err != nil {
		return "", err
	}
	next := ""
	if a.b("next_href", false) && a.b("next_label", false) {
		next = `<a class="success-notice-next" href="` + a.href("next_href") + `">` + a.e("next_label", "") + `</a>`
	}
	return html(`<div class="success-notice" role="status" data-success-notice><span class="success-notice-text">` + a.e("text", "") + `</span>` + next + `<button type="button" class="success-notice-close" data-success-dismiss aria-label="` + escText(c.t("a11y.dismiss_notification")) + `">` + mustIcon("x", 16) + `</button></div>`), nil
}

func copyIcon() template.HTML {
	return html(`<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.4"/><path d="M4.5 10.5H3.5a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1H9.5a1 1 0 0 1 1 1V4.5" stroke="currentColor" stroke-width="1.4"/></svg>`)
}

func (c *reqCtx) copyButton(in ...any) (template.HTML, error) {
	a, err := bind("copy_button", []string{"target_id", "label", "primary"}, in)
	if err != nil {
		return "", err
	}
	label := a.e("label", "")
	if !a.b("label", false) {
		label = escText(c.t("common.copy"))
	}
	copied := escText(c.t("common.copied"))
	target := a.e("target_id", "")
	if c.v2 {
		ghost := ""
		if !a.b("primary", false) {
			ghost = " ghost"
		}
		return html(`<button class="btn sm` + ghost + ` copy-btn" type="button" data-copy="` + target + `" data-copy-label="` + label + `" data-copied-label="` + copied + `" aria-label="` + label + `">` + mustIcon("copy", 18) + `<span class="copy-label-default">` + label + `</span><span class="btn-icon-label" data-copy-label-slot></span></button>`), nil
	}
	return html(`<button class="ui-btn ui-btn-secondary ui-btn-icon ui-btn-compact copy-btn" type="button" data-copy="` + target + `" data-copy-label="` + label + `" data-copied-label="` + copied + `" aria-label="` + label + `">` + mustIcon("copy", 16) + `<span class="btn-icon-label" data-copy-label-slot hidden></span><span class="sr-only">` + label + `</span></button>`), nil
}

func (c *reqCtx) copyInline(in ...any) (template.HTML, error) {
	a, err := bind("copy_inline", []string{"target_id", "value", "label", "role"}, in)
	if err != nil {
		return "", err
	}
	label := a.e("label", "")
	if !a.b("label", false) {
		label = escText(c.t("common.copy_link"))
	}
	cls, role := "btn small", ""
	if a.b("role", false) {
		cls = "row-menu-item"
		role = ` role="` + a.e("role", "") + `"`
	}
	target := a.e("target_id", "")
	return html(`<input class="sr-only" type="text" id="` + target + `" readonly value="` + a.e("value", "") + `" tabindex="-1" aria-hidden="true"> <button class="` + cls + `" type="button" data-copy="` + target + `" data-copy-label="` + label + `" data-copied-label="` + escText(c.t("common.copied")) + `"` + role + ` title="` + escText(c.t("common.copy_guest_link")) + `">` + label + `</button>`), nil
}

func (c *reqCtx) rowMenuBegin(in ...any) (template.HTML, error) {
	a, err := bind("row_menu_begin", []string{"label"}, in)
	if err != nil {
		return "", err
	}
	label := a.e("label", "")
	if !a.b("label", false) {
		label = escText(c.t("common.more_actions"))
	}
	return html(`<div class="row-menu ui-menu"><button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact row-menu-trigger" type="button" aria-label="` + label + `" aria-expanded="false" aria-haspopup="true">` + mustIcon("ellipsis-vertical", 16) + `</button><div class="row-menu-panel ui-menu-panel" role="menu" hidden>`), nil
}

func rowMenuEnd() template.HTML { return html(`</div></div>`) }

func (c *reqCtx) rowOpen(href any) template.HTML {
	return html(`<a class="row-open" href="` + safeHref(href) + `" tabindex="-1" aria-hidden="true"><span class="row-open-text">` + escText(c.t("common.open")) + `</span></a>`)
}

// platformLogos is templating._PLATFORM_LOGO_KEYS for the files in
// App/app/static/platforms/ today. Add a line when a logo file is added there.
var platformLogos = map[string]string{"airbnb": "airbnb.svg", "booking": "booking.svg", "echalupy": "echalupy.svg"}

// sourceMark is templating.source_mark.
func sourceMark(key any) template.HTML {
	k := strings.ToLower(strings.TrimSpace(pyStr(key)))
	if key == nil {
		k = ""
	}
	file, ok := platformLogos[k]
	if !ok {
		return ""
	}
	return html(`<img src="/static/platforms/` + file + `" alt="" aria-hidden="true" width="16" height="16" loading="lazy">`)
}

func sourceBadge(key, label any) template.HTML {
	return html(`<span class="source-badge">` + string(sourceMark(key)) + esc(label) + `</span>`)
}

func settingsGroup(in ...any) (template.HTML, error) {
	a, err := bind("settings_group", []string{"key", "title"}, in)
	if err != nil {
		return "", err
	}
	k := a.e("key", "")
	return html(`<section class="settings-group" id="settings-group-` + k + `" aria-labelledby="settings-group-` + k + `-title"><h2 class="settings-group-title sec" id="settings-group-` + k + `-title">` + a.e("title", "") + `</h2><div class="card settings-card">` + a.raw("caller") + `</div></section>`), nil
}

func (c *reqCtx) settingsHeading(in ...any) (template.HTML, error) {
	a, err := bind("settings_heading", []string{"key", "title", "help_text", "guide_href"}, in)
	if err != nil {
		return "", err
	}
	tip := ""
	if a.b("help_text", false) {
		h, err := c.helpTip("settings-"+a.s("key", "")+"-help", a.v("help_text", ""), a.v("guide_href", ""), a.v("title", ""))
		if err != nil {
			return "", err
		}
		tip = string(h)
	}
	return html(`<div class="settings-heading"><h3>` + a.e("title", "") + `</h3>` + tip + `</div>`), nil
}
