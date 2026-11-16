package calendar

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// stalledSeed loads the watchdog golden seed with only stay 201 live, on a
// scheduled property (the same scenario as TestRunFilingWatchdogPagesOnlyForFailedSends).
func stalledSeed(t *testing.T) (*pgxpool.Pool, watchdogRunGolden) {
	t.Helper()
	ctx := context.Background()
	g := loadWatchdogRunGolden(t)
	pool := dbPool(t)
	watchSeed(t, pool, watchGolden{Seed: g.Seed})
	if _, err := pool.Exec(ctx, `UPDATE reservation SET archived_at = '2026-09-16' WHERE id != 201`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE apartment SET automation_mode = 'scheduled' WHERE id = 1`); err != nil {
		t.Fatal(err)
	}
	return pool, g
}

// stalledLimit is the instant the alarm starts: deadline minus 6 h (cap) plus 3 h (grace).
func stalledLimit(t *testing.T, pool *pgxpool.Pool) time.Time {
	t.Helper()
	var d string
	if err := pool.QueryRow(context.Background(),
		`SELECT date_from::text FROM reservation WHERE id = 201`).Scan(&d); err != nil {
		t.Fatal(err)
	}
	anchor, ok, err := watchAnchor(context.Background(), pool, stayRow{id: 201, dateFrom: d})
	if err != nil || !ok {
		t.Fatalf("anchor: ok=%v err=%v", ok, err)
	}
	wall := deadlines.ReportingDeadline(anchor).Add(-filingStalledCapHours*time.Hour + filingStalledGrace)
	// The deadlines are naive Prague wall clock; StalledProperties takes an instant.
	prague, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		t.Fatal(err)
	}
	return time.Date(wall.Year(), wall.Month(), wall.Day(), wall.Hour(), wall.Minute(), wall.Second(), 0, prague)
}

// stalledKeys counts the outbox rows queued under the host and operator keys of a day.
func stalledKeys(t *testing.T, pool *pgxpool.Pool, id int64, day string) (host, op int) {
	t.Helper()
	ctx := context.Background()
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM email_outbox WHERE idempotency_key = $1`,
		fmt.Sprintf("filing_stalled:%d:%s", id, day)).Scan(&host); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM email_outbox WHERE idempotency_key = $1`,
		fmt.Sprintf("filing_stalled_operator:%d:%s", id, day)).Scan(&op); err != nil {
		t.Fatal(err)
	}
	return host, op
}

func stalledDay(at time.Time) string { return deadlines.LocalNow(at).Format("2006-01-02") }

func TestFilingStalledWaitsForCapPlusGrace(t *testing.T) {
	ctx := context.Background()
	pool, _ := stalledSeed(t)
	limit := stalledLimit(t, pool)
	before, err := StalledProperties(ctx, pool, limit.Add(-time.Minute))
	if err != nil || len(before) != 0 {
		t.Fatalf("before limit: %d props, err %v", len(before), err)
	}
	after, err := StalledProperties(ctx, pool, limit.Add(time.Minute))
	if err != nil || len(after) != 1 || after[0].ApartmentID != 1 || after[0].Stalled != 1 {
		t.Fatalf("after limit: %+v, err %v", after, err)
	}
}

// Exactly one host row and one operator row per property and Prague day; a
// repeat on the same day queues nothing; the next day queues one more of each.
func TestFilingStalledExactMailCountPerDay(t *testing.T) {
	ctx := context.Background()
	pool, g := stalledSeed(t)
	getenv := watchdogGetenv(g.Env)
	at := stalledLimit(t, pool).Add(time.Hour)
	day := stalledDay(at)
	res, err := RunFilingStalled(ctx, pool, getenv, at)
	if err != nil || res.Stalled != 1 || res.Alerts != 1 || res.Mailed != 1 {
		t.Fatalf("first run %+v, err %v", res, err)
	}
	if h, o := stalledKeys(t, pool, 1, day); h != 1 || o != 1 {
		t.Fatalf("first day rows host=%d operator=%d, want 1 and 1", h, o)
	}
	res, err = RunFilingStalled(ctx, pool, getenv, at.Add(time.Hour))
	if err != nil || res.Mailed != 0 {
		t.Fatalf("same-day rerun %+v, err %v", res, err)
	}
	if h, o := stalledKeys(t, pool, 1, day); h != 1 || o != 1 {
		t.Fatalf("same-day rerun rows host=%d operator=%d, want 1 and 1", h, o)
	}
	next := at.Add(24 * time.Hour)
	res, err = RunFilingStalled(ctx, pool, getenv, next)
	if err != nil || res.Mailed != 1 {
		t.Fatalf("next-day run %+v, err %v", res, err)
	}
	if h, o := stalledKeys(t, pool, 1, stalledDay(next)); h != 1 || o != 1 {
		t.Fatalf("next day rows host=%d operator=%d, want 1 and 1", h, o)
	}
}

// The cause of each stalled property, as the alarm and the mail name it.
func TestFilingStalledCauses(t *testing.T) {
	cases := []struct {
		name         string
		setup        string
		alert        string
		level        string
		noSetupAlert bool
		want         string
		wantAlerts   int
	}{
		{name: "auth", alert: "ubyport_auth_failed:1", level: "critical", want: "auth", wantAlerts: 1},
		{name: "failed", alert: "submission_transport:1", level: "critical", want: "failed", wantAlerts: 1},
		{name: "manual", setup: "UPDATE apartment SET automation_mode = 'manual' WHERE id = 1", want: "manual", wantAlerts: 1},
		{name: "setup alert gives no filing alert", alert: "apartment_setup:1", level: "critical", want: "setup", wantAlerts: 0},
		{name: "cleared password with setup alert", setup: "UPDATE apartment SET uby_ws_password_enc = '' WHERE id = 1", alert: "apartment_setup:1", level: "critical", want: "setup", wantAlerts: 0},
		{name: "no cause", want: "", wantAlerts: 1},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ctx := context.Background()
			pool, g := stalledSeed(t)
			if c.setup != "" {
				if _, err := pool.Exec(ctx, c.setup); err != nil {
					t.Fatal(err)
				}
			}
			if c.alert != "" {
				if _, err := pool.Exec(ctx, `INSERT INTO alert (id, level, kind, apartment_id, dedupe_key, message, created_at)
					VALUES (9201, $2, split_part($1, ':', 1), 1, $1, 'x', '2026-09-16T00:00:00+00:00')`, c.alert, c.level); err != nil {
					t.Fatal(err)
				}
			}
			at := stalledLimit(t, pool).Add(time.Hour)
			props, err := StalledProperties(ctx, pool, at)
			if err != nil || len(props) != 1 || props[0].Cause != c.want {
				t.Fatalf("props %+v, err %v; want cause %q", props, err, c.want)
			}
			res, err := RunFilingStalled(ctx, pool, watchdogGetenv(g.Env), at)
			if err != nil || res.Alerts != c.wantAlerts {
				t.Fatalf("alerts %+v, err %v; want %d", res, err, c.wantAlerts)
			}
		})
	}
}

// An apartment_setup alert that is critical while a guest waits mails before the
// cap; the warning level does not. The alarm itself is left to the setup alert.
func TestFilingStalledMailsCriticalSetupBeforeCap(t *testing.T) {
	ctx := context.Background()
	pool, g := stalledSeed(t)
	at := stalledLimit(t, pool).Add(-24 * time.Hour)
	if _, err := pool.Exec(ctx, `INSERT INTO alert (id, level, kind, apartment_id, dedupe_key, message, created_at)
		VALUES (9201, 'warning', 'apartment_setup', 1, 'apartment_setup:1', 'x', '2026-09-16T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	if props, err := StalledProperties(ctx, pool, at); err != nil || len(props) != 0 {
		t.Fatalf("warning setup before cap listed: %+v, err %v", props, err)
	}
	if _, err := pool.Exec(ctx, `UPDATE alert SET level = 'critical' WHERE id = 9201`); err != nil {
		t.Fatal(err)
	}
	props, err := StalledProperties(ctx, pool, at)
	if err != nil || len(props) != 1 || props[0].Stalled != 0 || props[0].Pending < 1 || props[0].Cause != "setup" {
		t.Fatalf("critical setup before cap: %+v, err %v", props, err)
	}
	res, err := RunFilingStalled(ctx, pool, watchdogGetenv(g.Env), at)
	if err != nil || res.Alerts != 0 || res.Mailed != 1 {
		t.Fatalf("run before cap %+v, err %v", res, err)
	}
	if h, _ := stalledKeys(t, pool, 1, stalledDay(at)); h != 1 {
		t.Fatalf("host rows before cap = %d, want 1", h)
	}
}

