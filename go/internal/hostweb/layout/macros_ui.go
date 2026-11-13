package layout

import (
	"fmt"
	"html/template"
	"strings"
)

// Ports of App/app/templates/_icons.html, _ui.html and _ui_layout.html. Each
// func keeps the macro's name and parameters; see args.go for how a call binds.

// icon is _icons.html icon(name, size=20, cls=”). An unknown name is an error,
// as the Jinja macro raises.
func icon(name string, rest ...any) (template.HTML, error) {
	a, err := bind("icon", []string{"size", "cls"}, rest)
	if err != nil {
		return "", err
	}
	paths, ok := iconPaths[name]
	if !ok {
		return "", fmt.Errorf("icon: unknown icon %q", name)
	}
	size := 20
	if a.has("size") {
		size = toInt(a.v("size", 20))
	}
	stroke := "1.75"
	if size <= 16 {
		stroke = "2"
	}
	cls := ""
	if a.b("cls", false) {
		cls = " " + a.e("cls", "")
	}
	return html(fmt.Sprintf(`<svg class="ui-icon%s" width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false" data-icon="%s">%s</svg>`,
		cls, size, size, stroke, escText(name), paths)), nil
}

func mustIcon(name string, size int) string {
	h, err := icon(name, size)
	if err != nil {
		panic(err)
	}
	return string(h)
}

func attrsPart(a args) string {
	if a.b("attrs", false) {
		return " " + a.raw("attrs")
	}
	return ""
}

func (c *reqCtx) uiButton(in ...any) (template.HTML, error) {
	a, err := bind("ui_button", []string{"label", "variant", "href", "type", "size", "icon_name", "loading", "disabled", "attrs", "id"}, in)
	if err != nil {
		return "", err
	}
	classes := "ui-btn ui-btn-" + a.e("variant", "secondary")
	if a.s("size", "regular") == "compact" {
		classes += " ui-btn-compact"
	}
	loading := a.b("loading", false)
	if loading {
		classes += " ui-btn-loading"
	}
	var b strings.Builder
	ic := ""
	if a.b("icon_name", false) {
		h, err := icon(a.s("icon_name", ""), 16)
		if err != nil {
			return "", err
		}
		ic = string(h)
	}
	id := ""
	if a.b("id", false) {
		id = ` id="` + a.e("id", "") + `"`
	}
	if a.b("href", false) {
		b.WriteString(`<a class="` + classes + `" href="` + a.href("href") + `"` + id)
		if a.b("disabled", false) {
			b.WriteString(` aria-disabled="true" tabindex="-1"`)
		}
		if loading {
			b.WriteString(` aria-busy="true"`)
		}
		b.WriteString(attrsPart(a) + ">" + ic + "<span>" + a.e("label", "") + "</span></a>")
	} else {
		b.WriteString(`<button class="` + classes + `" type="` + a.e("type", "button") + `"` + id)
		if a.b("disabled", false) {
			b.WriteString(` disabled`)
		}
		if loading {
			b.WriteString(` aria-busy="true"`)
		}
		b.WriteString(attrsPart(a) + ">" + ic + "<span>" + a.e("label", "") + "</span></button>")
	}
	return html(b.String()), nil
}

func (c *reqCtx) uiIconButton(in ...any) (template.HTML, error) {
	a, err := bind("ui_icon_button", []string{"label", "icon_name", "variant", "href", "type", "size", "attrs", "extra_class"}, in)
	if err != nil {
		return "", err
	}
	classes := "ui-btn ui-btn-" + a.e("variant", "quiet") + " ui-btn-icon"
	if a.s("size", "regular") == "compact" {
		classes += " ui-btn-compact"
	}
	if a.b("extra_class", false) {
		classes += " " + a.e("extra_class", "")
	}
	ic, err := icon(a.s("icon_name", ""), 16)
	if err != nil {
		return "", err
	}
	label := a.e("label", "")
	if a.b("href", false) {
		return html(`<a class="` + classes + `" href="` + a.href("href") + `" aria-label="` + label + `" title="` + label + `"` + attrsPart(a) + ">" + string(ic) + "</a>"), nil
	}
	return html(`<button class="` + classes + `" type="` + a.e("type", "button") + `" aria-label="` + label + `" title="` + label + `"` + attrsPart(a) + ">" + string(ic) + "</button>"), nil
}

