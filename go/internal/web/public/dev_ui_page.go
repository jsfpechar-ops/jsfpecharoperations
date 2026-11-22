package public

// GET /dev/ui (dev_ui.py): the living component catalog, admin only. The
// markup is templates/dev_ui/dev_ui.tmpl, a block-for-block port of
// App/app/templates/dev_ui.html on the host shell.

import (
	"embed"
	"html/template"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/dev_ui/*.tmpl
var devUITemplateFS embed.FS

// devUIPages carries no page catalog of its own: the catalog page's copy is
// literal, and the macro defaults come from the layout catalog.
var devUIPages = layout.MustParse(nil, devUITemplateFS, "templates/dev_ui/*.tmpl")

// devUISkeletonKinds is dev_ui.py's SKELETON_KINDS.
var devUISkeletonKinds = []string{"list", "detail", "form", "settings"}

// devUITokens is the swatch list of the Tokens section, in Python's order.
var devUITokens = []string{
	"canvas", "surface", "surface-2", "surface-3", "ink", "ink-2", "ink-3", "line",
	"line-strong", "accent", "accent-soft", "accent-ink", "st-action-bg",
	"st-attention-bg", "st-done-bg", "st-neutral-bg", "danger",
	"property-1", "property-2", "property-3",
}

type devUISampleRow struct {
	Index int
	Pdot  int
}

type devUIData struct {
	Tabs          []any
	Tokens        []string
	Skeletons     []string
	SelectOptions [][2]string
	TableColumns  []any
	SampleRows    []devUISampleRow
	Cards         []int
	Facts         []any
	Stats         []any
}

func devUIDataFor() devUIData {
	return devUIData{
		Tabs: []any{
			[]any{"/dev/ui#tokens", "Tokens", true},
			[]any{"/dev/ui#buttons", "Buttons", false},
			[]any{"/dev/ui#lists", "Lists", false},
			[]any{"/dev/ui#skeletons", "Skeletons", false},
		},
		Tokens:    devUITokens,
		Skeletons: devUISkeletonKinds,
		SelectOptions: [][2]string{
			{"a", "All properties"},
			{"b", "Studio Karlín"},
		},
		TableColumns: []any{
			[]any{"Stay", ""}, []any{"Dates", ""}, []any{"Property", ""},
			[]any{"Guests", "r"}, []any{"Police report", ""}, []any{"", ""},
		},
		SampleRows: []devUISampleRow{{1, 0}, {2, 1}, {3, 2}},
		Cards:      []int{0, 1, 2},
		Facts: []any{
			[]any{"Property", "Byt Vinohradská 12"},
			[]any{"Arrival", "19. 10. 2026"},
			[]any{"Guests", "1 of 2"},
			[]any{"Door code", template.HTML(`<span class="ui-mono">4821 #</span>`)},
		},
		Stats: []any{
			[]any{"#", 3, "Needs you"},
			[]any{"#", 2, "Ready to send"},
			[]any{"#", 1, "Overdue"},
		},
	}
}

// DevUIHandler serves GET /dev/ui for admins (mirrors dev_ui.py).
func DevUIHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if h == nil {
			return
		}
		if h.Account.Role != "admin" {
			http.NotFound(w, r)
			return
		}
		kind := r.URL.Query().Get("kind")
		if !devUIBodyKind(kind) {
			kind = "detail"
		}
		page := layout.Page{Title: "UI catalog", Nav: "admin", BodyKind: kind}
		env := layout.Env{Pool: pool, Getenv: getenv, Now: at}
		if err := layout.Render(w, r, env, h, page, devUIPages, "dev_ui", devUIDataFor()); err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		}
	}
}

func devUIBodyKind(kind string) bool {
	for _, k := range devUISkeletonKinds {
		if k == kind {
			return true
		}
	}
	return false
}
