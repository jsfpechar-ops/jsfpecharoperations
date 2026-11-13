package properties

// GET pages of the property settings area (brief 1301): /guide and
// /guest-links, ported from App/app/routes/admin.py guide_view (~645) and
// guest_links / _property_hub_redirect (~657-680). The page body is
// templates/guide.tmpl, rendered inside the host layout (hostweb/layout).

import (
	"embed"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/*.tmpl
var pageFiles embed.FS

// pages is parsed once; the layout clones it per request.
var pages = layout.MustParse(catalog, pageFiles, "templates/*.tmpl")

// RegisterPages adds the GET routes. It only builds handlers; the pool is
// first used inside a request.
func RegisterPages(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &Pages{pool: pool, getenv: getenv, now: now}
	for _, route := range []struct {
		path string
		h    http.HandlerFunc
	}{
		{"/guide", s.guide},
		{"/guest-links", s.guestLinks},
	} {
		mux.Handle("GET "+route.path, wrap(route.path, route.h))
	}
}

// Pages serves the GET routes; it shares the action server's fields.
type Pages server

// workflowStep is one row of workflow.steps(None) (App/app/workflow.py).
type workflowStep struct {
	N        int
	Key, Who string
}

type statusRow struct{ Tone, Label, Body string }

type part struct {
	Part  string
	Count int
}

// guideData is the guide.html context: havel_on, demo_available and the
// fixed lists the Jinja template spells inline.
type guideData struct {
	Havel, Demo    bool
	Sections       []string
	N              []int
	FindingParts   []string
	Workflow       []workflowStep
	Statuses       []statusRow
	CleaningParts  []part
	ReportingModes []string
	SettingsParts  []part
	FAQ            []string
	Glossary       []string
	Legal          []string
}

var guideSections = []string{"finding", "overview", "statuses", "setup", "business", "stays", "cleaning", "guests", "guest_links", "reporting", "filters", "housebook", "stay_fee", "invoices", "payments", "settings", "archive", "privacy_requests", "door-codes", "faster", "faq", "glossary", "legal"}

func newGuideData(havel, demo bool) guideData {
	sections := append([]string{}, guideSections...)
	if havel {
		sections = append(sections, "havel")
	}
	if demo {
		sections = append(sections, "demo")
	}
	n := make([]int, 12)
	for i := range n {
		n[i] = i + 1
	}
	return guideData{
		Havel: havel, Demo: demo, Sections: sections, N: n,
		FindingParts: []string{"phone", "computer"},
		// workflow.steps(None): no property, so step 4 is "police" and step 5 "finish".
		Workflow: []workflowStep{
			{1, "paste", "you_once"}, {2, "form", "auto"}, {3, "email", "auto"}, {4, "police", "auto"}, {5, "finish", "auto"},
		},
		Statuses: []statusRow{
			{"red", "status.failed", "guide.statuses.failed"},
			{"amber", "status.incomplete", "guide.statuses.incomplete"},
			{"blue", "status.ready", "guide.statuses.ready"},
			{"teal", "status.awaiting_guest_short", "guide.statuses.waiting"},
			{"green", "status.reported", "guide.statuses.reported"},
			{"grey", "status.not_required", "guide.statuses.not_required"},
		},
		CleaningParts:  []part{{"add", 5}, {"codes", 3}, {"share", 4}},
		ReportingModes: []string{"immediate", "scheduled", "manual"},
		SettingsParts:  []part{{"passkey", 3}, {"twofa", 4}, {"email", 2}},
		FAQ:            []string{"link", "count", "czech", "twice", "edit"},
		Glossary:       []string{"stay", "guest_link", "pin", "ical", "ubyport", "idub", "stay_fee", "housebook"},
		Legal:          []string{"housebook", "paper", "signature", "verification", "reporting", "retention"},
	}
}

const accountEmailSQL = `SELECT COALESCE(email, '') FROM user_account WHERE id = $1`

func (s *Pages) guide(w http.ResponseWriter, r *http.Request) {
	now := s.now()
	host, err := hostweb.Login(w, r, s.pool, s.getenv, now)
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	// ai.enabled_for(havel.FEATURE, current_user email): the signed-in
	// account (the admin while inside another workspace), not the workspace.
	havel := false
	if aiFeatureOn(s.getenv, "havel") {
		var email string
		err := s.pool.QueryRow(r.Context(), accountEmailSQL, host.Account.ID).Scan(&email)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			fail(w, err)
			return
		}
		havel = aiOnTestList(s.getenv, email)
	}
	// config.UBYPORT_ENV == "mock" (default mock, lower-cased; an empty value
	// counts as unset, as layout's env banner reads it).
	env := strings.ToLower(s.getenv("UBYHOST_UBYPORT_ENV"))
	if env == "" {
		env = "mock"
	}
	page := layout.Page{
		Title:    catalog.T(hostweb.Lang(r), "guide.title", nil),
		Nav:      "guide",
		BodyKind: "detail",
		V2:       true,
	}
	if err := layout.Render(w, r, layout.Env{Pool: s.pool, Getenv: s.getenv, Now: now}, host, page, pages, "guide", newGuideData(havel, env == "mock")); err != nil {
		fail(w, err)
	}
}

// apartmentsSQL is access.apartments(request) reduced to what
// _property_hub_redirect reads: the owner's non-archived ids by internal_name.
const apartmentsSQL = `SELECT id FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY internal_name LIMIT 2`

// guestLinks is guest_links: one property opens its guest settings, several
// or none land on the Properties summary.
func (s *Pages) guestLinks(w http.ResponseWriter, r *http.Request) {
	host, err := hostweb.Login(w, r, s.pool, s.getenv, s.now())
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	rows, err := s.pool.Query(r.Context(), apartmentsSQL, host.Workspace.ID)
	if err != nil {
		fail(w, err)
		return
	}
	ids, err := pgx.CollectRows(rows, pgx.RowTo[int64])
	if err != nil {
		fail(w, err)
		return
	}
	target := "/apartments#" + propertySummariesAnchor
	if len(ids) == 1 {
		target = "/apartments/" + strconv.FormatInt(ids[0], 10) + "?view=settings&section=guests#communication"
	}
	w.Header().Set("Location", target)
	w.WriteHeader(http.StatusSeeOther)
}

// propertySummariesAnchor is admin.py PROPERTY_SUMMARIES_ANCHOR.
const propertySummariesAnchor = "property-summaries"

// aiFeatureOn is ai.enabled: the feature is in UBYHOST_AI_FEATURES and the
// provider's key is set (copy of palette.aiEnabledFor's first half).
func aiFeatureOn(getenv func(string) string, feature string) bool {
	if !listHas(getenv("UBYHOST_AI_FEATURES"), feature) {
		return false
	}
	key := getenv("UBYHOST_ANTHROPIC_API_KEY")
	if strings.ToLower(strings.TrimSpace(getenv("UBYHOST_AI_PROVIDER"))) == "mistral" {
		key = getenv("UBYHOST_MISTRAL_API_KEY")
	}
	return strings.TrimSpace(key) != ""
}

// aiOnTestList is ai.on_test_list: an empty UBYHOST_AI_TEST_EMAILS lets everyone.
func aiOnTestList(getenv func(string) string, email string) bool {
	if strings.TrimSpace(getenv("UBYHOST_AI_TEST_EMAILS")) == "" {
		return true
	}
	return listHas(getenv("UBYHOST_AI_TEST_EMAILS"), email)
}

// listHas reports whether a comma-separated list holds value, case-insensitively
// (copy of palette.listHas).
func listHas(list, value string) bool {
	value = strings.ToLower(strings.TrimSpace(value))
	if value == "" {
		return false
	}
	for _, p := range strings.Split(list, ",") {
		if strings.ToLower(strings.TrimSpace(p)) == value {
			return true
		}
	}
	return false
}
