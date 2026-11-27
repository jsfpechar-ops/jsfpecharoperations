package ubyport

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

type completionFakeSender struct {
	mu     sync.Mutex
	calls  int
	guests [][]map[string]any
	delay  time.Duration
	res    SubmitResult
	err    error
}

func (s *completionFakeSender) Submit(_ context.Context, _ map[string]*string, guests []map[string]any) (SubmitResult, error) {
	if s.delay > 0 {
		time.Sleep(s.delay)
	}
	s.mu.Lock()
	s.calls++
	cp := make([]map[string]any, len(guests))
	copy(cp, guests)
	s.guests = append(s.guests, cp)
	res, err := s.res, s.err
	s.mu.Unlock()
	if err != nil {
		return SubmitResult{}, err
	}
	if len(res.RecordErrors) == 0 {
		res.RecordErrors = make([]string, len(guests))
	}
	return res, nil
}

func (s *completionFakeSender) snapshot() (int, [][]map[string]any) {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([][]map[string]any, len(s.guests))
	copy(out, s.guests)
	return s.calls, out
}

func completionEnv() func(string) string {
	return notifyEnv(map[string]string{
		"UBYHOST_SECRET_KEY":      "fixture-secret-key-2075-for-tests-only-32chars",
		"UBYHOST_UBYPORT_ENV":     "test",
		"UBYHOST_MAIL_BACKEND":    "console",
		"UBYHOST_PUBLIC_BASE_URL": "https://example.test",
		"UBYHOST_APP_BASE_URL":    "https://app.example.test",
	})
}

func completionFixtureApartment(t *testing.T, pool *pgxpool.Pool, env func(string) string, mode string) ApartmentRef {
	t.Helper()
	keys, err := secure.LoadDataKeys(env)
	if err != nil {
		t.Fatal(err)
	}
	pwEnc, err := keys.EncryptString("fixture-pw-2075")
	if err != nil {
		t.Fatal(err)
	}
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	collectSet(t, pool, "apartment", ref.ID, map[string]any{
		"automation_mode":     mode,
		"uby_ws_password_enc": pwEnc,
	})
	return ref
}

