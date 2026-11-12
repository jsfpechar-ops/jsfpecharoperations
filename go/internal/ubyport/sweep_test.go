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
		finished    string
		wantSent    int
		wantRetried bool
	}{
		{"auto_resend stale batch waits for its gap", "auto_resend", nil, false, false, "2026-11-01T09:45:00+00:00", 0, false},
		{"auto_resend stale batch is resent by the chain once due", "auto_resend", nil, false, false, "2026-11-01T09:00:00+00:00", 1, true},
		{"retried_at already set is not retried", nil, time.Date(2026, 11, 1, 9, 30, 0, 0, time.UTC), false, false, "", 0, true},
		{"empty guest list is marked and not sent", nil, nil, true, false, "", 0, true},
		{"open ubyport_auth_failed alert blocks the retry", nil, nil, false, true, "", 0, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
			guests := []int64{}
			if !c.empty {
				guests = append(guests, collectAddStay(t, pool, ref.ID, nil, nil))
			}
			stale := staleBatch(t, pool, ref.ID, guests, c.mode, c.retried, staleSubmissionReason)
			if c.finished != "" {
				if _, err := pool.Exec(ctx, `UPDATE submission SET finished_at = $1 WHERE id = $2`, c.finished, stale); err != nil {
					t.Fatal(err)
				}
			}
			if c.alert {
				if err := RaiseAlert(ctx, pool, "critical", "ubyport_auth_failed", "login refused", "",
					fmt.Sprintf("ubyport_auth_failed:%d", ref.ID), &ref.ID, nil, nil, nil); err != nil {
					t.Fatal(err)
				}
			}
			s := &sweepSender{}
			n, err := RetryOutcomeUnknownBatches(ctx, sweepDeps(t, pool, "pw", s), ref.ID)
			if err != nil || n != c.wantSent {
				t.Fatalf("retried=%d err=%v, want %d and no error", n, err, c.wantSent)
			}
			if len(s.sizes) != c.wantSent {
				t.Fatalf("sent=%v, want %d batch(es)", s.sizes, c.wantSent)
			}
			if got := retriedAtSet(t, pool, stale); got != c.wantRetried {
				t.Fatalf("retried_at set = %v, want %v", got, c.wantRetried)
			}
		})
	}
}

// chainStart is the first instant of the chain tests; the sweep clock is faked.
var chainStart = time.Date(2026, 11, 1, 9, 0, 0, 0, time.UTC)

func chainStamp(at time.Time) string { return at.UTC().Format(time.RFC3339) }

func chainCount(t *testing.T, pool *pgxpool.Pool, query string, args ...any) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), query, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// chainBatch stores an unanswered batch as an earlier attempt left it, finished
// at the given time, and points the guests at it.
func chainBatch(t *testing.T, pool *pgxpool.Pool, aptID int64, guests []int64, mode any, finished time.Time) int64 {
	t.Helper()
	ctx := context.Background()
	raw, err := json.Marshal(guests)
	if err != nil {
		t.Fatal(err)
	}
	var sub int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO submission (apartment_id, created_at, state, guest_ids, error_text, mode, finished_at)
		 VALUES ($1, $2, 'outcome_unknown', $3, 'Remote end closed connection without response', $4, $5) RETURNING id`,
		aptID, chainStart, string(raw), mode, chainStamp(finished)).Scan(&sub); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submission_id = $1 WHERE id = ANY($2)`, sub, guests); err != nil {
		t.Fatal(err)
	}
	return sub
}

// unknownSender answers every batch the way UbyPort does when the connection drops.
type unknownSender struct {
	sizes []int
}

func (s *unknownSender) Submit(ctx context.Context, header map[string]*string, guests []map[string]any) (SubmitResult, error) {
	s.sizes = append(s.sizes, len(guests))
	return SubmitResult{}, &Error{Kind: ErrOutcomeUnknown, Msg: "Remote end closed connection without response"}
}

