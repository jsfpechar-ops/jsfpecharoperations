package ubyport

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// sweepSender records the size of every batch it is asked to send.
type sweepSender struct {
	sizes []int
}

func (s *sweepSender) Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error) {
	s.sizes = append(s.sizes, len(guests))
	return SubmitResult{}, nil
}

// sweepDeps wires the sweep to the test database, the test keys and a recording sender.
func sweepDeps(t *testing.T, pool *pgxpool.Pool, password string, s Sender) SweepDeps {
	t.Helper()
	dec, enc := collectDecrypter(t)
	return SweepDeps{
		Batch: BatchDeps{
			Pool:          pool,
			Enc:           enc,
			Getenv:        notifyEnv(map[string]string{"UBYHOST_MAIL_BACKEND": "console", "UBYHOST_WEB_PUSH": "1", "UBYHOST_UBYPORT_ENV": "test"}),
			AppBaseURL:    "https://app.example.test",
			PublicBaseURL: "https://example.test",
			Endpoint:      "https://ubyport.example.test/ws",
			Codebook:      map[string]string{},
			Severities:    map[string]int{},
			Now:           func() time.Time { return time.Date(2026, 11, 1, 10, 0, 0, 0, time.UTC) },
		},
		Decrypt:       dec,
		DecryptSecret: func(string) string { return password },
		NewSender:     func(*ApartmentRow) Sender { return s },
		MaxBatch:      32,
	}
}

func TestSweepDemoApartmentIsNoop(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	if _, err := pool.Exec(ctx, `UPDATE apartment SET internal_name = $1 WHERE id = $2`, demoApartmentOne, ref.ID); err != nil {
		t.Fatal(err)
	}
	s := &sweepSender{}
	res, err := SubmitForApartment(ctx, sweepDeps(t, pool, "pw", s), ref.ID, CollectOptions{}, "auto")
	if err != nil || len(res) != 1 || res[0].State != "noop" || len(s.sizes) != 0 {
		t.Fatalf("demo: err=%v res=%+v sent=%v", err, res, s.sizes)
	}
}

func TestSweepIncompleteSetupAlertsAndSendsNothing(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	collectAddStay(t, pool, ref.ID, nil, nil)
	s := &sweepSender{}
	// An empty password fails validation, as a missing UbyPort password does.
	res, err := SubmitForApartment(ctx, sweepDeps(t, pool, "", s), ref.ID, CollectOptions{}, "auto")
	if err != nil || len(res) != 1 || res[0].State != "not_configured" || len(s.sizes) != 0 {
		t.Fatalf("setup: err=%v res=%+v sent=%v", err, res, s.sizes)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("apartment_setup:%d", ref.ID)); n != 1 {
		t.Fatalf("apartment_setup alerts open = %d, want 1", n)
	}
}

func TestSweepBatchesSeventyGuestsInThrees(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	for i := 0; i < 70; i++ {
		collectAddStay(t, pool, ref.ID, nil, nil)
	}
	s := &sweepSender{}
	res, err := SubmitForApartment(ctx, sweepDeps(t, pool, "pw", s), ref.ID, CollectOptions{}, "auto")
	if err != nil {
		t.Fatal(err)
	}
	if fmt.Sprint(s.sizes) != fmt.Sprint([]int{32, 32, 6}) || len(res) != 3 {
		t.Fatalf("batches sent=%v results=%d, want [32 32 6] and 3 results", s.sizes, len(res))
	}
}

