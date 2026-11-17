package opspage

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session/admingate"
)

// alertsHandler is what package auth's operationsAlerts does: _require_admin, then ServeAlerts.
func alertsHandler(pool *pgxpool.Pool, getenv func(string) string, now time.Time) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h, err := admingate.Require(w, r, pool, getenv, now)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		if h == nil {
			return
		}
		if err := ServeAlerts(w, r, pool, getenv, now, h); err != nil {
			http.Error(w, err.Error(), 500)
		}
	})
}

func getAlerts(t *testing.T, h http.Handler, query string, payload map[string]any, now time.Time) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("GET", "/admin/operations/alerts"+query, nil)
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	if payload != nil {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, now)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func execAll(t *testing.T, pool *pgxpool.Pool, stmts ...string) {
	t.Helper()
	for _, s := range stmts {
		if _, err := pool.Exec(context.Background(), s); err != nil {
			t.Fatal(err)
		}
	}
}

// TestAlertsDrillDown renders /admin/operations/alerts against a migrated
// test database with fake data: a linked stay, an alert without a stay, and
// an alert whose stay row is gone.
func TestAlertsDrillDown(t *testing.T) {
	g := loadGolden(t)
	now := goldenNow(t, g)
	pool := testPool(t)
	seed(t, pool, g, "full")
	execAll(t, pool,
		`INSERT INTO apartment (id, internal_name, active, created_at) VALUES (987001, 'Test flat A', 1, '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO reservation (id, apartment_id, uid, date_from, date_to, created_at, updated_at)
		 VALUES (987001, 987001, 'drill-test-1', '2026-07-01', '2026-07-05', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO guest (id, reservation_id, surname, first_name, is_lead, created_at, updated_at)
		 VALUES (987001, 987001, 'Testova', 'Eva', 1, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO alert (id, level, kind, reservation_id, message, created_at)
		 VALUES (987101, 'critical', 'deadline_at_risk', 987001, 'MSG-STAY-LINKED', '2026-07-01T10:00:00+00:00')`,
		`INSERT INTO alert (id, level, kind, apartment_id, message, created_at)
		 VALUES (987102, 'warning', 'feed_error', 987001, 'MSG-NO-STAY', '2026-07-02T10:00:00+00:00')`,
		`INSERT INTO alert (id, level, kind, reservation_id, message, created_at)
		 VALUES (987103, 'critical', 'deadline_at_risk', 987999, 'MSG-REMOVED', '2026-07-03T10:00:00+00:00')`,
	)
	h := alertsHandler(pool, testGetenv(g, nil), now)
	admin := map[string]any{"uid": 1, "sv": 1}

	rec := getAlerts(t, h, "", admin, now)
	if rec.Code != http.StatusOK {
		t.Fatalf("all: status %d: %s", rec.Code, rec.Body.String())
	}
	body := rec.Body.String()
	for _, want := range []string{"MSG-STAY-LINKED", "MSG-NO-STAY", "MSG-REMOVED", "Test flat A",
		`href="/reservations/987001"`, "Testova Eva 2026-07-01", "stay removed", ">none</td>"} {
		if !strings.Contains(body, want) {
			t.Errorf("all: body lacks %q", want)
		}
	}

	rec = getAlerts(t, h, "?kind=deadline_at_risk", admin, now)
	body = rec.Body.String()
	if rec.Code != http.StatusOK || !strings.Contains(body, "MSG-STAY-LINKED") || !strings.Contains(body, "MSG-REMOVED") {
		t.Errorf("kind filter: status %d, missing deadline rows", rec.Code)
	}
	if strings.Contains(body, "MSG-NO-STAY") {
		t.Errorf("kind filter: feed_error row leaked into deadline_at_risk")
	}

	rec = getAlerts(t, h, "?kind=no_such_kind&level=critical", admin, now)
	body = rec.Body.String()
	if rec.Code != http.StatusOK || strings.Contains(body, "MSG-") || !strings.Contains(body, "Nothing here.") {
		t.Errorf("unknown kind: status %d, want empty list with the none line", rec.Code)
	}

	execAll(t, pool, `INSERT INTO alert (id, level, kind, message, created_at)
		SELECT 987200 + i, 'info', 'cap_test', 'CAP', '2026-06-01T00:00:00+00:00' FROM generate_series(1, 203) AS i`)
	rec = getAlerts(t, h, "?kind=cap_test", admin, now)
	if !strings.Contains(rec.Body.String(), "Showing 200 of 203") {
		t.Errorf("cap: no 'Showing 200 of 203' line")
	}

	for i, doc := range []string{"terms", "privacy", "dpa"} { // host 2 has accepted, so the gate reaches the role check
		if _, err := pool.Exec(context.Background(), `INSERT INTO legal_acceptance (id, user_account_id, document, version,
			accepted_at, method) VALUES ($1, 2, $2, $3, '2026-01-01T00:00:00+00:00', 'clickwrap')`, 987301+i, doc, g.Versions[doc]); err != nil {
			t.Fatal(err)
		}
	}
	rec = getAlerts(t, h, "", map[string]any{"uid": 2, "sv": 1}, now)
	if rec.Code != http.StatusForbidden || rec.Body.String() != "Administrators only." {
		t.Errorf("host: %d %q, want the same denial as /admin/operations", rec.Code, rec.Body.String())
	}
}
