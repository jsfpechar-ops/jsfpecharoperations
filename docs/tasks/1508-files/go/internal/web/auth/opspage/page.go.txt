// Package opspage renders GET /admin/operations, the operator's System page
// (brief 1508): the port of operations_admin in
// App/app/routes/admin_accounts.py (lines 929-950) with its template
// admin_operations.html. The admin gate is the caller's (package auth); the
// forms on the page post to /admin/incidents and /admin/incidents/{id},
// which brief 1282 serves. Nothing here writes.
package opspage

import (
	"context"
	"embed"
	"net/http"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
)

//go:embed i18n.json
var catalogJSON []byte

//go:embed templates/*.tmpl
var templateFS embed.FS

// catalog holds the strings the page reads, generated from i18n_keys.txt by
// App/scripts/go_host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

var pages = layout.MustParse(catalog, templateFS, "templates/*.tmpl")

// tr is t() for the texts the handler builds, in the page's language.
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

// age is the template macro age(minutes).
func (lang tr) age(minutes *int64) string {
	switch {
	case minutes == nil:
		return lang.t("ops.age.never")
	case *minutes < 120:
		return lang.t("ops.age.minutes", "n", *minutes)
	case *minutes < 2880:
		return lang.t("ops.age.hours", "n", *minutes/60)
	}
	return lang.t("ops.age.days", "n", *minutes/1440)
}

// pyCapitalize is Jinja's capitalize (str.capitalize): the first character
// in title case, the rest in lower case.
func pyCapitalize(s string) string {
	r, size := utf8.DecodeRuneInString(s)
	if size == 0 {
		return s
	}
	return string(unicode.ToTitle(r)) + strings.ToLower(s[size:])
}

// workspace is the template macro workspace_link(row).
type workspace struct {
	OwnerID *int64
	Label   string // row.workspace or row.owner_user_id
}

func newWorkspace(owner *int64, name string) workspace {
	if owner == nil || *owner == 0 { // Jinja: no owner, or 0, is false
		return workspace{}
	}
	label := name
	if label == "" {
		label = strconv.FormatInt(*owner, 10)
	}
	return workspace{OwnerID: owner, Label: label}
}

type filingView struct {
	Workspace       workspace
	Property, State string
	StayID          int64
	Age             string
}
type stuckView struct {
	Workspace    workspace
	Property     string
	SubmissionID int64
	Age          string
}
type feedView struct {
	Workspace       workspace
	Property, Label string
	FeedID          int64
	StateText, Age  string
}
type jobView struct {
	Name, Interval, LastOK string
	Failed, Late           bool
}
type mailView struct {
	OutboxID         int64
	Kind, State, Age string
	Attempts         int64
}
type alertView struct {
	KindLabel, Kind, Level, Age string
	Count                       int64
}
type gapView struct {
	Count                               int
	Question, Why, Anchor, Label, Where string
}
type stampView struct {
	Field, Label, Value string
}
type incidentView struct {
	ID                  int64
	Summary, DetectedAt string
	RiskText            string
	Stamps              []stampView
	Draft               string
}

// view is the data of admin_operations.tmpl.
type view struct {
	Tabs [][]any

	FilingsCount, StuckCount int64
	Filings                  []filingView
	Stuck                    []stuckView
	FeedsCount               int64
	Feeds                    []feedView
	JobsCount                int64
	Jobs                     []jobView
	MailCount                int64
	Mail                     []mailView

	TTLockEnabled, TTLockOpen, TTLockHigh bool
	TTLockBadge, TTLockLine               string

	AlertsCount int64
	Alerts      []alertView

	HavelOpen  bool
	HavelLine  string
	Gaps       []gapView
	HavelStats []ai.HavelStat

	ReviewAlerts []reviewView
	Owners       []Owner
	Incidents    []incidentView
}

type reviewView struct{ Message, Detail string }

// adminTabs is ui_section_tabs() on /admin/operations: the System tab is open.
func adminTabs(lang tr) [][]any {
	return [][]any{
		{"/admin", lang.t("admin.tab.today"), false},
		{"/admin/customers", lang.t("customers.title"), false},
		{"/admin/fakturace", lang.t("admin.tab.money"), false},
		{"/admin/operations", lang.t("admin.tab.system"), true},
	}
}

var feedStates = map[string]bool{"ok": true, "error": true, "suspect": true, "never": true}

// pyNone is how Jinja prints a NULL column: None.
func pyNone(p *string) string {
	if p == nil {
		return "None"
	}
	return *p
}