func TestSweepContainsUnreadableGuestAndSkipsAuthAlert(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	bad := sweepFixtureApartment(t, pool, ptrString("bad@example.test"))
	collectAddStay(t, pool, bad.ID, nil, map[string]any{"doc_number_enc": "not-a-fernet-token"})
	good := sweepFixtureApartment(t, pool, ptrString("good@example.test"))
	collectAddStay(t, pool, good.ID, nil, nil)
	authed := sweepFixtureApartment(t, pool, ptrString("authed@example.test"))
	collectAddStay(t, pool, authed.ID, nil, nil)
	if err := RaiseAlert(ctx, pool, "critical", "ubyport_auth_failed", "login refused", "",
		fmt.Sprintf("ubyport_auth_failed:%d", authed.ID), &authed.ID, nil, nil, nil); err != nil {
		t.Fatal(err)
	}

	s := &sweepSender{}
	summary, err := Sweep(ctx, sweepDeps(t, pool, "pw", s), nil)
	if err != nil {
		t.Fatal(err)
	}
	if summary.Apartments != 2 || summary.Failed != 1 {
		t.Fatalf("summary = %+v, want 2 apartments and 1 failed", summary)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("guest_record_unreadable:%d", bad.ID)); n != 1 {
		t.Fatalf("guest_record_unreadable open = %d, want 1", n)
	}
	if fmt.Sprint(s.sizes) != fmt.Sprint([]int{1}) {
		t.Fatalf("sent=%v, want one batch of 1 for the good apartment only", s.sizes)
	}
}

// sweepApartment is notifyApartment with the UbyPort settings a valid setup needs.
func sweepFixtureApartment(t *testing.T, pool *pgxpool.Pool, contact *string) ApartmentRef {
	t.Helper()
	ref := notifyApartment(t, pool, contact)
	collectSet(t, pool, "apartment", ref.ID, map[string]any{
		"addr_house_no": "12", "addr_obec": "Praha", "addr_okres": "Praha", "addr_orient_no": "3a",
		"addr_street": "Dlouha", "addr_zip": "11000", "uby_contact": "Jan Novak", "uby_idub": "ABCDEFGH1234",
		"uby_mark": "AAKLI", "uby_name": "Penzion U Lesa", "uby_ws_user": "UBY-WS_AAKLI",
	})
	return ref
}

// failSecondSender answers batch 2 with a transport error and the other batches with success.
type failSecondSender struct {
	calls int
}

func (f *failSecondSender) Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error) {
	f.calls++
	if f.calls == 2 {
		return SubmitResult{}, &Error{Kind: ErrTransport, Msg: "connection refused"}
	}
	return SubmitResult{}, nil
}

func TestSweepReleasesClaimsWhenABatchFails(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	var guests []int64
	for i := 0; i < 70; i++ {
		guests = append(guests, collectAddStay(t, pool, ref.ID, nil, nil))
	}
	s := &failSecondSender{}
	// The error is contained per batch; the claims must go either way.
	_, _ = SubmitForApartment(ctx, sweepDeps(t, pool, "pw", s), ref.ID, CollectOptions{}, sweepMode)
	if s.calls < 2 {
		t.Fatalf("batches sent = %d, want at least the failing batch 2", s.calls)
	}
	for _, id := range guests {
		if n := claimCount(t, pool, id); n != 0 {
			t.Fatalf("guest %d still holds %d claim rows after a failed batch", id, n)
		}
	}
}