func (c *reqCtx) uiBadge(in ...any) (template.HTML, error) {
	a, err := bind("ui_badge", []string{"kind", "label", "overdue"}, in)
	if err != nil {
		return "", err
	}
	over := ""
	if a.b("overdue", false) {
		over = " ui-badge-overdue"
	}
	return html(`<span class="ui-badge ui-badge-` + a.e("kind", "") + over + `">` + a.e("label", "") + `</span>`), nil
}

func (c *reqCtx) uiChip(in ...any) (template.HTML, error) {
	a, err := bind("ui_chip", []string{"label", "href", "selected", "remove_href", "attrs"}, in)
	if err != nil {
		return "", err
	}
	if a.b("href", false) {
		sel := ""
		if a.b("selected", false) {
			sel = ` aria-current="true"`
		}
		return html(`<a class="ui-chip" href="` + a.href("href") + `"` + sel + attrsPart(a) + `>` + a.e("label", "") + `</a>`), nil
	}
	pressed := "false"
	if a.b("selected", false) {
		pressed = "true"
	}
	return html(`<button class="ui-chip" type="button" aria-pressed="` + pressed + `"` + attrsPart(a) + `>` + a.e("label", "") + `</button>`), nil
}

// fieldHead is the shared label and describedby logic of ui_field, ui_select and ui_textarea.
func (c *reqCtx) fieldOpen(a args) string {
	cls := "ui-field"
	if a.b("error", false) {
		cls += " ui-field-err"
	}
	opt := ""
	if a.b("optional", false) {
		opt = ` <span class="ui-opt">` + escText(c.t("common.optional")) + `</span>`
	}
	return `<div class="` + cls + `"><label class="ui-label" for="` + a.e("id", "") + `">` + a.e("label", "") + opt + `</label>`
}

func describedBy(a args) string {
	id := a.e("id", "")
	if a.b("error", false) {
		return ` aria-invalid="true" aria-describedby="` + id + `-error"`
	}
	if a.b("help", false) {
		return ` aria-describedby="` + id + `-help"`
	}
	return ""
}

func fieldClose(a args) string {
	id := a.e("id", "")
	tail := ""
	if a.b("error", false) {
		tail = `<span class="ui-error" id="` + id + `-error">` + mustIcon("triangle-alert", 16) + a.e("error", "") + `</span>`
	} else if a.b("help", false) {
		tail = `<span class="ui-help" id="` + id + `-help">` + a.e("help", "") + `</span>`
	}
	return tail + `</div>`
}

func nameOrID(a args) string {
	if a.b("name", false) {
		return a.e("name", "")
	}
	return a.e("id", "")
}

func (c *reqCtx) uiField(in ...any) (template.HTML, error) {
	a, err := bind("ui_field", []string{"id", "label", "name", "value", "type", "help", "error", "optional", "attrs", "placeholder"}, in)
	if err != nil {
		return "", err
	}
	ph := ""
	if a.b("placeholder", false) {
		ph = ` placeholder="` + a.e("placeholder", "") + `"`
	}
	return html(c.fieldOpen(a) + `<input class="ui-input" id="` + a.e("id", "") + `" name="` + nameOrID(a) + `" type="` + a.e("type", "text") + `" value="` + a.e("value", "") + `"` + ph + describedBy(a) + ` ` + a.raw("attrs") + `>` + fieldClose(a)), nil
}

