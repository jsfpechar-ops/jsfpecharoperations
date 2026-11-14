package customers

import (
	"context"
	"fmt"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Tests of the counts behind the "System problems" list of GET /admin (brief 1592).
// The expected numbers are worked out by hand from admin_ops.py; each case names
// the Python rule it tests.

func mustExec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", sql, err)
	}
}

const stampOld = "2026-11-13T11:00:00+00:00"     // an hour before testNow
const stampFresh = "2026-11-13T11:45:00+00:00"   // 15 minutes before testNow
const stampStale3h = "2026-11-13T08:00:00+00:00" // four hours before testNow

// TestOpsCounts runs the six counts over rows chosen to sit on both sides of every rule.
func TestOpsCounts(t *testing.T) {
	pool := dbPool(t)
	const created = "2026-11-01T00:00:00+00:00"
	// Two active apartments and one archived one.
	for _, a := range []struct {
		name     string
		active   int
		archived any
	}{{"A1", 1, nil}, {"A2", 1, nil}, {"A3", 0, nil}, {"A4", 1, created}} {
		mustExec(t, pool, "INSERT INTO apartment (internal_name, active, archived_at, created_at) VALUES ($1, $2, $3, $4)", a.name, a.active, a.archived, created)
	}
	apt := func(name string) int64 {
		var id int64
		if err := pool.QueryRow(context.Background(), "SELECT id FROM apartment WHERE internal_name = $1", name).Scan(&id); err != nil {
			t.Fatal(err)
		}
		return id
	}
	stay := func(a int64, uid string, archived any) int64 {
		var id int64
		if err := pool.QueryRow(context.Background(), `INSERT INTO reservation (apartment_id, uid, date_from, date_to, created_at, updated_at, archived_at)
			VALUES ($1, $2, '2026-11-20', '2026-11-22', $3, $3, $4) RETURNING id`, a, uid, created, archived).Scan(&id); err != nil {
			t.Fatal(err)
		}
		return id
	}
	guest := func(stayID int64, state string, submission any, archived any) {
		mustExec(t, pool, `INSERT INTO guest (reservation_id, submit_state, submission_id, archived_at, created_at, updated_at)
			VALUES ($1, $2, $3, $4, $5, $5)`, stayID, state, submission, archived, created)
	}
	sub := func(a int64, state, at string) int64 {
		var id int64
		if err := pool.QueryRow(context.Background(), `INSERT INTO submission (apartment_id, created_at, state) VALUES ($1, $2, $3) RETURNING id`, a, at, state).Scan(&id); err != nil {
			t.Fatal(err)
		}
		return id
	}
	a1 := apt("A1")
	// Filings: a stay counts once however many guests are in trouble (admin_ops 80-124).
	r1, r2, r3, r4, r5, r6 := stay(a1, "1", nil), stay(a1, "2", nil), stay(a1, "3", nil), stay(a1, "4", nil), stay(a1, "5", created), stay(a1, "6", nil)
	guest(r1, "error", nil, nil)
	guest(r2, "blocked", nil, nil)
	guest(r2, "error", nil, nil)
	unknown := sub(a1, "outcome_unknown", stampFresh)
	guest(r3, "sent", unknown, nil)    // sent: not counted even under an unknown outcome
	guest(r3, "pending", unknown, nil) // pending under an unknown outcome: counted
	guest(r4, "error", nil, created)   // archived guest
	guest(r5, "error", nil, nil)       // archived stay
	guest(r6, "pending", nil, nil)     // nothing wrong
	// Stuck: running for over 30 minutes (127-157).
	sub(a1, "running", stampOld)
	sub(a1, "running", stampFresh)
	sub(a1, "sent", stampOld)
	// Feeds: active feed on an active, unarchived apartment, not ok or not checked for 3 hours (160-203).
	feed := func(apartment int64, active int, status, checked, synced any) {
		mustExec(t, pool, `INSERT INTO ical_feed (apartment_id, url, active, last_status, last_checked_at, last_sync_at, created_at)
			VALUES ($1, 'https://example.test/c.ics', $2, $3, $4, $5, $6)`, apartment, active, status, checked, synced, created)
	}
	feed(a1, 1, "ok", stampOld, nil)        // checked within 3 hours
	feed(a1, 1, "ok", stampStale3h, nil)    // counted: too old
	feed(a1, 1, nil, stampOld, nil)         // counted: never had a status
	feed(a1, 1, "error", stampOld, nil)     // counted: not ok
	feed(a1, 1, "ok", nil, nil)             // counted: never checked
	feed(a1, 0, "error", stampOld, nil)     // inactive feed
	feed(apt("A3"), 1, "error", nil, nil)   // inactive apartment
	feed(apt("A4"), 1, "error", nil, nil)   // archived apartment
	feed(apt("A2"), 1, "ok", nil, stampOld) // falls back to last_sync_at: fresh enough
	// Mail: failed, bounced, complained, queued or sending for over 30 minutes (245-274).
	n := 0
	mail := func(state, createdAt, updatedAt string) {
		n++
		mustExec(t, pool, `INSERT INTO email_outbox (idempotency_key, kind, state, created_at, updated_at) VALUES ($1, 'x', $2, $3, $4)`,
			fmt.Sprintf("ops-%d", n), state, createdAt, updatedAt)
	}
	mail("failed", stampFresh, stampFresh)
	mail("bounced", stampFresh, stampFresh)
	mail("complained", stampFresh, stampFresh)
	mail("queued", stampOld, stampOld)
	mail("queued", stampFresh, stampFresh)
	mail("sending", stampFresh, stampOld)
	mail("sending", stampOld, stampFresh)
	mail("sent", stampOld, stampOld)
	// Alerts: unresolved, summed over the first 50 groups of (kind, level) by count then kind (277-295).
	alert := func(kind, level string, resolved any, key any) {
		mustExec(t, pool, `INSERT INTO alert (level, kind, message, created_at, resolved_at, dedupe_key) VALUES ($1, $2, 'm', $3, $4, $5)`, level, kind, created, resolved, key)
	}
	for i := 0; i < 3; i++ {
		alert("a", "warning", nil, nil)
	}
	for i := 0; i < 2; i++ {
		alert("a", "info", nil, nil)
	}
	alert("a", "warning", created, nil) // resolved
	for i := 0; i < 60; i++ {
		alert(fmt.Sprintf("k%02d", i), "info", nil, nil)
	}
	// Jobs: no success on record, or older than twice the interval plus 15 minutes under 15 (206-242).
	last := func(job, value string) {
		mustExec(t, pool, "INSERT INTO settings (key, value) VALUES ($1, $2)", "job_last_ok:"+job, value)
	}
	for _, job := range []string{"submit", "door_codes", "posthog", "push", "guide_import", "stay_fee_mail", "stripe_sweep", "billing_snapshot", "meta_capi"} {
		last(job, stampFresh)
	}
	last("mail", "2026-11-13T11:30:00+00:00")      // 30 minutes old, threshold 25: late
	last("ical", "2026-11-13T10:59:00+00:00")      // 61 minutes old: late only when the interval is 30
	last("deadlines", "garbage")                   // not a time: late
	last("retention", "2026-11-11T13:00:00+00:00") // 47 hours old, threshold 48 hours: fine
	// photo_sweep has no row: late. posthog is fresh but has an open failure.
	alert("job_failed", "error", nil, "job_failed:posthog")
	alert("job_failed", "error", nil, "job_failed:mail") // late and failed: counted once
	alert("job_failed", "error", created, "job_failed:push")
	// Review alerts for the incidents line.
	alert("incident_review", "info", nil, nil)
	alert("incident_review", "info", nil, nil)
	alert("incident_review", "info", created, nil)

	env := func(extra map[string]string) func(string) string {
		return func(k string) string { return extra[k] }
	}
	got, err := Ops(context.Background(), pool, env(nil), testNow)
	if err != nil {
		t.Fatal(err)
	}
	// alerts: groups are a/warning 3, a/info 2, job_failed/error 2, incident_review/info 2 and 60 singles; the
	// first 50 groups by count then kind are the four above (3+2+2+2) and 46 singles.
	want := OpsCounts{Filings: 3, Stuck: 1, Feeds: 4, Jobs: 4, Mail: 5, Alerts: 9 + 46}
	if got != want {
		t.Errorf("counts %+v, want %+v", got, want)
	}
	// With UBYHOST_ICAL_POLL_MINUTES=30 the 61-minute-old ical success is late.
	got, err = Ops(context.Background(), pool, env(map[string]string{"UBYHOST_ICAL_POLL_MINUTES": "30"}), testNow)
	if err != nil || got.Jobs != 5 {
		t.Errorf("jobs with ical every 30 minutes: %d %v, want 5", got.Jobs, err)
	}
	if n, err := ReviewAlertCount(context.Background(), pool); err != nil || n != 2 {
		t.Errorf("review alerts %d %v, want 2", n, err)
	}
}

