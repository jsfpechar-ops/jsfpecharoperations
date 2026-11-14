package ai

import (
	"context"
	"testing"
	"time"
)

var havelPragueZone, _ = time.LoadLocation("Europe/Prague")

func TestHavelWindowsAreWallClockSeconds(t *testing.T) {
	// The values come from the real Python (aware datetimes of one zone are
	// subtracted by their wall clock, so the daylight-saving change adds no hour).
	for _, c := range []struct {
		at          time.Time
		week, month int64
	}{
		{time.Date(2026, 3, 29, 12, 0, 0, 0, havelPragueZone), 561601, 2462401},
		{time.Date(2026, 3, 30, 10, 0, 0, 0, havelPragueZone), 36001, 2541601},
		{time.Date(2026, 10, 26, 9, 0, 0, 0, havelPragueZone), 32401, 2192401},
		{time.Date(2026, 11, 13, 12, 0, 0, 0, havelPragueZone), 388801, 1080001},
		{time.Date(2026, 11, 2, 0, 0, 0, 0, havelPragueZone), 1, 86401},
		{time.Date(2026, 11, 13, 11, 0, 0, 0, time.UTC), 388801, 1080001},
	} {
		if w, m := HavelSinceWeekStart(c.at), HavelSinceMonthStart(c.at); w != c.week || m != c.month {
			t.Errorf("%s: week %d month %d, Python %d %d", c.at, w, m, c.week, c.month)
		}
	}
}

func TestHavelGates(t *testing.T) {
	on := havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "guide_import, Havel", "UBYHOST_ANTHROPIC_API_KEY": "k"})
	if !HavelAIOn(on, "havel", "x@example.test") {
		t.Error("listed feature with a key is on")
	}
	if HavelAIOn(havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "havel"}), "havel", "") {
		t.Error("no key, no AI")
	}
	if HavelAIOn(havelMapEnv(map[string]string{"UBYHOST_ANTHROPIC_API_KEY": "k"}), "havel", "") {
		t.Error("feature not listed, no AI")
	}
	mistral := havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "havel", "UBYHOST_AI_PROVIDER": "mistral", "UBYHOST_ANTHROPIC_API_KEY": "k"})
	if HavelAIOn(mistral, "havel", "") {
		t.Error("the mistral provider needs the mistral key")
	}
	listed := havelMapEnv(map[string]string{"UBYHOST_AI_FEATURES": "havel", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_AI_TEST_EMAILS": " Anna@Example.test ,b@example.test"})
	if !HavelAIOn(listed, "havel", " anna@example.TEST ") || HavelAIOn(listed, "havel", "c@example.test") || HavelAIOn(listed, "havel", "") {
		t.Error("the test list limits AI to its e-mails, case and spaces ignored")
	}
	if !HavelBillingOn(havelMapEnv(map[string]string{"UBYHOST_BILLING_ENABLED": "Yes"})) || HavelBillingOn(havelMapEnv(nil)) {
		t.Error("billing switch")
	}
}

func TestHavelLimitsOnPostgres(t *testing.T) {
	pool := havelTestPool(t)
	ctx := context.Background()
	env := havelMapEnv(map[string]string{"UBYHOST_BILLING_ENABLED": "1"})
	store := HavelStore{Pool: pool, Env: env}
	now := time.Date(2026, 11, 13, 12, 0, 0, 0, havelPragueZone) // a Friday, week 388801 s old
	rec := func(scope string, n int, age time.Duration) {
		for i := 0; i < n; i++ {
			if err := store.Record(ctx, scope, "7", now.Add(-age)); err != nil {
				t.Fatal(err)
			}
		}
	}
	state := func(want string) {
		t.Helper()
		got, err := store.LimitState(ctx, 7, now)
		if err != nil || got != want {
			t.Fatalf("limit state %q (%v), want %q", got, err, want)
		}
	}
	state("") // billing on, no account row: base limits
	rec("havel_burst", 4, time.Minute)
	state("")
	rec("havel_burst", 1, time.Minute)
	state("limit_burst")
	rec("havel_burst", 5, 11*time.Minute) // past the 600 s window
	state("limit_burst")                  // the check deletes what is past its window, then counts
	var burst int
	_ = pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'havel_burst'`).Scan(&burst)
	if burst != 5 {
		t.Fatalf("%d burst rows left, want the 5 inside the window", burst)
	}
	havelExec(t, pool, `DELETE FROM rate_limit_event`)
	rec("havel_week", 7, 2*time.Hour)
	state("")
	rec("havel_week", 1, 2*time.Hour)
	state("limit_week")
	rec("havel_week", 3, 7*24*time.Hour) // older than the week: gone
	havelExec(t, pool, `DELETE FROM rate_limit_event`)
	rec("havel_month", 14, 24*time.Hour)
	state("")
	rec("havel_month", 1, 24*time.Hour)
	state("limit_month")
	rec("havel_refuse", 3, time.Hour)
	state("paused")
	havelExec(t, pool, `DELETE FROM rate_limit_event`)

	// Max scales the limits by 5; paused accounts have none.
	havelExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (7, 'h@example.test', 'x', 'host', '2026-01-01')`,
		`INSERT INTO billing_account (owner_user_id, status, plan, updated_at) VALUES (7, 'active', 'max', '2026-01-01')`)
	rec("havel_week", 8, time.Hour)
	state("")
	rec("havel_week", 32, time.Hour)
	state("limit_week")
	havelExec(t, pool, `DELETE FROM rate_limit_event`, `UPDATE billing_account SET status = 'paused'`)
	state("limit_week") // a multiplier of 0 blocks at once
	if m, _ := store.Multiplier(ctx, 7); m != 0 {
		t.Errorf("paused multiplier %d", m)
	}
	havelExec(t, pool, `UPDATE billing_account SET status = 'trialing'`)
	if m, _ := store.Multiplier(ctx, 7); m != 1 {
		t.Errorf("trial multiplier %d", m)
	}
	havelExec(t, pool, `UPDATE billing_account SET status = 'active', plan = 'standard'`)
	if m, _ := store.Multiplier(ctx, 7); m != 1 {
		t.Errorf("standard multiplier %d", m)
	}
	if m, _ := (HavelStore{Pool: pool, Env: havelMapEnv(nil)}).Multiplier(ctx, 7); m != 1 {
		t.Errorf("billing off multiplier %d", m)
	}
}