func (c *reqCtx) uiSelect(in ...any) (template.HTML, error) {
	a, err := bind("ui_select", []string{"id", "label", "options", "selected", "name", "help", "error", "optional", "attrs"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(c.fieldOpen(a) + `<select class="ui-select" id="` + a.e("id", "") + `" name="` + nameOrID(a) + `"` + describedBy(a) + ` ` + a.raw("attrs") + `>`)
	selected := a.s("selected", "")
	for _, row := range items(a.v("options", nil)) {
		value := cell(row, 0)
		sel := ""
		if pyStr(value) == selected {
			sel = " selected"
		}
		b.WriteString(`<option value="` + esc(value) + `"` + sel + `>` + esc(cell(row, 1)) + `</option>`)
	}
	b.WriteString(`</select>` + fieldClose(a))
	return html(b.String()), nil
}

func (c *reqCtx) uiTextarea(in ...any) (template.HTML, error) {
	a, err := bind("ui_textarea", []string{"id", "label", "value", "name", "help", "error", "optional", "rows", "attrs", "placeholder"}, in)
	if err != nil {
		return "", err
	}
	ph := ""
	if a.b("placeholder", false) {
		ph = ` placeholder="` + a.e("placeholder", "") + `"`
	}
	return html(c.fieldOpen(a) + `<textarea class="ui-textarea" id="` + a.e("id", "") + `" name="` + nameOrID(a) + `" rows="` + a.e("rows", "3") + `"` + ph + describedBy(a) + ` ` + a.raw("attrs") + `>` + a.e("value", "") + `</textarea>` + fieldClose(a)), nil
}

func (c *reqCtx) uiCheck(in ...any) (template.HTML, error) {
	a, err := bind("ui_check", []string{"id", "label", "name", "checked", "value", "attrs"}, in)
	if err != nil {
		return "", err
	}
	chk := ""
	if a.b("checked", false) {
		chk = " checked"
	}
	return html(`<label class="ui-check" for="` + a.e("id", "") + `"><input class="ui-input" type="checkbox" id="` + a.e("id", "") + `" name="` + nameOrID(a) + `" value="` + a.e("value", "1") + `"` + chk + ` ` + a.raw("attrs") + `><span>` + a.e("label", "") + `</span></label>`), nil
}

func (c *reqCtx) uiToggle(in ...any) (template.HTML, error) {
	a, err := bind("ui_toggle", []string{"id", "label", "name", "checked", "attrs"}, in)
	if err != nil {
		return "", err
	}
	chk := ""
	if a.b("checked", false) {
		chk = " checked"
	}
	return html(`<label class="ui-toggle" for="` + a.e("id", "") + `"><span>` + a.e("label", "") + `</span><input class="ui-input ui-switch" type="checkbox" role="switch" id="` + a.e("id", "") + `" name="` + nameOrID(a) + `" value="1"` + chk + ` ` + a.raw("attrs") + `></label>`), nil
}

func (c *reqCtx) uiMenuBegin(in ...any) (template.HTML, error) {
	a, err := bind("ui_menu_begin", []string{"label"}, in)
	if err != nil {
		return "", err
	}
	label := a.e("label", "")
	if !a.b("label", false) {
		label = escText(c.t("common.actions"))
	}
	return html(`<span class="ui-menu row-menu" data-row-menu><button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact row-menu-trigger" type="button" aria-haspopup="menu" aria-expanded="false" aria-label="` + label + `" title="` + label + `">` + mustIcon("ellipsis-vertical", 16) + `</button><span class="ui-menu-panel row-menu-panel" role="menu" hidden>`), nil
}

func uiMenuEnd() template.HTML { return html(`</span></span>`) }

func (c *reqCtx) uiMenuItem(in ...any) (template.HTML, error) {
	a, err := bind("ui_menu_item", []string{"label", "href", "danger", "icon_name", "attrs"}, in)
	if err != nil {
		return "", err
	}
	cls := "ui-menu-item"
	if a.b("danger", false) {
		cls += " ui-menu-danger"
	}
	ic := ""
	if a.b("icon_name", false) {
		h, err := icon(a.s("icon_name", ""), 16)
		if err != nil {
			return "", err
		}
		ic = string(h)
	}
	if a.b("href", false) {
		return html(`<a class="` + cls + `" role="menuitem" href="` + a.href("href") + `"` + attrsPart(a) + `>` + ic + a.e("label", "") + `</a>`), nil
	}
	return html(`<button class="` + cls + `" role="menuitem" type="submit"` + attrsPart(a) + `>` + ic + a.e("label", "") + `</button>`), nil
}

func uiDialogBegin(id, title any) template.HTML {
	i := esc(id)
	return html(`<dialog id="` + i + `" class="ui-dialog" aria-labelledby="` + i + `-title"><div class="ui-sheet"><span class="ui-sheet-handle" aria-hidden="true"></span><h2 id="` + i + `-title">` + esc(title) + `</h2>`)
}

func uiDialogEnd() template.HTML { return html(`</div></dialog>`) }

func (c *reqCtx) uiEmpty(in ...any) (template.HTML, error) {
	a, err := bind("ui_empty", []string{"title", "body", "action_label", "action_href", "primary", "tip"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`<div class="ui-empty" data-empty-state><h2>` + a.e("title", "") + a.e("tip", "") + `</h2>`)
	if a.b("body", false) {
		b.WriteString(`<p>` + a.e("body", "") + `</p>`)
	}
	if a.b("action_href", false) {
		variant := "secondary"
		if a.b("primary", true) {
			variant = "primary"
		}
		btn, err := c.uiButton(a.v("action_label", ""), variant, map[string]any{"href": a.v("action_href", "")})
		if err != nil {
			return "", err
		}
		b.WriteString(string(btn))
	}
	if a.has("caller") {
		b.WriteString(a.raw("caller"))
	}
	b.WriteString(`</div>`)
	return html(b.String()), nil
}

func (c *reqCtx) uiTip(in ...any) (template.HTML, error) {
	a, err := bind("ui_tip", []string{"id", "text", "href"}, in)
	if err != nil {
		return "", err
	}
	id := a.e("id", "")
	more := ""
	if a.b("href", false) {
		moreLabel := escText(c.t("help.tip.more"))
		more = ` <a href="` + a.href("href") + `" aria-label="` + moreLabel + `: ` + escText(truncate(striptags(a.s("text", "")), 50)) + `">` + moreLabel + `</a>`
	}
	return html(`<span class="ui-tip help-tip" data-help-tip><button type="button" class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact help-tip-btn" aria-label="` + escText(c.t("help.tip.label")) + `" aria-expanded="false" aria-controls="` + id + `">` + mustIcon("circle-help", 16) + `</button><span class="help-tip-body" id="` + id + `" role="tooltip">` + a.e("text", "") + more + `</span></span>`), nil
}

func (c *reqCtx) uiPagination(in ...any) (template.HTML, error) {
	a, err := bind("ui_pagination", []string{"page", "pages", "prev_url", "next_url", "label", "more_label", "prev_label", "next_label", "page_label"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`<nav class="ui-pagination" aria-label="` + a.e("label", "") + `">`)
	btn := func(args ...any) {
		h, e := c.uiButton(args...)
		if e != nil && err == nil {
			err = e
		}
		b.WriteString(string(h))
	}
	if a.b("next_url", false) {
		btn(a.v("more_label", ""), "secondary", map[string]any{"href": a.v("next_url", ""), "attrs": html("data-pagination-more")})
	}
	pageLabel := a.e("page_label", "")
	if !a.b("page_label", false) {
		pageLabel = escText(a.s("page", "") + " / " + a.s("pages", ""))
	}
	b.WriteString(`<span class="ui-num">` + pageLabel + `</span>`)
	if a.b("prev_url", false) {
		btn(a.v("prev_label", ""), "secondary", map[string]any{"href": a.v("prev_url", ""), "size": "compact"})
	} else {
		btn(a.v("prev_label", ""), "secondary", map[string]any{"size": "compact", "disabled": true})
	}
	if a.b("next_url", false) {
		btn(a.v("next_label", ""), "secondary", map[string]any{"href": a.v("next_url", ""), "size": "compact"})
	} else {
		btn(a.v("next_label", ""), "secondary", map[string]any{"size": "compact", "disabled": true})
	}
	b.WriteString(`</nav>`)
	return html(b.String()), err
}

func uiPdot(index, name any) template.HTML {
	return html(fmt.Sprintf(`<span class="ui-pdot" data-property="%d">%s</span>`, pyMod(toInt(index), 4)+1, esc(name)))
}

// --- _ui_layout.html ---

func (c *reqCtx) uiTabs(in ...any) (template.HTML, error) {
	a, err := bind("ui_tabs", []string{"items", "label"}, in)
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
	b.WriteString(`<nav class="ui-tabs" data-sub-tabs aria-label="` + label + `">`)
	for _, row := range rows {
		cur := ""
		if truthy(cell(row, 2)) {
			cur = ` aria-current="page"`
		}
		b.WriteString(`<a class="ui-tab" href="` + safeHref(cell(row, 0)) + `"` + cur + `>` + esc(cell(row, 1)) + `</a>`)
	}
	b.WriteString(`</nav>`)
	return html(b.String()), nil
}

func (c *reqCtx) uiToolbar(in ...any) (template.HTML, error) {
	a, err := bind("ui_toolbar", []string{"search", "chips", "filters_id", "filters_count", "actions", "filters_label"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`<div class="ui-toolbar" data-filter-toolbar data-list-toolbar>`)
	if s := a.v("search", nil); truthy(s) {
		row := items([]any{s})[0]
		b.WriteString(`<label class="ui-toolbar-search">` + mustIcon("search", 16) + `<input class="ui-input" type="search" name="` + esc(cell(row, 0)) + `" placeholder="` + esc(cell(row, 1)) + `" value="` + esc(cell(row, 2)) + `" aria-label="` + esc(cell(row, 1)) + `"></label>`)
	}
	if chips := items(a.v("chips", nil)); len(chips) > 0 {
		b.WriteString(`<div class="ui-chips">`)
		for _, row := range chips {
			h, err := c.uiChip(cell(row, 1), map[string]any{"href": cell(row, 0), "selected": cell(row, 2)})
			if err != nil {
				return "", err
			}
			b.WriteString(string(h))
		}
		b.WriteString(`</div>`)
	}
	if a.b("filters_id", false) {
		label := a.e("filters_label", "")
		if !a.b("filters_label", false) {
			label = escText(c.t("host.filter.filters"))
		}
		count := ""
		if a.b("filters_count", false) {
			count = `<span class="ui-badge ui-badge-neutral">` + a.e("filters_count", "") + `</span>`
		}
		b.WriteString(`<button class="ui-btn ui-btn-secondary" type="button" data-filter-toggle aria-expanded="true" aria-controls="` + a.e("filters_id", "") + `" hidden>` + mustIcon("sliders-horizontal", 16) + `<span>` + label + `</span>` + count + `</button>`)
	}
	if actions := a.raw("actions"); strings.TrimSpace(actions) != "" {
		b.WriteString(`<div class="ui-toolbar-right">` + actions + `</div>`)
	}
	b.WriteString(`</div>`)
	return html(b.String()), nil
}

func (c *reqCtx) uiSection(in ...any) (template.HTML, error) {
	a, err := bind("ui_section", []string{"title", "actions", "id", "tip"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`<section class="ui-section"`)
	if a.b("id", false) {
		b.WriteString(` id="` + a.e("id", "") + `"`)
	}
	b.WriteString(`><div class="ui-section-h">`)
	if a.b("tip", false) {
		parts := rsplit1(a.s("title", ""))
		b.WriteString(`<h2>`)
		if len(parts) == 2 {
			b.WriteString(escText(parts[0]) + " ")
		}
		b.WriteString(`<span class="tip-nowrap">` + escText(parts[len(parts)-1]) + `</span>` + a.e("tip", "") + `</h2>`)
	} else {
		b.WriteString(`<h2>` + a.e("title", "") + `</h2>`)
	}
	if actions := a.raw("actions"); strings.TrimSpace(actions) != "" {
		b.WriteString(`<div class="ui-btn-group">` + actions + `</div>`)
	}
	b.WriteString(`</div>` + a.raw("caller") + `</section>`)
	return html(b.String()), nil
}

func uiFacts(pairs any) template.HTML {
	var b strings.Builder
	b.WriteString(`<dl class="ui-facts">`)
	for _, row := range items(pairs) {
		b.WriteString(`<div><dt>` + esc(cell(row, 0)) + `</dt><dd>` + safe(cell(row, 1)) + `</dd></div>`)
	}
	b.WriteString(`</dl>`)
	return html(b.String())
}

func uiStats(list any, label ...any) template.HTML {
	var b strings.Builder
	l := ""
	if len(label) > 0 {
		l = esc(label[0])
	}
	b.WriteString(`<nav class="ui-stats" aria-label="` + l + `">`)
	for _, row := range items(list) {
		b.WriteString(`<a class="ui-stat" href="` + safeHref(cell(row, 0)) + `"><strong class="ui-num">` + esc(cell(row, 1)) + `</strong><span>` + esc(cell(row, 2)) + `</span></a>`)
	}
	b.WriteString(`</nav>`)
	return html(b.String())
}

func (c *reqCtx) uiBanner(in ...any) (template.HTML, error) {
	a, err := bind("ui_banner", []string{"kind", "text", "action_label", "action_href"}, in)
	if err != nil {
		return "", err
	}
	name := "info"
	if a.s("kind", "") == "attention" {
		name = "triangle-alert"
	}
	btn := ""
	if a.b("action_href", false) {
		h, err := c.uiButton(a.v("action_label", ""), "secondary", map[string]any{"href": a.v("action_href", ""), "size": "compact"})
		if err != nil {
			return "", err
		}
		btn = string(h)
	}
	return html(`<div class="ui-banner ui-banner-` + a.e("kind", "") + `" role="status">` + mustIcon(name, 20) + `<div class="grow">` + a.raw("text") + `</div>` + btn + `</div>`), nil
}

func uiTableBegin(columns any, label ...any) template.HTML {
	var b strings.Builder
	l := ""
	if len(label) > 0 {
		l = esc(label[0])
	}
	b.WriteString(`<table class="ui-table" aria-label="` + l + `"><thead><tr>`)
	for _, row := range items(columns) {
		cls := ""
		if pyStr(cell(row, 1)) == "r" {
			cls = ` class="ui-cell-r"`
		}
		b.WriteString(`<th scope="col"` + cls + `>` + esc(cell(row, 0)) + `</th>`)
	}
	b.WriteString(`</tr></thead><tbody>`)
	return html(b.String())
}

func uiTableEnd() template.HTML { return html(`</tbody></table>`) }

func uiCard(in ...any) (template.HTML, error) {
	a, err := bind("ui_card", []string{"href", "l1", "l2", "l3", "badge", "label"}, in)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	b.WriteString(`<a class="ui-card" href="` + a.href("href") + `"`)
	if a.b("label", false) {
		b.WriteString(` aria-label="` + a.e("label", "") + `"`)
	}
	b.WriteString(`><span class="ui-card-l1"><span>` + a.raw("l1") + `</span>` + a.raw("badge") + `</span>`)
	if a.b("l2", false) {
		b.WriteString(`<span class="ui-card-l2">` + a.raw("l2") + `</span>`)
	}
	if a.b("l3", false) {
		b.WriteString(`<span class="ui-card-l3">` + a.raw("l3") + `</span>`)
	}
	b.WriteString(`</a>`)
	return html(b.String()), nil
}

// uiSkeleton is ui_skeleton(kind).
func uiSkeleton(kind any) template.HTML {
	k := pyStr(kind)
	var b strings.Builder
	b.WriteString(`<div class="ui-skel" aria-hidden="true" data-skeleton-kind="` + escText(k) + `">`)
	b.WriteString(`<div class="ui-skel-h"><div><span class="ui-bone ui-bone-title"></span><span class="ui-bone ui-bone-meta"></span></div><span class="ui-bone ui-bone-btn"></span></div>`)
	rep := func(n int, s string) string { return strings.Repeat(s, n) }
	switch k {
	case "list":
		b.WriteString(`<span class="ui-bone ui-bone-toolbar"></span>`)
		b.WriteString(`<div class="ui-skel-rows">` + rep(6, `<div class="ui-skel-row"><span class="ui-bone ui-w30"></span><span class="ui-bone ui-w18"></span><span class="ui-bone ui-w18"></span><span class="ui-bone ui-w14"></span><span class="ui-bone ui-bone-badge"></span></div>`) + `</div>`)
		b.WriteString(`<div class="ui-skel-cards">` + rep(6, `<div class="ui-skel-card"><span class="ui-bone ui-w40"></span><span class="ui-bone ui-w60"></span><span class="ui-bone ui-w30"></span></div>`) + `</div>`)
	case "detail":
		b.WriteString(`<div class="ui-skel-detail"><div class="ui-skel-group">` + rep(2, `<span class="ui-bone ui-bone-label"></span><div class="ui-skel-rows">`+rep(3, `<div class="ui-skel-row"><span class="ui-bone ui-w40"></span></div>`)+`</div>`) + `</div>`)
		b.WriteString(`<div class="ui-skel-side ui-skel-rows">` + rep(4, `<div class="ui-skel-row"><span class="ui-bone ui-w30"></span><span class="ui-bone ui-w30"></span></div>`) + `</div></div>`)
	case "form":
		b.WriteString(`<div class="ui-skel-group">` + rep(6, `<span class="ui-bone ui-bone-label"></span><span class="ui-bone ui-bone-control"></span>`) + `<span class="ui-bone ui-bone-btn"></span></div>`)
	default:
		b.WriteString(`<div class="ui-skel-group">` + rep(2, `<span class="ui-bone ui-bone-label"></span><div class="ui-skel-rows">`+rep(3, `<div class="ui-skel-row ui-skel-row-setting"><span class="ui-bone ui-w40"></span><span class="ui-bone ui-bone-btn"></span></div>`)+`</div>`) + `</div>`)
	}
	b.WriteString(`</div>`)
	return html(b.String())
}
