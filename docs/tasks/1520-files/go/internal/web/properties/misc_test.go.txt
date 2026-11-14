package properties

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

func TestRefererPath(t *testing.T) {
	cases := []struct{ referer, host, want string }{
		{"", "h.example", "/"},
		{"https://h.example/reservations?x=1#top", "h.example", "/reservations?x=1"},
		{"https://H.example:8443/a;p=1?q=2", "h.example:8000", "/a?q=2"},
		{"https://other.example/a", "h.example", "/"},
		{"/relative", "h.example", "/"},
		{"https://h.example", "h.example", "/"},
		{"https://h.example//evil", "h.example", "/"},
		{"https://h.example/a%20b", "h.example", "/a%20b"},
		{"https://h.example/a", "", "/"},
	}
	for _, c := range cases {
		req := httptest.NewRequest(http.MethodPost, "/x", nil)
		req.Host = c.host
		if c.referer != "" {
			req.Header.Set("Referer", c.referer)
		}
		if got := refererPath(req, "/"); got != c.want {
			t.Errorf("referer %q host %q: got %q, want %q", c.referer, c.host, got, c.want)
		}
	}
}

func TestDoorCodesEnabled(t *testing.T) {
	on := map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": " id ", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"}
	if !doorCodesEnabled(moreEnv(on)) {
		t.Error("enabled config reads as off")
	}
	for _, drop := range []string{"UBYHOST_DOOR_CODES", "UBYHOST_TTLOCK_CLIENT_ID", "UBYHOST_TTLOCK_CLIENT_SECRET"} {
		cp := map[string]string{}
		for k, v := range on {
			if k != drop {
				cp[k] = v
			}
		}
		if doorCodesEnabled(moreEnv(cp)) {
			t.Errorf("without %s it must be off", drop)
		}
	}
	for _, v := range []string{"0", "True", "YES", "on", ""} {
		cp := map[string]string{"UBYHOST_DOOR_CODES": v, "UBYHOST_TTLOCK_CLIENT_ID": "i", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"}
		if doorCodesEnabled(moreEnv(cp)) {
			t.Errorf("UBYHOST_DOOR_CODES=%q must be off (Python compares the exact strings 1, true, yes)", v)
		}
	}
}

func TestPragueDay(t *testing.T) {
	at := time.Date(2026, 11, 30, 23, 30, 0, 0, time.UTC) // already Dec 1 in Prague
	if got := pragueDay(at).Format("2006-01-02"); got != "2026-12-01" {
		t.Errorf("got %s", got)
	}
}

func TestMiscRegisterDoesNotTouchThePool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterMisc(mux, noWrap, nil, testEnv, testClock)
	if _, p := mux.Handler(httptest.NewRequest(http.MethodGet, "/menu", nil)); !strings.Contains(p, "/menu") {
		t.Errorf("pattern %q", p)
	}
}

func miscMux(pool *pgxpool.Pool, env map[string]string) *http.ServeMux {
	mux := http.NewServeMux()
	RegisterMisc(mux, noWrap, pool, moreEnv(env), testClock)
	return mux
}