func TestFilingStalledResolvesWhenFiled(t *testing.T) {
	ctx := context.Background()
	pool, g := stalledSeed(t)
	at := stalledLimit(t, pool).Add(time.Hour)
	if _, err := RunFilingStalled(ctx, pool, watchdogGetenv(g.Env), at); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'sent' WHERE reservation_id = 201`); err != nil {
		t.Fatal(err)
	}
	res, err := RunFilingStalled(ctx, pool, watchdogGetenv(g.Env), at.Add(time.Hour))
	if err != nil || res.Stalled != 0 {
		t.Fatalf("after filing %+v, err %v", res, err)
	}
	var open int
	if err := pool.QueryRow(ctx,
		`SELECT count(*) FROM alert WHERE dedupe_key = 'filing_stalled:1' AND resolved_at IS NULL`).Scan(&open); err != nil || open != 0 {
		t.Fatalf("alert still open: %d, err %v", open, err)
	}
}

func TestFilingStalledSkipsPropertyWithoutPoliceFields(t *testing.T) {
	ctx := context.Background()
	pool, _ := stalledSeed(t)
	limit := stalledLimit(t, pool)
	if _, err := pool.Exec(ctx, `UPDATE apartment SET uby_idub = '', uby_ws_user = '', uby_ws_password_enc = '', uby_mark = '' WHERE id = 1`); err != nil {
		t.Fatal(err)
	}
	props, err := StalledProperties(ctx, pool, limit.Add(time.Hour))
	if err != nil || len(props) != 0 {
		t.Fatalf("property without police fields listed: %+v, err %v", props, err)
	}
}
