package submissions

import (
	"embed"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

//go:embed i18n.json
var catalogJSON []byte

var catalog = hostweb.Load(catalogJSON)

var outcomeTone = map[string]string{
	"ok": "p-ok", "ok_duplicate": "p-ok", "partial": "p-warn",
	"error": "p-bad", "failed": "p-bad", "transport_error": "p-bad",
	"outcome_unknown": "p-bad", "not_configured": "p-warn", "running": "p-n", "noop": "p-n",
}

var outcomeKey = map[string]string{
	"ok": "submission.accepted", "ok_duplicate": "submission.duplicate", "partial": "submission.partial",
	"error": "submission.rejected", "failed": "submission.rejected", "transport_error": "submission.not_delivered",
	"outcome_unknown": "submission.outcome_unknown", "not_configured": "submission.setup_incomplete",
	"running": "submission.in_progress", "noop": "submission.nothing_to_send",
}

var outcomeLevel = map[string]string{
	"ok": "done", "ok_duplicate": "done", "partial": "action", "not_configured": "action",
	"error": "critical", "failed": "critical", "transport_error": "critical",
	"outcome_unknown": "critical", "running": "waiting", "noop": "neutral",
}

var outcomeNote = map[string]string{
	"ok": "reports.detail.note_ok", "ok_duplicate": "reports.detail.note_duplicate",
	"partial": "reports.detail.note_partial", "error": "reports.detail.note_rejected",
	"failed": "reports.detail.note_rejected", "transport_error": "reports.detail.note_failed",
	"outcome_unknown": "reports.detail.note_outcome_unknown", "running": "reports.detail.note_running",
	"noop": "reports.detail.note_noop", "not_configured": "reports.detail.note_noop",
}

var tplFuncs = map[string]any{
	"report_mode_label":  reportModeLabel,
	"outcome_tone":       outcomeToneFunc,
	"outcome_label":      outcomeLabel,
	"outcome_level":      outcomeLevelFunc,
	"outcome_note":       outcomeNoteFunc,
	"initial_rune":       initialRune,
	"guest_count_json":   guestCountJSON,
	"stamp_or_dash":      stampOrDash,
	"accepted_states":    acceptedState,
	"has_pdf":            hasPDF,
	"country_line":       countryLine,
	"guest_doc_line":     guestDocLine,
	"record_errors_join": stringsJoin,
}

var pages = layout.MustParseFuncs(catalog, tplFuncs, templateFS, "templates/*.tmpl")

func reportModeLabel(lang, mode string) string {
	key := "reports.mode." + strings.TrimSpace(mode)
	text := catalog.T(lang, key, nil)
	if text == key {
		m := strings.ReplaceAll(strings.TrimSpace(mode), "_", " ")
		if m == "" {
			return ""
		}
		return strings.ToUpper(m[:1]) + m[1:]
	}
	return text
}

func outcomeToneFunc(state string) string {
	if v, ok := outcomeTone[state]; ok {
		return v
	}
	return "p-bad"
}

func outcomeLabel(lang, state string) string {
	if key, ok := outcomeKey[state]; ok {
		return catalog.T(lang, key, nil)
	}
	return state
}

func outcomeLevelFunc(state string) string {
	if v, ok := outcomeLevel[state]; ok {
		return v
	}
	return "critical"
}

func outcomeNoteFunc(lang, state string) string {
	if key, ok := outcomeNote[state]; ok {
		return catalog.T(lang, key, nil)
	}
	return ""
}

func initialRune(name string) string {
	name = strings.TrimSpace(name)
	if name == "" || name == "?" {
		return "?"
	}
	return strings.ToUpper(string([]rune(name)[:1]))
}

func guestCountJSON(guestIDs string) int {
	guestIDs = strings.TrimSpace(guestIDs)
	if guestIDs == "" {
		return 0
	}
	var ids []any
	if err := json.Unmarshal([]byte(guestIDs), &ids); err != nil {
		return 0
	}
	return len(ids)
}

func stampOrDash(stamp string) string {
	if strings.TrimSpace(stamp) == "" {
		return "—"
	}
	return stamp
}

func acceptedState(state string) bool {
	switch state {
	case "ok", "ok_duplicate", "partial":
		return true
	}
	return false
}

func hasPDF(v string) bool {
	return strings.TrimSpace(v) != ""
}

func countryLine(lang, code string) string {
	code = strings.TrimSpace(code)
	if code == "" {
		return "—"
	}
	if name := countries.Name(code, lang); name != "" {
		return name
	}
	return code
}

func guestDocLine(visible bool, doc string) string {
	if !visible {
		return maskIdentifier(doc)
	}
	return strings.TrimSpace(doc)
}

// maskIdentifier is access.mask_identifier.
func maskIdentifier(v string) string {
	if v == "" {
		return ""
	}
	r := []rune(v)
	if len(r) <= 3 {
		return "•••"
	}
	return "•••" + string(r[len(r)-3:])
}

func stringsJoin(lines []string, sep string) string {
	return strings.Join(lines, sep)
}

func detailTitle(lang string, id int64) string {
	return catalog.T(lang, "reports.detail.title", map[string]any{"id": id})
}

func detailMeta(lang, aptName, mode string) string {
	return fmt.Sprintf("%s · %s", aptName, reportModeLabel(lang, mode))
}