// chainSweepAt runs one sweep at the fake time at, then stamps the batches it
// wrote with that time, so the next sweep measures its gaps from them.
func chainSweepAt(t *testing.T, pool *pgxpool.Pool, d SweepDeps, aptID int64, at time.Time) int {
	t.Helper()
	ctx := context.Background()
	d.Batch.Now = func() time.Time { return at }
	n, err := RetryOutcomeUnknownBatches(ctx, d, aptID)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx,
		`UPDATE submission SET finished_at = $1 WHERE apartment_id = $2 AND finished_at > $1`,
		chainStamp(at), aptID); err != nil {
		t.Fatal(err)
	}
	return n
}

// The gaps 30 min, 2 h, 6 h, 12 h, then the final notice; never a sixth batch.
func TestChainTimingAndCap(t *testing.T) {
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	g := collectAddStay(t, pool, ref.ID, nil, nil)
	at := chainStart
	chainBatch(t, pool, ref.ID, []int64{g}, nil, at)
	d := sweepDeps(t, pool, "pw", &unknownSender{})
	gaps := []time.Duration{30 * time.Minute, 2 * time.Hour, 6 * time.Hour, 12 * time.Hour}
	for k, gap := range gaps {
		due := at.Add(gap)
		if n := chainSweepAt(t, pool, d, ref.ID, due.Add(-time.Minute)); n != 0 {
			t.Fatalf("attempt %d resent 1 minute before its gap", k+2)
		}
		if n := chainSweepAt(t, pool, d, ref.ID, due); n != 1 {
			t.Fatalf("attempt %d: resent %d at its gap, want 1", k+2, n)
		}
		at = due
	}
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM submission WHERE apartment_id = $1`, ref.ID); got != 5 {
		t.Fatalf("batches = %d, want 5", got)
	}
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE apartment_id = $1`, ref.ID); got != 0 {
		t.Fatalf("mail rows before the final notice = %d, want 0", got)
	}
	if n := chainSweepAt(t, pool, d, ref.ID, at.Add(time.Hour)); n != 0 {
		t.Fatalf("resent %d at the cap, want 0", n)
	}
	last := chainCount(t, pool, `SELECT MAX(id) FROM submission WHERE apartment_id = $1`, ref.ID)
	key := fmt.Sprintf("submission_unanswered:%d", last)
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = $1 AND cc_email = 'support@ubyhost.com'`, key); got != 1 {
		t.Fatalf("final notice rows = %d, want 1 with the support copy", got)
	}
	chainSweepAt(t, pool, d, ref.ID, at.Add(time.Hour+5*time.Minute))
	chainSweepAt(t, pool, d, ref.ID, at.Add(time.Hour+10*time.Minute))
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = $1`, key); got != 1 {
		t.Fatalf("final notice rows after two more sweeps = %d, want 1", got)
	}
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM submission WHERE apartment_id = $1`, ref.ID); got != 5 {
		t.Fatalf("batches after the cap = %d, want 5", got)
	}
}

// A guest order of [2,1] and a resend of [1,2] are one chain.
func TestChainKeyIsTextOrderFree(t *testing.T) {
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	g1 := collectAddStay(t, pool, ref.ID, nil, nil)
	g2 := collectAddStay(t, pool, ref.ID, nil, nil)
	chainBatch(t, pool, ref.ID, []int64{g2, g1}, nil, chainStart)
	d := sweepDeps(t, pool, "pw", &unknownSender{})
	at := chainStart.Add(30 * time.Minute)
	if n := chainSweepAt(t, pool, d, ref.ID, at); n != 1 {
		t.Fatalf("resent %d, want 1", n)
	}
	if n := chainSweepAt(t, pool, d, ref.ID, at.Add(time.Hour+59*time.Minute)); n != 0 {
		t.Fatalf("resent %d before the 2 h gap of one chain", n)
	}
	if n := chainSweepAt(t, pool, d, ref.ID, at.Add(2*time.Hour)); n != 1 {
		t.Fatalf("resent %d at the 2 h gap, want 1", n)
	}
}

// A guest filed by hand during the gap is not resent; the other one is.
func TestChainResendsOnlyGuestsNotFiledByHand(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	g1 := collectAddStay(t, pool, ref.ID, nil, nil)
	g2 := collectAddStay(t, pool, ref.ID, nil, nil)
	chainBatch(t, pool, ref.ID, []int64{g1, g2}, nil, chainStart)
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'sent' WHERE id = $1`, g1); err != nil {
		t.Fatal(err)
	}
	s := &sweepSender{}
	d := sweepDeps(t, pool, "pw", s)
	if n := chainSweepAt(t, pool, d, ref.ID, chainStart.Add(30*time.Minute)); n != 1 {
		t.Fatalf("resent %d, want 1", n)
	}
	if len(s.sizes) != 1 || s.sizes[0] != 1 {
		t.Fatalf("sent=%v, want one batch of one guest", s.sizes)
	}
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM guest WHERE id = $1 AND submission_id IS NOT NULL`, g1); got != 1 {
		t.Fatalf("filed guest was freed")
	}
}

// A host send that is unanswered starts a fresh chain: first resend 30 min later.
func TestChainHostSendStartsFreshChain(t *testing.T) {
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	g := collectAddStay(t, pool, ref.ID, nil, nil)
	chainBatch(t, pool, ref.ID, []int64{g}, nil, chainStart)
	chainBatch(t, pool, ref.ID, []int64{g}, nil, chainStart.Add(time.Hour))
	d := sweepDeps(t, pool, "pw", &unknownSender{})
	if n := chainSweepAt(t, pool, d, ref.ID, chainStart.Add(time.Hour+29*time.Minute)); n != 0 {
		t.Fatalf("resent %d before 30 min after the host send", n)
	}
	if n := chainSweepAt(t, pool, d, ref.ID, chainStart.Add(time.Hour+30*time.Minute)); n != 1 {
		t.Fatalf("resent %d at 30 min after the host send, want 1", n)
	}
}

// A second sweep right after a resend does not resend again.
func TestChainResendsOnceForRepeatedSweeps(t *testing.T) {
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	g := collectAddStay(t, pool, ref.ID, nil, nil)
	chainBatch(t, pool, ref.ID, []int64{g}, nil, chainStart)
	d := sweepDeps(t, pool, "pw", &unknownSender{})
	at := chainStart.Add(30 * time.Minute)
	if n := chainSweepAt(t, pool, d, ref.ID, at); n != 1 {
		t.Fatalf("first sweep resent %d, want 1", n)
	}
	if n := chainSweepAt(t, pool, d, ref.ID, at); n != 0 {
		t.Fatalf("second sweep resent %d, want 0", n)
	}
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM submission WHERE apartment_id = $1`, ref.ID); got != 2 {
		t.Fatalf("batches = %d, want 2", got)
	}
}