// TestOpsTimeHelpers pins admin_ops.parse_time and age_minutes.
func TestOpsTimeHelpers(t *testing.T) {
	cases := []struct {
		in   string
		want int
		ok   bool
	}{
		{"2026-11-13T11:00:00+00:00", 60, true}, {"2026-11-13T11:00:00Z", 60, true}, {" 2026-11-13T11:00:00 ", 60, true},
		{"2026-11-13 11:00:00", 60, true}, {"2026-11-13T12:00:00.5+00:00", 0, true}, {"2026-11-13T13:00:00+00:00", 0, true},
		{"2026-11-13T12:00:00+01:00", 60, true}, {"2026-11-13", 720, true}, {"", 0, false}, {"garbage", 0, false},
	}
	for _, c := range cases {
		got, ok := ageMinutes(c.in, testNow)
		if got != c.want || ok != c.ok {
			t.Errorf("ageMinutes(%q) = %d %v, want %d %v", c.in, got, ok, c.want, c.ok)
		}
	}
	for interval, want := range map[int]int{1: 17, 10: 35, 14: 43, 15: 30, 60: 120, 1440: 2880} {
		if got := lateAfterMinutes(interval); got != want {
			t.Errorf("lateAfterMinutes(%d) = %d, want %d", interval, got, want)
		}
	}
}