// staleBatch stores an outcome_unknown batch for the given guests, as a crash leaves it,
// and points those guests at it.
func staleBatch(t *testing.T, pool *pgxpool.Pool, aptID int64, guests []int64, mode any, retried any, reason string) int64 {
	t.Helper()
	ctx := context.Background()
	raw, err := json.Marshal(guests)
	if err != nil {
		t.Fatal(err)
	}
	var sub int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO submission (apartment_id, created_at, state, guest_ids, error_text, mode, retried_at)
		 VALUES ($1, $2, 'outcome_unknown', $3, $4, $5, $6) RETURNING id`,
		aptID, time.Date(2026, 11, 1, 9, 0, 0, 0, time.UTC), string(raw), reason, mode, retried).Scan(&sub); err != nil {
		t.Fatal(err)
	}
	if len(guests) > 0 {
		if _, err := pool.Exec(ctx, `UPDATE guest SET submission_id = $1 WHERE id = ANY($2)`, sub, guests); err != nil {
			t.Fatal(err)
		}
	}
	return sub
}

func retriedAtSet(t *testing.T, pool *pgxpool.Pool, submissionID int64) bool {
	t.Helper()
	var set bool
	if err := pool.QueryRow(context.Background(),
		`SELECT retried_at IS NOT NULL FROM submission WHERE id = $1`, submissionID).Scan(&set); err != nil {
		t.Fatal(err)
	}
	return set
}

func TestRetryResendsOnlyStaleBatchGuests(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	var guests []int64
	for i := 0; i < 3; i++ {
		guests = append(guests, collectAddStay(t, pool, ref.ID, nil, nil))
	}
	// The stale batch holds only the first two guests; the third is not in it.
	stale := staleBatch(t, pool, ref.ID, guests[:2], nil, nil, staleSubmissionReason)

	s := &sweepSender{}
	n, err := RetryOutcomeUnknownBatches(ctx, sweepDeps(t, pool, "pw", s), ref.ID)
	if err != nil || n != 1 {
		t.Fatalf("retried=%d err=%v, want 1 and no error", n, err)
	}
	if fmt.Sprint(s.sizes) != fmt.Sprint([]int{2}) {
		t.Fatalf("sent=%v, want one resend of 2 guests", s.sizes)
	}
	if !retriedAtSet(t, pool, stale) {
		t.Fatal("stale batch retried_at not set")
	}
	for _, id := range guests[:2] {
		var sid *int64
		if err := pool.QueryRow(ctx, `SELECT submission_id FROM guest WHERE id = $1`, id).Scan(&sid); err != nil {
			t.Fatal(err)
		}
		if sid != nil && *sid == stale {
			t.Fatalf("guest %d still points at the stale batch", id)
		}
	}
	var resent int
	if err := pool.QueryRow(ctx,
		`SELECT count(*) FROM submission WHERE apartment_id = $1 AND mode = 'auto_resend'`, ref.ID).Scan(&resent); err != nil {
		t.Fatal(err)
	}
	if resent != 1 {
		t.Fatalf("auto_resend submissions = %d, want 1", resent)
	}
}

func TestRetrySkipsAndGuards(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	cases := []struct {
		name        string
		mode        any
		retried     any
		empty       bool
		alert       bool
		wantRetried bool
	}{
		{"auto_resend mode is not retried again", "auto_resend", nil, false, false, false},
		{"retried_at already set is not retried", nil, time.Date(2026, 11, 1, 9, 30, 0, 0, time.UTC), false, false, true},
		{"empty guest list is marked and not sent", nil, nil, true, false, true},
		{"open ubyport_auth_failed alert blocks the retry", nil, nil, false, true, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
			guests := []int64{}
			if !c.empty {
				guests = append(guests, collectAddStay(t, pool, ref.ID, nil, nil))
			}
			stale := staleBatch(t, pool, ref.ID, guests, c.mode, c.retried, staleSubmissionReason)
			if c.alert {
				if err := RaiseAlert(ctx, pool, "critical", "ubyport_auth_failed", "login refused", "",
					fmt.Sprintf("ubyport_auth_failed:%d", ref.ID), &ref.ID, nil, nil, nil); err != nil {
					t.Fatal(err)
				}
			}
			s := &sweepSender{}
			n, err := RetryOutcomeUnknownBatches(ctx, sweepDeps(t, pool, "pw", s), ref.ID)
			if err != nil || n != 0 {
				t.Fatalf("retried=%d err=%v, want 0 and no error", n, err)
			}
			if len(s.sizes) != 0 {
				t.Fatalf("sent=%v, want nothing", s.sizes)
			}
			if got := retriedAtSet(t, pool, stale); got != c.wantRetried {
				t.Fatalf("retried_at set = %v, want %v", got, c.wantRetried)
			}
		})
	}
}