func buildView(lang tr, o Overview, h ai.HavelOps, incidents []Incident, reviews []ReviewAlert, owners []Owner) view {
	v := view{Tabs: adminTabs(lang), FilingsCount: o.FilingsCount, StuckCount: o.StuckCount, FeedsCount: o.FeedsCount,
		JobsCount: o.JobsCount, MailCount: o.MailCount, AlertsCount: o.AlertsCount, Owners: owners}
	for _, f := range o.Filings {
		v.Filings = append(v.Filings, filingView{Workspace: newWorkspace(f.OwnerUserID, f.Workspace), Property: f.Property,
			State: lang.t("ops.filing_state." + f.State), StayID: f.StayID, Age: lang.age(f.AgeMinutes)})
	}
	for _, s := range o.Stuck {
		v.Stuck = append(v.Stuck, stuckView{Workspace: newWorkspace(s.OwnerUserID, s.Workspace), Property: s.Property,
			SubmissionID: s.SubmissionID, Age: lang.age(s.AgeMinutes)})
	}
	for _, f := range o.Feeds {
		state := f.Status
		if feedStates[f.Status] {
			state = lang.t("ops.feed_state." + f.Status)
		}
		v.Feeds = append(v.Feeds, feedView{Workspace: newWorkspace(f.OwnerUserID, f.Workspace), Property: f.Property,
			Label: f.Label, FeedID: f.FeedID, StateText: state, Age: lang.age(f.AgeMinutes)})
	}
	for _, j := range o.Jobs {
		interval := j.IntervalMinutes
		v.Jobs = append(v.Jobs, jobView{Name: pyCapitalize(lang.t("notification.job_name." + j.JobID)),
			Interval: lang.age(&interval), LastOK: lang.age(j.AgeMinutes), Failed: j.Failed, Late: j.Late})
	}
	for _, m := range o.Mail {
		v.Mail = append(v.Mail, mailView{OutboxID: m.OutboxID, Kind: m.Kind, State: m.State, Attempts: m.Attempts,
			Age: lang.age(m.AgeMinutes)})
	}
	t := o.TTLock
	v.TTLockEnabled = t.Enabled
	v.TTLockHigh = float64(t.Used) >= float64(t.Limit)*0.8
	v.TTLockOpen = t.Failed != 0 || v.TTLockHigh
	v.TTLockBadge = strconv.FormatInt(t.Used, 10) + " / " + strconv.FormatInt(t.Limit, 10)
	mode := lang.t("ops.ttlock.test_mode")
	if t.Live {
		mode = lang.t("ops.ttlock.live")
	}
	v.TTLockLine = lang.t("ops.ttlock.counts", "issued", t.Issued, "failed", t.Failed) + " · " + mode
	for _, a := range o.Alerts {
		key := "ops.alert_kind." + a.Kind
		label := lang.t(key)
		if label == key {
			label = ""
		}
		v.Alerts = append(v.Alerts, alertView{KindLabel: label, Kind: a.Kind, Level: a.Level, Count: a.Count,
			Age: lang.age(a.AgeMinutes)})
	}
	v.HavelOpen = len(h.Gaps) > 0
	v.HavelLine = lang.t("ops.havel.spend", "spent", h.Spent, "cap", h.Cap, "percent", h.Percent)
	if !h.Enabled {
		v.HavelLine += " · " + lang.t("ops.havel.off")
	}
	for _, g := range h.Gaps {
		why := make([]string, len(g.Reasons))
		for i, k := range g.Reasons {
			why[i] = lang.t(k)
		}
		page := g.Page
		if page == "" {
			page = "-"
		}
		v.Gaps = append(v.Gaps, gapView{Count: g.Count, Question: g.Question, Why: strings.Join(why, "; "),
			Anchor: g.GuideAnchor, Label: lang.t(g.GuideLabel), Where: page + " · " + g.Langs + " · " + g.Newest})
	}
	v.HavelStats = h.Stats
	for _, r := range reviews {
		v.ReviewAlerts = append(v.ReviewAlerts, reviewView{Message: r.Message, Detail: pyNone(r.Detail)})
	}
	for _, in := range incidents {
		risk := "none"
		if in.RiskLevel != nil && *in.RiskLevel != "" {
			risk = *in.RiskLevel
		}
		iv := incidentView{ID: in.ID, Summary: in.Summary, DetectedAt: in.DetectedAt,
			RiskText: lang.t("incidents.risk." + risk), Draft: Draft(in)}
		for _, f := range incidentTimestamps {
			iv.Stamps = append(iv.Stamps, stampView{Field: f[0], Label: lang.t(f[1]), Value: str(in.Stamps[f[0]])})
		}
		v.Incidents = append(v.Incidents, iv)
	}
	return v
}

// lookupFrom turns getenv into the lookup anthropic.ConfigFromEnv reads. An
// empty value counts as unset (Python would read the empty string).
func lookupFrom(getenv func(string) string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v := getenv(k)
		return v, v != ""
	}
}

// load reads every block of the page.
func load(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (Overview, ai.HavelOps, []Incident, []ReviewAlert, []Owner, error) {
	o, err := LoadOverview(ctx, pool, getenv, at)
	if err != nil {
		return o, ai.HavelOps{}, nil, nil, nil, err
	}
	svc := &anthropic.Service{Pool: pool, Cfg: anthropic.ConfigFromEnv(lookupFrom(getenv)), Now: func() time.Time { return at }}
	h, err := ai.HavelAdminOverview(ctx, pool, svc)
	if err != nil {
		return o, h, nil, nil, nil, err
	}
	incidents, err := LoadIncidents(ctx, pool)
	if err != nil {
		return o, h, nil, nil, nil, err
	}
	reviews, err := LoadReviewAlerts(ctx, pool)
	if err != nil {
		return o, h, nil, nil, nil, err
	}
	owners, err := LoadOwners(ctx, pool)
	return o, h, incidents, reviews, owners, err
}

// Serve writes the page for the admin h, who has passed _require_admin.
func Serve(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time, h *session.Host) error {
	o, havel, incidents, reviews, owners, err := load(r.Context(), pool, getenv, at)
	if err != nil {
		return err
	}
	lang := tr(hostweb.Lang(r))
	data := buildView(lang, o, havel, incidents, reviews, owners)
	p := layout.Page{Title: lang.t("ops.title"), Nav: "operations", BodyKind: "detail", V2: true, AdminWorkspace: true}
	return layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, p, pages, "admin_operations", data)
}
