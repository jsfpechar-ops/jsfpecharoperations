package ubyport

import (
	"context"
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
