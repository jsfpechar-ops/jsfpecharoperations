package calendar

import (
	"context"
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

func TestFilingStalledRaisesAndMailsOncePerDay(t *testing.T) {
	ctx := context.Background()
	pool, g := stalledSeed(t)
	at := stalledLimit(t, pool).Add(time.Hour)
	getenv := watchdogGetenv(g.Env)
	res, err := RunFilingStalled(ctx, pool, getenv, at)
	if err != nil || res.Stalled != 1 || res.Alerts != 1 {
		t.Fatalf("first run %+v, err %v", res, err)
	}
	var level string
	if err := pool.QueryRow(ctx,
		`SELECT level FROM alert WHERE dedupe_key = 'filing_stalled:1' AND resolved_at IS NULL`).Scan(&level); err != nil || level != "critical" {
		t.Fatalf("alert level %q, err %v", level, err)
	}
	count := func() int {
		var n int
		if err := pool.QueryRow(ctx,
			`SELECT count(*) FROM email_outbox WHERE kind IN ('filing_stalled', 'filing_stalled_operator')`).Scan(&n); err != nil {
			t.Fatal(err)
		}
		return n
	}
	first := count()
	if _, err := RunFilingStalled(ctx, pool, getenv, at.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if count() != first {
		t.Fatalf("second run the same day queued mail: %d -> %d", first, count())
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
