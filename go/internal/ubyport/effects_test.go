package ubyport

import (
	"context"
	"fmt"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"
)

const effectsTS = "2026-11-01T00:00:00+00:00"

// effectsSeed inserts one owner, an apartment that owner holds, one reservation
// and one guest. It returns their ids.
func effectsSeed(t *testing.T, pool *pgxpool.Pool) (owner, apt, res, guest int64) {
	t.Helper()
	ctx := context.Background()
	if err := pool.QueryRow(ctx,
		`INSERT INTO user_account (username, password_hash, created_at) VALUES ($1, $2, $3) RETURNING id`,
		"owner-effects", "not-a-hash", effectsTS).Scan(&owner); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO apartment (internal_name, owner_user_id, created_at) VALUES ($1, $2, $3) RETURNING id`,
		"Effects flat", owner, effectsTS).Scan(&apt); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $5) RETURNING id`,
		apt, "uid-effects", "2026-12-01", "2026-12-03", effectsTS).Scan(&res); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, created_at, updated_at) VALUES ($1, $2, $2) RETURNING id`,
		res, effectsTS).Scan(&guest); err != nil {
		t.Fatal(err)
	}
	return owner, apt, res, guest
}

// effectsText returns one text column of the first row (SQL NULL is "<nil>").
func effectsText(t *testing.T, pool *pgxpool.Pool, query string, args ...any) string {
	t.Helper()
	var v *string
	if err := pool.QueryRow(context.Background(), query, args...).Scan(&v); err != nil {
		t.Fatal(err)
	}
	if v == nil {
		return "<nil>"
	}
	return *v
}

// effectsCount returns one count query.
func effectsCount(t *testing.T, pool *pgxpool.Pool, query string, args ...any) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), query, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestEffectsRaiseTwiceOneRow(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, apt, _, _ := effectsSeed(t, pool)
	if err := RaiseAlert(ctx, pool, "warning", "kind_a", "first", "d1", "key-a", &apt, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if err := RaiseAlert(ctx, pool, "error", "kind_a", "second", "d2", "key-a", &apt, nil, nil,
		AlertParams{"count": 2, "property": "Byt á<1>"}); err != nil {
		t.Fatal(err)
	}
	const open = `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`
	if n := effectsCount(t, pool, open, "key-a"); n != 1 {
		t.Fatalf("open alerts: want 1, got %d", n)
	}
	if got := effectsText(t, pool, `SELECT message FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, "key-a"); got != "second" {
		t.Fatalf("message: got %q", got)
	}
	if got := effectsText(t, pool, `SELECT level FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, "key-a"); got != "error" {
		t.Fatalf("level: got %q", got)
	}
}

func TestEffectsParamsBytes(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, apt, _, _ := effectsSeed(t, pool)
	if err := RaiseAlert(ctx, pool, "warning", "kind_p", "msg", "", "key-p", &apt, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	// Overwrite with params: the refresh path stores them too.
	if err := RaiseAlert(ctx, pool, "warning", "kind_p", "msg", "", "key-p", &apt, nil, nil,
		AlertParams{"property": "Byt á<1>", "count": 2}); err != nil {
		t.Fatal(err)
	}
	want := `{"count": 2, "property": "Byt á<1>"}`
	if got := effectsText(t, pool, `SELECT params FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, "key-p"); got != want {
		t.Fatalf("params: got %q want %q", got, want)
	}
}

func TestEffectsBadParamWritesNothing(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, apt, _, _ := effectsSeed(t, pool)
	if err := RaiseAlert(ctx, pool, "warning", "kind_x", "msg", "", "key-bad", &apt, nil, nil,
		AlertParams{"ratio": 1.5}); err == nil {
		t.Fatal("want error for float param")
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`, "key-bad"); n != 0 {
		t.Fatalf("rows written: %d", n)
	}
}

func TestEffectsResolveThenRaise(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, apt, _, _ := effectsSeed(t, pool)
	if err := RaiseAlert(ctx, pool, "warning", "kind_r", "one", "", "key-r", &apt, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if err := ResolveAlert(ctx, pool, "key-r"); err != nil {
		t.Fatal(err)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NOT NULL`, "key-r"); n != 1 {
		t.Fatalf("resolved rows: want 1, got %d", n)
	}
	if err := RaiseAlert(ctx, pool, "warning", "kind_r", "two", "", "key-r", &apt, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, "key-r"); n != 1 {
		t.Fatalf("open rows: want 1, got %d", n)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`, "key-r"); n != 2 {
		t.Fatalf("total rows: want 2, got %d", n)
	}
}

func TestEffectsOwnerFromApartmentAndReservation(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	owner, apt, res, _ := effectsSeed(t, pool)
	if err := RaiseAlert(ctx, pool, "warning", "kind_o", "m", "", "key-o-apt", &apt, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if got := effectsText(t, pool, `SELECT owner_user_id::text FROM alert WHERE dedupe_key = $1`, "key-o-apt"); got != fmt.Sprint(owner) {
		t.Fatalf("owner from apartment: got %q", got)
	}
	if err := RaiseAlert(ctx, pool, "warning", "kind_o", "m", "", "key-o-res", nil, &res, nil, nil); err != nil {
		t.Fatal(err)
	}
	if got := effectsText(t, pool, `SELECT owner_user_id::text FROM alert WHERE dedupe_key = $1`, "key-o-res"); got != fmt.Sprint(owner) {
		t.Fatalf("owner from reservation: got %q", got)
	}
}

func TestEffectsKeyFallbackPrintsNone(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	if err := RaiseAlert(ctx, pool, "info", "kind_b", "msg-b", "", "", nil, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`, "kind_b:None:None:msg-b"); n != 1 {
		t.Fatalf("fallback key rows: want 1, got %d", n)
	}
}