// seedAlerts: ids 1xx belong to host A (130001), 2xx to host B.
func seedAlerts(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	seedHosts(t, pool)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, created_at) VALUES (130201, 130001, 'Flat A', $1), (130202, 130002, 'Flat B', $1)`, stamp0)
	for _, a := range []struct {
		id    int64
		owner int64
		kind  string
		apt   any
	}{
		{101, 130001, "calendar_error", nil},
		{102, 130001, "dates_changed_resign", nil},
		{103, 130001, "guest_pin_rotated", 130201},
		{104, 130001, "guest_pin_rotated", 130201},
		{105, 130001, "submission_outcome_unknown", 130201},
		{201, 130002, "calendar_error", nil},
		{202, 130002, "guest_pin_rotated", 130202},
	} {
		mustExec(t, pool, `INSERT INTO alert (id, level, kind, apartment_id, owner_user_id, message, created_at) VALUES ($1, 'warning', $2, $3, $4, 'm', $5)`,
			a.id, a.kind, a.apt, a.owner, stamp0)
	}
}

func alertState(t *testing.T, pool *pgxpool.Pool, id int64) (resolved bool, dismissed int64) {
	t.Helper()
	var at *string
	if err := pool.QueryRow(context.Background(), `SELECT resolved_at, user_dismissed FROM alert WHERE id = $1`, id).Scan(&at, &dismissed); err != nil {
		t.Fatal(err)
	}
	return at != nil, dismissed
}

// dismiss_alert (admin.py ~5216): every branch.
func TestDismissAlert(t *testing.T) {
	pool := testPool(t)
	seedAlerts(t, pool)
	mux := miscMux(pool, nil)
	req := func(path string, uid int64, hdr map[string]string) *httptest.ResponseRecorder {
		h := map[string]string{"Referer": "https://h.example/reservations?x=1"}
		for k, v := range hdr {
			h[k] = v
		}
		return postWithHost(t, mux, path, uid, "h.example", h)
	}

	// A plain dismissal: 303 to the Referer path, resolved with user_dismissed = 1.
	rec := req("/alerts/101/dismiss", 130001, nil)
	if r, d := alertState(t, pool, 101); !r || d != 1 {
		t.Fatalf("alert 101 resolved=%v dismissed=%d", r, d)
	}
	if loc := rec.Header().Get("Location"); loc != "/reservations?x=1" || rec.Code != http.StatusSeeOther {
		t.Errorf("plain dismissal: %d %q", rec.Code, loc)
	}

	// Another host's alert: 404 "No such alert." and nothing changes.
	rec = req("/alerts/201/dismiss", 130001, nil)
	if rec.Code != http.StatusNotFound || rec.Body.String() != "No such alert." || rec.Header().Get("Content-Type") != "" {
		t.Errorf("foreign alert: %d %q ct=%q", rec.Code, rec.Body.String(), rec.Header().Get("Content-Type"))
	}
	if r, _ := alertState(t, pool, 201); r {
		t.Error("a foreign alert was resolved")
	}
	// Unknown id and bad id.
	if rec = req("/alerts/999999/dismiss", 130001, nil); rec.Code != http.StatusNotFound {
		t.Errorf("unknown alert: %d", rec.Code)
	}
	if rec = req("/alerts/abc/dismiss", 130001, nil); rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("bad id: %d", rec.Code)
	}
	// Signed out: sent to the login page, nothing changes.
	if rec = req("/alerts/102/dismiss", 0, nil); rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}

	// dates_changed_resign is the filing gate: locked, with the error flash (303) or 409 for fetch.
	rec = req("/alerts/102/dismiss", 130001, nil)
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/reservations?x=1&err=") {
		t.Errorf("resign card: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = req("/alerts/102/dismiss", 130001, map[string]string{"X-Requested-With": "fetch"})
	if rec.Code != http.StatusConflict || rec.Body.Len() != 0 {
		t.Errorf("resign card fetch: %d %q", rec.Code, rec.Body.String())
	}
	if r, _ := alertState(t, pool, 102); r {
		t.Error("the resign card was resolved")
	}

	// guest_pin_rotated: one dismissal clears the host's other pin cards, not another host's.
	rec = req("/alerts/103/dismiss", 130001, map[string]string{"X-Requested-With": "fetch"})
	if rec.Code != http.StatusNoContent {
		t.Errorf("fetch dismissal: %d", rec.Code)
	}
	for id, want := range map[int64]bool{103: true, 104: true, 202: false} {
		if r, _ := alertState(t, pool, id); r != want {
			t.Errorf("alert %d resolved=%v want %v", id, r, want)
		}
	}

	// submission_outcome_unknown: dismissable while no guest points at an unknown batch.
	if rec = req("/alerts/105/dismiss", 130001, nil); rec.Code != http.StatusSeeOther {
		t.Errorf("unknown card: %d", rec.Code)
	}
	if r, _ := alertState(t, pool, 105); !r {
		t.Error("the unknown-outcome card should clear when nothing is in doubt")
	}
}

// The in-doubt branch of submission_outcome_unknown.
func TestDismissAlertInDoubt(t *testing.T) {
	pool := testPool(t)
	seedAlerts(t, pool)
	mustExec(t, pool, `INSERT INTO reservation (id, apartment_id, date_from, date_to, uid, status, created_at, updated_at) VALUES (130301, 130201, '2026-11-10', '2026-11-12', 'u1', 'active', $1, $1)`, stamp0)
	mustExec(t, pool, `INSERT INTO submission (id, apartment_id, state, created_at) VALUES (130401, 130201, 'outcome_unknown', $1)`, stamp0)
	mustExec(t, pool, `INSERT INTO guest (id, reservation_id, submission_id, submit_state, created_at, updated_at) VALUES (130501, 130301, 130401, 'pending', $1, $1)`, stamp0)
	mux := miscMux(pool, nil)
	rec := postWithHost(t, mux, "/alerts/105/dismiss", 130001, "h.example", map[string]string{"Referer": "https://h.example/dashboard"})
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/dashboard?err=") {
		t.Errorf("in doubt: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if r, _ := alertState(t, pool, 105); r {
		t.Error("the card was resolved while a batch is in doubt")
	}
	rec = postWithHost(t, mux, "/alerts/105/dismiss", 130001, "h.example", map[string]string{"X-Requested-With": "fetch"})
	if rec.Code != http.StatusConflict {
		t.Errorf("in doubt, fetch: %d", rec.Code)
	}
}

// smart_locks_page (admin.py ~712) with _lock_tab_url and _lock_property_return.
func TestSmartLocksRedirect(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, active, created_at) VALUES
		(130201, 130001, 'B flat', 1, $1), (130202, 130001, 'A off', 0, $1), (130203, 130002, 'Other', 1, $1)`, stamp0)
	on := map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "i", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"}
	loc := func(env map[string]string, path string, uid int64) string {
		rec := getAs(t, miscMux(pool, env), path, uid, 0, nil)
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("%s: status %d", path, rec.Code)
		}
		return rec.Header().Get("Location")
	}
	if got := loc(nil, "/smart-locks", 130001); !strings.HasPrefix(got, "/apartments?err=") {
		t.Errorf("switched off: %q", got)
	}
	// First active property by name, "how" anchor without a lock account.
	if got := loc(on, "/smart-locks", 130001); got != "/apartments/130201?view=settings&section=lock#smart-locks-how" {
		t.Errorf("no account: %q", got)
	}
	mustExec(t, pool, `INSERT INTO lock_account (id, owner_user_id, provider, username, created_at, updated_at) VALUES (130601, 130001, 'ttlock', 'x', $1, $1)`, stamp0)
	if got := loc(on, "/smart-locks", 130001); got != "/apartments/130201?view=settings&section=lock#smart-locks-list" {
		t.Errorf("with account: %q", got)
	}
	// return_to naming the host's own property wins; a foreign or odd one does not.
	for _, c := range []struct{ query, want string }{
		{"?return_to=/apartments/130202", "/apartments/130202?view=settings&section=lock&sec=lock#sec-lock"},
		{"?return_to=/apartments/130202/setup/door_lock", "/apartments/130202?view=settings&section=lock&sec=lock#sec-lock"},
		{"?return_to=/apartments/130202%3Fview%3Dx%23y", "/apartments/130202?view=settings&section=lock&sec=lock#sec-lock"},
		{"?return_to=/apartments/130203", "/apartments/130201?view=settings&section=lock#smart-locks-list"},
		{"?return_to=/apartments/130202/page", "/apartments/130201?view=settings&section=lock#smart-locks-list"},
		{"?return_to=https://evil.example/", "/apartments/130201?view=settings&section=lock#smart-locks-list"},
	} {
		if got := loc(on, "/smart-locks"+c.query, 130001); got != c.want {
			t.Errorf("%s: got %q want %q", c.query, got, c.want)
		}
	}
	// No active property at all.
	if got := loc(on, "/smart-locks", 130003); got != "/apartments" {
		t.Errorf("no property: %q", got)
	}
}