func completionAddStay(t *testing.T, pool *pgxpool.Pool, aptID int64, res, guest map[string]any) (int64, int64) {
	t.Helper()
	ctx := context.Background()
	const ts = "2026-11-01T00:00:00+00:00"
	var resID int64
	uid := fmt.Sprintf("uid-2075-%d", time.Now().UnixNano())
	if err := pool.QueryRow(ctx,
		`INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, created_at, updated_at)
		 VALUES ($1, $2, '2026-10-30', '2026-11-02', 'active', $3, $3) RETURNING id`,
		aptID, uid, ts).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	r := map[string]any{
		"date_from":                 "2026-10-30",
		"date_to":                   "2026-11-02",
		"declared_guests":           1,
		"registration_completed_at": "2026-10-30T10:00:00+00:00",
	}
	for k, v := range res {
		r[k] = v
	}
	collectSet(t, pool, "reservation", resID, r)
	if guest == nil {
		return resID, 0
	}
	var guestID int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, created_at, updated_at) VALUES ($1, $2, $2) RETURNING id`,
		resID, ts).Scan(&guestID); err != nil {
		t.Fatal(err)
	}
	g := collectValidGuest(t)
	for k, v := range guest {
		g[k] = v
	}
	collectSet(t, pool, "guest", guestID, g)
	return resID, guestID
}

func TestSubmitCompletedStay(t *testing.T) {
	now := func() time.Time { return time.Date(2026, 11, 1, 10, 0, 0, 0, time.UTC) }

	t.Run("two stays in same apartment files only completed stay with receipt", func(t *testing.T) {
		pool := claimTestPool(t)
		ctx := context.Background()
		env := completionEnv()
		ref := completionFixtureApartment(t, pool, env, "immediate")

		resA, guestA := completionAddStay(t, pool, ref.ID,
			map[string]any{"declared_guests": 1},
			map[string]any{"surname": "StayA"})
		_, guestB := completionAddStay(t, pool, ref.ID,
			map[string]any{"declared_guests": 1},
			map[string]any{"surname": "StayB"})

		sender := &completionFakeSender{
			res: SubmitResult{
				RecordErrors: []string{""},
				PseudoStamp:  "STAMP-2075",
				ReceiptPDF:   "PDF-2075",
			},
		}
		opts := &SubmitCompletedStayOptions{
			NewSender: func(*ApartmentRow) Sender { return sender },
		}

		called, err := SubmitCompletedStay(ctx, pool, env, now, ref.ID, resA, opts)
		if err != nil || !called {
			t.Fatalf("SubmitCompletedStay = (%v, %v), want (true, nil)", called, err)
		}

		calls, sent := sender.snapshot()
		if calls != 1 || len(sent) != 1 || len(sent[0]) != 1 {
			t.Fatalf("sender calls=%d batches=%d, want 1 call with 1 guest", calls, len(sent))
		}
		if got := sent[0][0]["cSurN"]; got != "StayA" {
			t.Fatalf("sent cSurN = %v, want StayA", got)
		}

		rowA := storeRead(t, pool, "guest", guestA, "submit_state", "submission_id")
		if rowA["submit_state"] != "sent" || rowA["submission_id"] == "<nil>" {
			t.Fatalf("guest A = %+v, want submit_state=sent and non-null submission_id", rowA)
		}
		var subID int64
		if err := pool.QueryRow(ctx, `SELECT submission_id FROM guest WHERE id = $1`, guestA).Scan(&subID); err != nil {
			t.Fatal(err)
		}
		sub := storeRead(t, pool, "submission", subID, "mode", "pseudo_stamp", "receipt_pdf")
		if sub["mode"] != "completion_immediate" || sub["pseudo_stamp"] != "STAMP-2075" || sub["receipt_pdf"] != "PDF-2075" {
			t.Fatalf("submission = %+v, want completion_immediate / STAMP-2075 / PDF-2075", sub)
		}

		rowB := storeRead(t, pool, "guest", guestB, "submit_state")
		if rowB["submit_state"] != "pending" {
			t.Fatalf("guest B submit_state = %q, want pending (untouched)", rowB["submit_state"])
		}
	})

	t.Run("gates block filing", func(t *testing.T) {
		cases := []struct {
			name  string
			setup func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (aptID, resID, untouchedGuestID int64)
		}{
			{
				name: "incomplete",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref := completionFixtureApartment(t, pool, env, "immediate")
					resID, _ := completionAddStay(t, pool, ref.ID,
						map[string]any{"declared_guests": 2, "registration_completed_at": nil},
						map[string]any{"surname": "Incomplete"})
					return ref.ID, resID, 0
				},
			},
			{
				name: "manual mode",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref := completionFixtureApartment(t, pool, env, "manual")
					resID, _ := completionAddStay(t, pool, ref.ID, nil, map[string]any{"surname": "Manual"})
					return ref.ID, resID, 0
				},
			},
			{
				name: "scheduled mode",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref := completionFixtureApartment(t, pool, env, "scheduled")
					resID, _ := completionAddStay(t, pool, ref.ID, nil, map[string]any{"surname": "Scheduled"})
					return ref.ID, resID, 0
				},
			},
			{
				name: "auth paused",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref := completionFixtureApartment(t, pool, env, "immediate")
					resID, _ := completionAddStay(t, pool, ref.ID, nil, map[string]any{"surname": "Paused"})
					if err := RaiseAlert(context.Background(), pool, "critical", "ubyport_auth_failed",
						"refused", "", fmt.Sprintf("ubyport_auth_failed:%d", ref.ID), &ref.ID, nil, nil, nil); err != nil {
						t.Fatal(err)
					}
					return ref.ID, resID, 0
				},
			},
			{
				name: "empty guest list",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref := completionFixtureApartment(t, pool, env, "immediate")
					resEmpty, _ := completionAddStay(t, pool, ref.ID,
						map[string]any{"declared_guests": 0, "registration_completed_at": "2026-10-30T10:00:00+00:00"},
						nil)
					_, guestB := completionAddStay(t, pool, ref.ID,
						map[string]any{"declared_guests": 1},
						map[string]any{"surname": "StayB"})
					return ref.ID, resEmpty, guestB
				},
			},
			{
				name: "wrong apartment",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref1 := completionFixtureApartment(t, pool, env, "immediate")
					ref2 := completionFixtureApartment(t, pool, env, "immediate")
					resID, _ := completionAddStay(t, pool, ref2.ID, nil, map[string]any{"surname": "WrongApt"})
					return ref1.ID, resID, 0
				},
			},
			{
				name: "cancelled stay",
				setup: func(t *testing.T, pool *pgxpool.Pool, env func(string) string) (int64, int64, int64) {
					ref := completionFixtureApartment(t, pool, env, "immediate")
					resID, _ := completionAddStay(t, pool, ref.ID,
						map[string]any{"status": "cancelled"},
						map[string]any{"surname": "Cancelled"})
					return ref.ID, resID, 0
				},
			},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				pool := claimTestPool(t)
				env := completionEnv()
				aptID, resID, untouchedGuestID := tc.setup(t, pool, env)
				sender := &completionFakeSender{}
				d := sweepDeps(t, pool, "fixture-pw-2075", sender)
				opts := &SubmitCompletedStayOptions{SweepDeps: &d}

				called, err := SubmitCompletedStay(context.Background(), pool, env, now, aptID, resID, opts)
				if err != nil || called {
					t.Fatalf("SubmitCompletedStay = (%v, %v), want (false, nil)", called, err)
				}
				calls, _ := sender.snapshot()
				if calls != 0 {
					t.Fatalf("sender calls = %d, want 0", calls)
				}
				if untouchedGuestID > 0 {
					rowB := storeRead(t, pool, "guest", untouchedGuestID, "submit_state")
					if rowB["submit_state"] != "pending" {
						t.Fatalf("Stay B guest submit_state = %q, want pending", rowB["submit_state"])
					}
				}
			})
		}
	})

	t.Run("failed send raises submission_immediate warning safely", func(t *testing.T) {
		pool := claimTestPool(t)
		ctx := context.Background()
		env := completionEnv()
		ref := completionFixtureApartment(t, pool, env, "immediate")
		resID, _ := completionAddStay(t, pool, ref.ID, nil, map[string]any{"surname": "Crash"})

		crashSender := &completionFakeSender{err: errors.New("unexpected soap crash")}
		called, err := SubmitCompletedStay(ctx, pool, env, now, ref.ID, resID, &SubmitCompletedStayOptions{
			NewSender: func(*ApartmentRow) Sender { return crashSender },
		})
		if err != nil || called {
			t.Fatalf("unexpected error path = (%v, %v), want (false, nil)", called, err)
		}
		immKey := fmt.Sprintf("submission_immediate:%d", ref.ID)
		if n := batchOpenAlert(t, pool, immKey); n != 1 {
			t.Fatalf("open %s alerts = %d, want 1", immKey, n)
		}
		level := effectsText(t, pool, `SELECT level FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, immKey)
		params := effectsText(t, pool, `SELECT params FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, immKey)
		if level != "warning" {
			t.Fatalf("alert level = %q, want warning", level)
		}
		if !strings.Contains(params, `"property"`) || !strings.Contains(params, `"error"`) {
			t.Fatalf("alert params = %q, want property and error keys", params)
		}

		// Auth error opens ubyport_auth_failed:<apt> and blocks subsequent immediate attempts.
		refAuth := completionFixtureApartment(t, pool, env, "immediate")
		resAuth, _ := completionAddStay(t, pool, refAuth.ID, nil, map[string]any{"surname": "AuthFail"})
		authSender := &completionFakeSender{
			err: &Error{Kind: ErrAuth, Cause: "auth", Msg: "401 Unauthorized"},
		}
		called, err = SubmitCompletedStay(ctx, pool, env, now, refAuth.ID, resAuth, &SubmitCompletedStayOptions{
			NewSender: func(*ApartmentRow) Sender { return authSender },
		})
		if err != nil || !called {
			t.Fatalf("auth error first call = (%v, %v), want (true, nil)", called, err)
		}
		authKey := fmt.Sprintf("ubyport_auth_failed:%d", refAuth.ID)
		if n := batchOpenAlert(t, pool, authKey); n != 1 {
			t.Fatalf("open %s alerts = %d, want 1", authKey, n)
		}
		calls1, _ := authSender.snapshot()
		if calls1 != 1 {
			t.Fatalf("auth sender calls after first attempt = %d, want 1", calls1)
		}

		called, err = SubmitCompletedStay(ctx, pool, env, now, refAuth.ID, resAuth, &SubmitCompletedStayOptions{
			NewSender: func(*ApartmentRow) Sender { return authSender },
		})
		if err != nil || called {
			t.Fatalf("auth-paused second call = (%v, %v), want (false, nil)", called, err)
		}
		calls2, _ := authSender.snapshot()
		if calls2 != 1 {
			t.Fatalf("auth sender calls after paused attempt = %d, want 1", calls2)
		}
	})

	t.Run("repeated and concurrent calls never send an accepted guest twice", func(t *testing.T) {
		pool := claimTestPool(t)
		ctx := context.Background()
		env := completionEnv()
		ref := completionFixtureApartment(t, pool, env, "immediate")
		resID, _ := completionAddStay(t, pool, ref.ID, nil, map[string]any{"surname": "Concurrent"})

		sender := &completionFakeSender{
			delay: 30 * time.Millisecond,
			res: SubmitResult{
				RecordErrors: []string{""},
				PseudoStamp:  "STAMP-CONC",
				ReceiptPDF:   "PDF-CONC",
			},
		}
		opts := &SubmitCompletedStayOptions{
			NewSender: func(*ApartmentRow) Sender { return sender },
		}

		var wg sync.WaitGroup
		errs := make([]error, 2)
		for i := 0; i < 2; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				_, errs[idx] = SubmitCompletedStay(ctx, pool, env, now, ref.ID, resID, opts)
			}(i)
		}
		wg.Wait()
		for i, err := range errs {
			if err != nil {
				t.Fatalf("concurrent call %d err = %v", i, err)
			}
		}

		if _, err := SubmitCompletedStay(ctx, pool, env, now, ref.ID, resID, opts); err != nil {
			t.Fatalf("sequential repeat err = %v", err)
		}

		calls, sent := sender.snapshot()
		totalGuests := 0
		for _, batch := range sent {
			totalGuests += len(batch)
		}
		if calls != 1 || totalGuests != 1 {
			t.Fatalf("sender calls=%d totalGuests=%d, want 1 and 1", calls, totalGuests)
		}
		if n := effectsCount(t, pool, `SELECT count(*) FROM submission WHERE apartment_id = $1`, ref.ID); n != 1 {
			t.Fatalf("submission row count = %d, want 1", n)
		}
	})
}