func TestEffectsAuditRow(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	owner, _, _, _ := effectsSeed(t, pool)
	if err := Audit(ctx, pool, "submit_batch", "3 guests", &owner); err != nil {
		t.Fatal(err)
	}
	var at, actor, action, detail string
	var ownerID *int64
	var actorNull, impersonatorNull bool
	if err := pool.QueryRow(ctx,
		`SELECT at, actor, action, detail, owner_user_id, actor_user_id IS NULL, impersonator_user_id IS NULL
		 FROM audit ORDER BY id DESC LIMIT 1`).Scan(&at, &actor, &action, &detail, &ownerID, &actorNull, &impersonatorNull); err != nil {
		t.Fatal(err)
	}
	if actor != "host" || action != "submit_batch" || detail != "3 guests" {
		t.Fatalf("audit fields: actor=%q action=%q detail=%q", actor, action, detail)
	}
	if ownerID == nil || *ownerID != owner {
		t.Fatalf("audit owner: got %v", ownerID)
	}
	if !actorNull || !impersonatorNull {
		t.Fatal("audit user ids must be NULL")
	}
	if len(at) != len(effectsTS) {
		t.Fatalf("audit time format: %q", at)
	}
}

func TestEffectsApartmentInDoubt(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, apt, _, guest := effectsSeed(t, pool)
	before, err := ApartmentInDoubt(ctx, pool, apt)
	if err != nil {
		t.Fatal(err)
	}
	if before {
		t.Fatal("no submission yet: want false")
	}
	sub, err := InsertSubmission(ctx, pool, apt, "auto", []int64{guest}, "https://example.test/endpoint", effectsTS)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE submission SET state = 'outcome_unknown' WHERE id = $1`, sub); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submission_id = $1 WHERE id = $2`, sub, guest); err != nil {
		t.Fatal(err)
	}
	inDoubt, err := ApartmentInDoubt(ctx, pool, apt)
	if err != nil {
		t.Fatal(err)
	}
	if !inDoubt {
		t.Fatal("guest on outcome_unknown submission: want true")
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET archived_at = $1 WHERE id = $2`, effectsTS, guest); err != nil {
		t.Fatal(err)
	}
	inDoubt, err = ApartmentInDoubt(ctx, pool, apt)
	if err != nil {
		t.Fatal(err)
	}
	if inDoubt {
		t.Fatal("archived guest must be ignored: want false")
	}
}

func TestEffectsClearStuckIfRecovered(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	_, apt, res, guest := effectsSeed(t, pool)
	key := fmt.Sprintf("submission_stuck:%d", res)
	if err := RaiseAlert(ctx, pool, "error", "submission_stuck", "stuck", "", key, &apt, &res, nil, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'error', submit_attempts = $1 WHERE id = $2`,
		SubmissionMaxAutoAttempts, guest); err != nil {
		t.Fatal(err)
	}
	if err := ClearStuckIfRecovered(ctx, pool, res); err != nil {
		t.Fatal(err)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key); n != 1 {
		t.Fatalf("still stranded: alert must stay open, open rows = %d", n)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'ok' WHERE id = $1`, guest); err != nil {
		t.Fatal(err)
	}
	if err := ClearStuckIfRecovered(ctx, pool, res); err != nil {
		t.Fatal(err)
	}
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key); n != 0 {
		t.Fatalf("recovered: alert must be resolved, open rows = %d", n)
	}
}