// Once no guest waits on an unknown batch (filed by hand), the card resolves.
func TestChainResolvesCardWhenNoGuestWaits(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	g := collectAddStay(t, pool, ref.ID, nil, nil)
	chainBatch(t, pool, ref.ID, []int64{g}, nil, chainStart)
	key := fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)
	if err := RaiseAlert(ctx, pool, "critical", "submission_outcome_unknown", "x", "", key, &ref.ID, nil, nil, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET submit_state = 'sent' WHERE id = $1`, g); err != nil {
		t.Fatal(err)
	}
	d := sweepDeps(t, pool, "pw", &unknownSender{})
	chainSweepAt(t, pool, d, ref.ID, chainStart.Add(time.Minute))
	if got := chainCount(t, pool, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key); got != 0 {
		t.Fatalf("open card = %d, want 0", got)
	}
}

// stuckRunning seeds an apartment (mode, active), one stay with an unsent guest and a
// running batch nobody points at, as a crash leaves it. claimAge < 0 means no claim row;
// otherwise it is the claim's age in seconds at the sweep clock.
func stuckRunning(t *testing.T, pool *pgxpool.Pool, d SweepDeps, mode string, active int, claimAge int) (ApartmentRef, int64, int64) {
	t.Helper()
	ctx := context.Background()
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	if _, err := pool.Exec(ctx, `UPDATE apartment SET automation_mode = $1, active = $2 WHERE id = $3`, mode, active, ref.ID); err != nil {
		t.Fatal(err)
	}
	_, guest := notifyStay(t, pool, ref.ID, fmt.Sprintf("stuck-%d", time.Now().UnixNano()), "2099-01-10", "2099-01-12")
	sub, err := InsertSubmission(ctx, pool, ref.ID, "auto", []int64{guest}, "ep", "2026-11-01T09:00:00+00:00")
	if err != nil {
		t.Fatal(err)
	}
	if claimAge >= 0 {
		if _, err := pool.Exec(ctx,
			`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 't', $2)`,
			guest, float64(d.Batch.Now().Unix())-float64(claimAge)); err != nil {
			t.Fatal(err)
		}
	}
	return ref, guest, sub
}

func TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment(t *testing.T) {
	cases := []struct {
		name     string
		mode     string
		active   int
		claimAge int
		authFail bool
	}{
		{"manual", "manual", 1, -1, false},
		{"manual stale claim", "manual", 1, 600, false},
		{"inactive", "immediate", 0, -1, false},
		{"auth failed", "immediate", 1, -1, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ctx := context.Background()
			pool := claimTestPool(t)
			s := &sweepSender{}
			d := sweepDeps(t, pool, "pw", s)
			ref, guest, sub := stuckRunning(t, pool, d, c.mode, c.active, c.claimAge)
			if c.authFail {
				if err := RaiseAlert(ctx, pool, "critical", "ubyport_auth_failed", "login refused", "",
					fmt.Sprintf("ubyport_auth_failed:%d", ref.ID), &ref.ID, nil, nil, nil); err != nil {
					t.Fatal(err)
				}
			}

			if _, err := Sweep(ctx, d, ref.OwnerUserID); err != nil {
				t.Fatal(err)
			}

			if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "outcome_unknown" {
				t.Fatalf("state %q, want outcome_unknown", st)
			}
			if got := storeRead(t, pool, "guest", guest, "submission_id")["submission_id"]; got != fmt.Sprint(sub) {
				t.Fatalf("guest points at %q, want %d", got, sub)
			}
			key := fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)
			if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL AND level = 'critical'`, key); n != 1 {
				t.Fatalf("critical alerts open = %d, want 1", n)
			}
			if len(s.sizes) != 0 {
				t.Fatalf("recovery sent %v, want nothing", s.sizes)
			}
		})
	}
}

