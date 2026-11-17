package opspage

// GET /admin/operations/alerts: the drill-down of the open-alerts table on the
// System page (brief 1800). The admin gate is the caller's, as for Serve.

import (
	"net/http"
	"sort"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// kindChip is one kind of the filter row.
type kindChip struct {
	Kind, Label string
	Count       int64
	Active      bool
}

// alertDetailView is one row of the drill-down table.
type alertDetailView struct {
	Level, KindLabel, Kind, Message, Property string
	StayID                                    int64
	HasStay, StayRemoved                      bool
	GuestName, DateFrom, DateTo               string
	Status, Age                               string
}

// alertsView is the data of admin_operations_alerts.tmpl.
type alertsView struct {
	Tabs        [][]any
	Level       string
	AllCount    int64
	AllActive   bool
	Kinds       []kindChip
	Rows        []alertDetailView
	ShowingLine string
}

// kindLabel is the ops.alert_kind.* label, or "" when the kind has none.
func kindLabel(lang tr, kind string) string {
	key := "ops.alert_kind." + kind
	label := lang.t(key)
	if label == key {
		return ""
	}
	return label
}

func buildAlertsView(lang tr, d AlertDetails, kind, level string) alertsView {
	v := alertsView{Tabs: adminTabs(lang), Level: level, AllCount: d.AllCount, AllActive: kind == ""}
	kinds := make([]string, 0, len(d.KindCounts))
	for k := range d.KindCounts {
		kinds = append(kinds, k)
	}
	sort.Slice(kinds, func(i, j int) bool {
		a, b := d.KindCounts[kinds[i]], d.KindCounts[kinds[j]]
		if a != b {
			return a > b
		}
		return kinds[i] < kinds[j]
	})
	for _, k := range kinds {
		v.Kinds = append(v.Kinds, kindChip{Kind: k, Label: kindLabel(lang, k), Count: d.KindCounts[k], Active: k == kind})
	}
	for _, a := range d.Rows {
		row := alertDetailView{Level: a.Level, KindLabel: kindLabel(lang, a.Kind), Kind: a.Kind,
			Message: a.Message, Property: a.Property, HasStay: a.ReservationID != nil,
			GuestName: a.GuestName, DateFrom: a.DateFrom, DateTo: a.DateTo,
			Status: lang.t("ops.alerts.status_open"), Age: lang.age(a.AgeMinutes)}
		if a.ReservationID != nil {
			row.StayID = *a.ReservationID
			row.StayRemoved = !a.StayFound
		}
		v.Rows = append(v.Rows, row)
	}
	if d.Total > int64(len(d.Rows)) {
		v.ShowingLine = lang.t("ops.alerts.showing", "n", len(d.Rows), "total", d.Total)
	}
	return v
}

// ServeAlerts writes the drill-down for the admin h, who has passed the admin gate.
func ServeAlerts(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time, h *session.Host) error {
	kind := r.URL.Query().Get("kind")
	level := r.URL.Query().Get("level")
	d, err := LoadAlertDetails(r.Context(), pool, at, kind, level)
	if err != nil {
		return err
	}
	lang := tr(hostweb.Lang(r))
	data := buildAlertsView(lang, d, kind, level)
	p := layout.Page{Title: lang.t("ops.alerts.page_title"), Nav: "operations", BodyKind: "detail", V2: true, AdminWorkspace: true}
	return layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, p, pages, "admin_operations_alerts", data)
}
