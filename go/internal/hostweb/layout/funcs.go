package layout

import (
	"html/template"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// reqCtx is what the request-bound funcs read: the language, both catalogs,
// the CSRF token, the page's v2 flag and the clock.
type reqCtx struct {
	lang   string
	page   hostweb.Catalog
	layout hostweb.Catalog
	csrf   string
	v2     bool
	now    time.Time
	getenv func(string) string // nil at parse time
}

// has reports whether the catalog has the key in lang or the default table.
func has(cat hostweb.Catalog, lang, key string) bool {
	if _, ok := cat[lang][key]; ok {
		return true
	}
	_, ok := cat[hostweb.DefaultLanguage][key]
	return ok
}

// params reads "name" value pairs, or one map[string]any.
func params(in []any) map[string]any {
	if len(in) == 1 {
		if m, ok := in[0].(map[string]any); ok {
			return m
		}
	}
	if len(in) == 0 {
		return nil
	}
	m := make(map[string]any, len(in)/2)
	for i := 0; i+1 < len(in); i += 2 {
		if k, ok := in[i].(string); ok {
			m[k] = in[i+1]
		}
	}
	return m
}

// t is the template t(): the page catalog first, then the layout catalog,
// then the key itself.
func (c *reqCtx) t(key string, in ...any) string {
	p := params(in)
	if c.page != nil && has(c.page, c.lang, key) {
		return c.page.T(c.lang, key, p)
	}
	return c.layout.T(c.lang, key, p)
}

// pluralKey is host_i18n.plural_key for en, cs and vi.
func pluralKey(base string, n int) string {
	switch {
	case n == 1:
		return base + ".one"
	case n >= 2 && n <= 4:
		return base + ".few"
	}
	return base
}

// tp is the template tp(): host_i18n.translate_plural with count and n set.
func (c *reqCtx) tp(base string, nv any, in ...any) string {
	n := toInt(nv)
	p := params(in)
	if p == nil {
		p = map[string]any{}
	}
	if _, ok := p["count"]; !ok {
		p["count"] = n
	}
	if _, ok := p["n"]; !ok {
		p["n"] = n
	}
	return c.t(pluralKey(base, n), p)
}

// funcs is the template func map, bound to this request.
func (c *reqCtx) funcs() template.FuncMap {
	return template.FuncMap{
		"t":                     c.t,
		"tp":                    c.tp,
		"lang":                  func() string { return c.lang },
		"csrf":                  func() string { return c.csrf },
		"kv":                    kv,
		"safe":                  func(s string) template.HTML { return template.HTML(s) },
		"icon":                  icon,
		"datetime_local":        datetimeLocal,
		"describe_time_left":    c.describeTimeLeft,
		"ui_button":             c.uiButton,
		"ui_icon_button":        c.uiIconButton,
		"ui_badge":              c.uiBadge,
		"ui_chip":               c.uiChip,
		"ui_field":              c.uiField,
		"ui_select":             c.uiSelect,
		"ui_textarea":           c.uiTextarea,
		"ui_check":              c.uiCheck,
		"ui_toggle":             c.uiToggle,
		"ui_menu_begin":         c.uiMenuBegin,
		"ui_menu_end":           uiMenuEnd,
		"ui_menu_item":          c.uiMenuItem,
		"ui_dialog_begin":       uiDialogBegin,
		"ui_dialog_end":         uiDialogEnd,
		"ui_empty":              c.uiEmpty,
		"ui_tip":                c.uiTip,
		"ui_pagination":         c.uiPagination,
		"ui_pdot":               uiPdot,
		"ui_tabs":               c.uiTabs,
		"ui_toolbar":            c.uiToolbar,
		"ui_section":            c.uiSection,
		"ui_facts":              uiFacts,
		"ui_stats":              uiStats,
		"ui_banner":             c.uiBanner,
		"ui_table_begin":        uiTableBegin,
		"ui_table_end":          uiTableEnd,
		"ui_card":               uiCard,
		"ui_skeleton":           uiSkeleton,
		"help_tip":              c.helpTip,
		"page_help":             c.pageHelp,
		"tip_label":             c.tipLabel,
		"choice_card":           c.choiceCard,
		"field_label":           c.fieldLabel,
		"sub_tabs":              c.subTabs,
		"page_header":           c.pageHeader,
		"progress_pill":         c.progressPill,
		"guest_count":           c.guestCount,
		"bulk_send_ready":       c.bulkSendReady,
		"sync_calendars_button": c.syncCalendarsButton,
		"nav_icon":              navIcon,
		"csv_actions_menu":      c.csvActionsMenu,
		"submission_pill":       c.submissionPill,
		"deadline_badge":        c.deadlineBadge,
		"empty_state":           c.emptyState,
		"property_identity":     propertyIdentity,
		"success_notice":        c.successNotice,
		"copy_icon":             copyIcon,
		"copy_button":           c.copyButton,
		"copy_inline":           c.copyInline,
		"row_menu_begin":        c.rowMenuBegin,
		"row_menu_end":          rowMenuEnd,
		"row_open":              c.rowOpen,
		"source_mark":           sourceMark,
		"source_badge":          sourceBadge,
		"settings_group":        settingsGroup,
		"settings_heading":      c.settingsHeading,
		"billing_on":            func() bool { return c.getenv != nil && billingOn(c.getenv) },
		"seq":                   seq,
		"add":                   add,
		"sub":                   sub,
		"default":               dflt,
	}
}