// menu_view (admin.py ~5257): month tiles count only this host's live, non-demo stays that overlap November.
func TestMenuPage(t *testing.T) {
	pool := testPool(t)
	seedHosts(t, pool)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, archived_at, created_at) VALUES
		(130201, 130001, 'Live', NULL, $1), (130202, 130001, 'Archived', $1, $1), (130203, 130002, 'Other', NULL, $1)`, stamp0)
	for _, r := range []struct {
		id        int64
		apt       int64
		from, to  string
		source    string
		guests    int
		sentCount int
	}{
		{1, 130201, "2026-11-10", "2026-11-12", "ical", 2, 1},
		{2, 130201, "2026-10-28", "2026-11-02", "manual", 1, 1}, // overlaps the month by one night
		{3, 130201, "2026-10-01", "2026-11-01", "manual", 3, 3}, // ends the day the month starts: out
		{4, 130201, "2026-11-20", "2026-11-22", "demo", 4, 4},
		{5, 130202, "2026-11-10", "2026-11-12", "manual", 5, 5},
		{6, 130203, "2026-11-10", "2026-11-12", "manual", 6, 6},
		{7, 130201, "2026-12-01", "2026-12-03", "manual", 7, 7},
	} {
		mustExec(t, pool, `INSERT INTO reservation (id, apartment_id, date_from, date_to, uid, source, status, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, 'active', $7, $7)`,
			130300+r.id, r.apt, r.from, r.to, "u"+string(rune('0'+r.id)), r.source, stamp0)
		for g := 0; g < r.guests; g++ {
			state := "pending"
			if g < r.sentCount {
				state = "sent"
			}
			mustExec(t, pool, `INSERT INTO guest (reservation_id, submit_state, created_at, updated_at) VALUES ($1, $2, $3, $3)`, 130300+r.id, state, stamp0)
		}
	}
	mustExec(t, pool, `UPDATE user_account SET display_name = 'élan' WHERE id = 130001`)
	mux := miscMux(pool, nil)
	rec := getAs(t, mux, "/menu", 130001, 0, nil)
	body := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	for _, want := range []string{
		`<a class="me-av" href="/settings" aria-label="Account">É</a>`,
		`<b>Guests</b><small>This month</small><span class="v">3</span>`,
		`<span class="v">2</span>`,
		`href="/cleaning"`, `action="/logout"`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("page lacks %q", want)
		}
	}
	if strings.Contains(body, `href="/admin"`) {
		t.Error("a host must not see the admin row")
	}
	// An admin inside a workspace still sees the admin row (current_user is the admin).
	if body = getAs(t, mux, "/menu", 130003, 130001, nil).Body.String(); !strings.Contains(body, `href="/admin"`) {
		t.Error("an admin should see the admin row")
	}
	if rec = getAs(t, mux, "/menu", 0, 0, nil); rec.Code != http.StatusSeeOther {
		t.Errorf("signed out: %d", rec.Code)
	}
}