func TestSweepNeverRecoversALiveClaimInManualMode(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	s := &sweepSender{}
	d := sweepDeps(t, pool, "pw", s)
	ref, guest, sub := stuckRunning(t, pool, d, "manual", 1, 10)

	if _, err := Sweep(ctx, d, ref.OwnerUserID); err != nil {
		t.Fatal(err)
	}

	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "running" {
		t.Fatalf("live claim: state %q, want running", st)
	}
	if got := storeRead(t, pool, "guest", guest, "submission_id")["submission_id"]; got != "<nil>" {
		t.Fatalf("live claim: guest pointed at %q", got)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)); n != 0 {
		t.Fatalf("live claim raised %d alerts", n)
	}
}

func TestSweepRecoversAnAutoApartmentStuckBatchOnce(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	s := &sweepSender{}
	d := sweepDeps(t, pool, "pw", s)
	ref, _, sub := stuckRunning(t, pool, d, "immediate", 1, -1)

	for i := 0; i < 2; i++ {
		if _, err := Sweep(ctx, d, ref.OwnerUserID); err != nil {
			t.Fatal(err)
		}
	}

	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "outcome_unknown" {
		t.Fatalf("state %q, want outcome_unknown", st)
	}
	// The retry pass may settle the alert itself in auto mode; the recovery pass
	// must not raise a second one.
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`,
		fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)); n != 1 {
		t.Fatalf("alert rows = %d, want 1", n)
	}
}

func TestSweepRecoveryStaysInsideTheRequestedWorkspace(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	d := sweepDeps(t, pool, "pw", &sweepSender{})
	ref, _, sub := stuckRunning(t, pool, d, "manual", 1, -1)
	other := *ref.OwnerUserID + 100000

	if _, err := Sweep(ctx, d, &other); err != nil {
		t.Fatal(err)
	}

	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "running" {
		t.Fatalf("state %q, want running for another workspace's sweep", st)
	}
}
