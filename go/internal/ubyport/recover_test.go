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

// refreshFixture makes a stay with filed hand-filed guests and blank (reportable,
// incomplete) guests, the declared headcount, the guests' stamp and a stored stamp.
func refreshFixture(t *testing.T, pool *pgxpool.Pool, declared any, filed, blank int, updated string, existing any) int64 {
	t.Helper()
	ctx := context.Background()
	first := seedGuest(t, pool)
	var res int64
	if err := pool.QueryRow(ctx, `SELECT reservation_id FROM guest WHERE id = $1`, first).Scan(&res); err != nil {
		t.Fatal(err)
	}
	guests := []int64{first}
	for i := 1; i < filed+blank; i++ {
		guests = append(guests, addGuestLike(t, pool, first))
	}
	for i, g := range guests {
		if i < filed {
			if _, err := pool.Exec(ctx,
				`UPDATE guest SET submit_state = 'sent', manual_filed_at = $2, updated_at = $3 WHERE id = $1`,
				g, recoverStamp, updated); err != nil {
				t.Fatal(err)
			}
		} else if _, err := pool.Exec(ctx,
			`UPDATE guest SET nationality = 'DE', updated_at = $2 WHERE id = $1`, g, updated); err != nil {
			t.Fatal(err)
		}
	}
	if _, err := pool.Exec(ctx,
		`UPDATE reservation SET declared_guests = $2, registration_completed_at = $3 WHERE id = $1`,
		res, declared, existing); err != nil {
		t.Fatal(err)
	}
	return res
}

func TestRefreshRegistrationCompletedAt(t *testing.T) {
	const (
		quiet  = "2026-10-31T23:00:00+00:00" // 13 hours before the pinned clock
		recent = "2026-11-01T11:00:00+00:00" // 1 hour before it
		old    = "2026-10-30T10:00:00+00:00"
	)
	cases := []struct {
		name         string
		declared     any
		filed, blank int
		updated      string
		existing     any
		want         string // "" nil, "new" any new stamp, else that stored value
	}{
		{"declared count reached", 2, 2, 0, recent, nil, "new"},
		{"quiet after 12 hours", nil, 2, 0, quiet, nil, "new"},
		{"not yet quiet", nil, 2, 0, recent, nil, ""},
		{"incomplete guest clears stamp", 2, 1, 1, recent, old, ""},
		{"complete stay keeps stamp", 2, 2, 0, recent, old, old},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			pool := claimTestPool(t)
			res := refreshFixture(t, pool, c.declared, c.filed, c.blank, c.updated, c.existing)
			got, err := RefreshRegistrationCompletedAt(context.Background(), pool, res, nil, recoverNow)
			if err != nil {
				t.Fatal(err)
			}
			col := storeRead(t, pool, "reservation", res, "registration_completed_at")["registration_completed_at"]
			switch c.want {
			case "":
				if got != nil || col != "<nil>" {
					t.Fatalf("want no stamp, got %v, column %q", got, col)
				}
			case "new":
				if got == nil || *got == "" || col != *got {
					t.Fatalf("want a new stamp, got %v, column %q", got, col)
				}
			default:
				if got == nil || *got != c.want || col != c.want {
					t.Fatalf("want %q kept, got %v, column %q", c.want, got, col)
				}
			}
		})
	}
}
