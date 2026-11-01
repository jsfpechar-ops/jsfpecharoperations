package ubyport

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// recoverNow pins the clock of the recovery tests.
func recoverNow() time.Time { return time.Date(2026, 11, 1, 12, 0, 0, 0, time.UTC) }

const recoverStamp = "2026-11-01T12:00:00+00:00"

// addGuestLike adds a guest in the same stay as guest like.
func addGuestLike(t *testing.T, pool *pgxpool.Pool, like int64) int64 {
	t.Helper()
	var id int64
	if err := pool.QueryRow(context.Background(),
		`INSERT INTO guest (reservation_id, created_at, updated_at)
		 SELECT reservation_id, created_at, created_at FROM guest WHERE id = $1 RETURNING id`,
		like).Scan(&id); err != nil {
		t.Fatal(err)
	}
	return id
}

func TestRecoverLiveClaimLeftAlone(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	apt := storeApartmentOf(t, pool, g1)
	sub, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g1}, "ep", recoverStamp)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'live', $2)`,
		g1, float64(recoverNow().Unix())-10); err != nil {
		t.Fatal(err)
	}
	n, err := RecoverStaleSubmissions(ctx, pool, apt, recoverNow)
	if err != nil || n != 0 {
		t.Fatalf("live claim: n=%d err=%v", n, err)
	}
	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "running" {
		t.Fatalf("live claim: state %q", st)
	}
	if c := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`,
		fmt.Sprintf("submission_outcome_unknown:%d", apt)); c != 0 {
		t.Fatalf("live claim raised %d alerts", c)
	}
}

func TestRecoverStaleBatches(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	g1 := seedGuest(t, pool)
	apt := storeApartmentOf(t, pool, g1)
	g2 := addGuestLike(t, pool, g1) // sent: must not be pointed at the stale batch
	g4 := addGuestLike(t, pool, g1) // already on a newer batch: must keep it

	// subA: old claim on g1, so stale. Its guest g2 is sent.
	subA, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g1, g2}, "ep", recoverStamp)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'sent' WHERE id = $1`, g2); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'old', $2)`,
		g1, float64(recoverNow().Unix())-600); err != nil {
		t.Fatal(err)
	}
	// subB: empty guest list is always stale.
	subB, err := InsertSubmission(ctx, pool, apt, "auto", []int64{}, "ep", recoverStamp)
	if err != nil {
		t.Fatal(err)
	}
	// subE: running with no claim, so stale; g4 has moved on to subF.
	subE, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g4}, "ep", recoverStamp)
	if err != nil {
		t.Fatal(err)
	}
	subF, err := InsertSubmission(ctx, pool, apt, "auto", []int64{}, "ep", recoverStamp)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE submission SET state = 'sent' WHERE id = $1`, subF); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submission_id = $1 WHERE id = $2`, subF, g4); err != nil {
		t.Fatal(err)
	}

	n, err := RecoverStaleSubmissions(ctx, pool, apt, recoverNow)
	if err != nil || n != 3 {
		t.Fatalf("stale: n=%d err=%v", n, err)
	}
	for _, sub := range []int64{subA, subB, subE} {
		row := storeRead(t, pool, "submission", sub, "state", "error_text", "finished_at")
		if row["state"] != "outcome_unknown" || row["error_text"] != staleSubmissionReason || row["finished_at"] == "" {
			t.Fatalf("submission %d: %v", sub, row)
		}
	}
	if got := storeRead(t, pool, "guest", g1, "submission_id")["submission_id"]; got != fmt.Sprint(subA) {
		t.Fatalf("g1 points at %q, want %d", got, subA)
	}
	if got := storeRead(t, pool, "guest", g2, "submission_id")["submission_id"]; got != "<nil>" {
		t.Fatalf("sent g2 was pointed at %q", got)
	}
	if got := storeRead(t, pool, "guest", g4, "submission_id")["submission_id"]; got != fmt.Sprint(subF) {
		t.Fatalf("g4 moved from newer batch to %q", got)
	}

	key := fmt.Sprintf("submission_outcome_unknown:%d", apt)
	if c := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL AND level = 'critical' AND kind = 'submission_outcome_unknown'`, key); c != 1 {
		t.Fatalf("want one critical alert, got %d", c)
	}
	want, err := pyJSONParams(AlertParams{"property": "Test flat", "error": staleSubmissionReason})
	if err != nil {
		t.Fatal(err)
	}
	if p := effectsText(t, pool, `SELECT params FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key); p != *want {
		t.Fatalf("params %q, want %q", p, *want)
	}

	// Nothing running now: nothing stale, no new work.
	if n, err := RecoverStaleSubmissions(ctx, pool, apt, recoverNow); err != nil || n != 0 {
		t.Fatalf("second run: n=%d err=%v", n, err)
	}
}

// TestReportingTodayIsUTCDate pins the day the completeness checks use: 23:30 UTC
// is already the next day in Prague, but the UTC date is the one that counts.
func TestReportingTodayIsUTCDate(t *testing.T) {
	late := time.Date(2026, 11, 1, 23, 30, 0, 0, time.UTC)
	if got := reportingToday(late); !got.Equal(time.Date(2026, 11, 1, 0, 0, 0, 0, time.UTC)) {
		t.Fatalf("reportingToday(23:30 UTC) = %v", got)
	}
}