func TestHavelRecordsAndSupportCap(t *testing.T) {
	pool := havelTestPool(t)
	ctx := context.Background()
	store := HavelStore{Pool: pool, Env: havelMapEnv(nil)}
	now := time.Date(2026, 11, 13, 12, 0, 0, 0, havelPragueZone)
	if err := store.RecordMessage(ctx, 9, now); err != nil {
		t.Fatal(err)
	}
	if err := store.RecordRefusal(ctx, 9, now); err != nil {
		t.Fatal(err)
	}
	rows, _ := pool.Query(ctx, `SELECT scope, key, at FROM rate_limit_event ORDER BY id`)
	var got []string
	for rows.Next() {
		var scope, key string
		var at float64
		_ = rows.Scan(&scope, &key, &at)
		if key != "9" || at != float64(now.Unix()) {
			t.Errorf("event %s key %s at %v", scope, key, at)
		}
		got = append(got, scope)
	}
	if len(got) != 4 || got[0] != "havel_burst" || got[1] != "havel_week" || got[2] != "havel_month" || got[3] != "havel_refuse" {
		t.Errorf("record_message writes burst, week, month; record_refusal writes refuse: %v", got)
	}
	for i := 0; i < 2; i++ {
		_ = store.RecordSupport(ctx, 9, now)
	}
	if blocked, _ := store.SupportBlocked(ctx, 9, now); blocked {
		t.Error("two support mails a week are allowed")
	}
	_ = store.RecordSupport(ctx, 9, now)
	if blocked, _ := store.SupportBlocked(ctx, 9, now); !blocked {
		t.Error("the third support mail of a week blocks the next")
	}
	if blocked, _ := store.Blocked(ctx, "x", "", 100, 60, now); !blocked {
		t.Error("an empty key fails closed")
	}
}

func TestHavelStatsAndGapLog(t *testing.T) {
	pool := havelTestPool(t)
	ctx := context.Background()
	store := HavelStore{Pool: pool, Env: havelMapEnv(nil)}
	day := time.Date(2026, 11, 13, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		if err := store.RecordStat(ctx, "answer", day); err != nil {
			t.Fatal(err)
		}
	}
	_ = store.RecordStat(ctx, "refuse", day)
	var n int
	_ = pool.QueryRow(ctx, `SELECT count FROM havel_stats WHERE day = '2026-11-13' AND kind = 'answer'`).Scan(&n)
	if n != 3 {
		t.Errorf("stat count %d", n)
	}
	at := time.Date(2026, 11, 13, 15, 45, 30, 0, time.UTC)
	must := func(err error) {
		t.Helper()
		if err != nil {
			t.Fatal(err)
		}
	}
	must(store.RecordGap(ctx, "cs", "stays", "escalate", "  mail anna@example.test, tel +420 777 123 456  ", at))
	must(store.RecordGap(ctx, "", "nope", "fail", "How?", at))
	must(store.RecordGap(ctx, "vi-VN-x", "", "not_helped", "q", at))
	must(store.RecordGap(ctx, "en", "stays", "bogus", "kind not stored", at))
	must(store.RecordGap(ctx, "en", "stays", "fail", "   ", at))
	rows, _ := pool.Query(ctx, `SELECT created_at, lang, page, kind, question FROM havel_gap ORDER BY id`)
	type gap struct {
		created, lang, kind, question string
		page                          *string
	}
	var gaps []gap
	for rows.Next() {
		var g gap
		_ = rows.Scan(&g.created, &g.lang, &g.page, &g.kind, &g.question)
		gaps = append(gaps, g)
	}
	if len(gaps) != 3 {
		t.Fatalf("%d gap rows, want 3 (an unknown kind and an empty question are not stored)", len(gaps))
	}
	if gaps[0].created != "2026-11-13T00:00:00+00:00" || gaps[0].lang != "cs" || gaps[0].page == nil || *gaps[0].page != "stays" ||
		gaps[0].question != "mail [email 1], tel [phone 1]" {
		t.Errorf("gap 0: %+v", gaps[0])
	}
	if gaps[1].lang != "en" || gaps[1].page != nil || gaps[2].lang != "vi-VN" || gaps[2].page != nil {
		t.Errorf("gaps 1 and 2: %+v %+v", gaps[1], gaps[2])
	}
}
