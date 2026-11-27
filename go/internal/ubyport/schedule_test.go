package ubyport

import (
	"context"
	"testing"
	"time"
)

func intPtr(v int) *int { return &v }

func TestScheduledSendAtCheckInAnchored(t *testing.T) {
	prague, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		t.Fatal(err)
	}
	// Monday 2026-11-09 (CET, UTC+1). ReportingDeadline = Wed 2026-11-11 23:59:59 CET.
	// Cap (-6h) = Wed 2026-11-11 17:59:59 CET.
	mon := time.Date(2026, 11, 9, 0, 0, 0, 0, time.UTC)

	tests := []struct {
		name             string
		mode             string
		submitAfterHours int
		checkinHour      *int
		submittedAt      string
		anchor           *time.Time
		wantOK           bool
		wantPrague       time.Time
	}{
		{
			name:             "scheduled 24h early submit waits until check-in + 24h",
			mode:             "scheduled",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "2026-11-06T09:00:00+00:00", // Fri 10:00 CET
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 10, 15, 0, 0, 0, prague),
		},
		{
			name:             "scheduled 24h null checkin_hour falls back to 15:00",
			mode:             "scheduled",
			submitAfterHours: 24,
			checkinHour:      nil,
			submittedAt:      "2026-11-06T09:00:00+00:00",
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 10, 15, 0, 0, 0, prague),
		},
		{
			name:             "scheduled 24h late submit after check-in waits 24h from submit",
			mode:             "scheduled",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "2026-11-09T18:00:00+00:00", // Mon 19:00 CET
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 10, 19, 0, 0, 0, prague),
		},
		{
			name:             "scheduled 24h very late submit clamps at deadline - 6h",
			mode:             "scheduled",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "2026-11-11T13:00:00+00:00", // Wed 14:00 CET
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 11, 17, 59, 59, 0, prague),
		},
		{
			name:             "scheduled 24h late evening check-in 23:00 still precedes watchdog",
			mode:             "scheduled",
			submitAfterHours: 24,
			checkinHour:      intPtr(23),
			submittedAt:      "2026-11-06T09:00:00+00:00",
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 10, 23, 0, 0, 0, prague),
		},
		{
			name:             "immediate early submit gated until check-in hour",
			mode:             "immediate",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "2026-11-06T09:00:00+00:00",
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 9, 15, 0, 0, 0, prague),
		},
		{
			name:             "immediate submit after check-in fires immediately",
			mode:             "immediate",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "2026-11-09T18:00:00+00:00", // Mon 19:00 CET
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 9, 19, 0, 0, 0, prague),
		},
		{
			name:             "manual never due",
			mode:             "manual",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "2026-11-06T09:00:00+00:00",
			anchor:           &mon,
			wantOK:           false,
		},
		{
			name:             "missing submit stamp still falls back to deadline - 6h",
			mode:             "scheduled",
			submitAfterHours: 24,
			checkinHour:      intPtr(15),
			submittedAt:      "",
			anchor:           &mon,
			wantOK:           true,
			wantPrague:       time.Date(2026, 11, 11, 17, 59, 59, 0, prague),
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, ok := ScheduledSendAt(tc.mode, tc.submitAfterHours, tc.checkinHour, tc.submittedAt, tc.anchor)
			if ok != tc.wantOK {
				t.Fatalf("ScheduledSendAt ok=%v, want %v (got=%v)", ok, tc.wantOK, got)
			}
			if !ok {
				return
			}
			if !got.Equal(tc.wantPrague) {
				t.Fatalf("ScheduledSendAt = %v, want %v", got.In(prague), tc.wantPrague)
			}
		})
	}
}

func TestCollectSendablePerGuestTimerPartialStay(t *testing.T) {
	pool := claimTestPool(t)
	dec, _ := collectDecrypter(t)
	ctx := context.Background()

	aptID := collectNewApt(t, pool, map[string]any{
		"automation_mode":    "scheduled",
		"submit_after_hours": 24,
		"checkin_hour":       15,
	})

	// Monday 2026-11-09 check-in, declared 3 guests, registration_completed_at NULL (guest 3 not done).
	// Guest 1 filled Friday 2026-11-06 10:00 CET -> due Tue 2026-11-10 15:00 CET (14:00 UTC).
	// Guest 2 filled Mon 2026-11-09 19:00 CET (18:00 UTC) -> due Tue 2026-11-10 19:00 CET (18:00 UTC).
	g1 := collectAddStay(t, pool, aptID,
		map[string]any{
			"date_from":                 "2026-11-09",
			"date_to":                   "2026-11-12",
			"declared_guests":           3,
			"registration_completed_at": nil,
		},
		map[string]any{
			"surname":    "EarlyGuest",
			"filled_at":  "2026-11-06T09:00:00+00:00",
			"updated_at": "2026-11-06T09:00:00+00:00",
		},
	)
	var resID int64
	if err := pool.QueryRow(ctx, `SELECT reservation_id FROM guest WHERE id = $1`, g1).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	var g2 int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, created_at, updated_at) VALUES ($1, '2026-11-09T18:00:00+00:00', '2026-11-09T18:00:00+00:00') RETURNING id`,
		resID).Scan(&g2); err != nil {
		t.Fatal(err)
	}
	v2 := collectValidGuest(t)
	v2["surname"] = "LaterGuest"
	v2["doc_number"] = "DOC999002"
	v2["filled_at"] = "2026-11-09T18:00:00+00:00"
	v2["updated_at"] = "2026-11-09T18:00:00+00:00"
	collectSet(t, pool, "guest", g2, v2)

	// At Mon 15:00 CET (check-in): neither guest is due (scheduled +24h).
	atCheckIn := time.Date(2026, 11, 9, 14, 0, 0, 0, time.UTC)
	got, err := CollectSendable(ctx, pool, aptID, CollectOptions{Decrypt: dec, Now: func() time.Time { return atCheckIn }})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 0 {
		t.Fatalf("at check-in want 0 sendable, got %v", collectIDs(got))
	}

	// At Tue 15:00 CET (14:00 UTC): Guest 1 is due independently of missing Guest 3 and later Guest 2.
	atTue15 := time.Date(2026, 11, 10, 14, 0, 0, 0, time.UTC)
	got, err = CollectSendable(ctx, pool, aptID, CollectOptions{Decrypt: dec, Now: func() time.Time { return atTue15 }})
	if err != nil {
		t.Fatal(err)
	}
	ids := collectIDs(got)
	if len(ids) != 1 || ids[0] != g1 {
		t.Fatalf("at Tue 15:00 CET want [%d], got %v", g1, ids)
	}

	// At Tue 19:00 CET (18:00 UTC): both Guest 1 and Guest 2 are due.
	atTue19 := time.Date(2026, 11, 10, 18, 0, 0, 0, time.UTC)
	got, err = CollectSendable(ctx, pool, aptID, CollectOptions{Decrypt: dec, Now: func() time.Time { return atTue19 }})
	if err != nil {
		t.Fatal(err)
	}
	ids = collectIDs(got)
	if len(ids) != 2 || ids[0] != g1 || ids[1] != g2 {
		t.Fatalf("at Tue 19:00 CET want [%d %d], got %v", g1, g2, ids)
	}
}

func TestSubmitCompletedStayPreCheckInGate(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	env := completionEnv()
	ref := completionFixtureApartment(t, pool, env, "immediate")
	collectSet(t, pool, "apartment", ref.ID, map[string]any{"checkin_hour": 15})

	// Check-in Monday 2026-11-09 15:00 CET (14:00 UTC).
	resID, _ := completionAddStay(t, pool, ref.ID,
		map[string]any{
			"date_from":                 "2026-11-09",
			"date_to":                   "2026-11-11",
			"declared_guests":           1,
			"registration_completed_at": "2026-11-06T09:00:00+00:00",
		},
		map[string]any{
			"filled_at":  "2026-11-06T09:00:00+00:00",
			"updated_at": "2026-11-06T09:00:00+00:00",
		},
	)

	sender := &completionFakeSender{
		res: SubmitResult{RecordErrors: []string{""}, PseudoStamp: "STAMP-PRE", ReceiptPDF: "PDF-PRE"},
	}
	opts := &SubmitCompletedStayOptions{NewSender: func(*ApartmentRow) Sender { return sender }}

	// Before check-in (Mon 14:59 CET = 13:59 UTC): must NOT submit.
	beforeCheckIn := func() time.Time { return time.Date(2026, 11, 9, 13, 59, 0, 0, time.UTC) }
	called, err := SubmitCompletedStay(ctx, pool, env, beforeCheckIn, ref.ID, resID, opts)
	if err != nil || called {
		t.Fatalf("before check-in SubmitCompletedStay = (%v, %v), want (false, nil)", called, err)
	}
	if calls, _ := sender.snapshot(); calls != 0 {
		t.Fatalf("sender calls before check-in = %d, want 0", calls)
	}

	// At check-in (Mon 15:00 CET = 14:00 UTC): submits immediately.
	atCheckIn := func() time.Time { return time.Date(2026, 11, 9, 14, 0, 0, 0, time.UTC) }
	called, err = SubmitCompletedStay(ctx, pool, env, atCheckIn, ref.ID, resID, opts)
	if err != nil || !called {
		t.Fatalf("at check-in SubmitCompletedStay = (%v, %v), want (true, nil)", called, err)
	}
	if calls, _ := sender.snapshot(); calls != 1 {
		t.Fatalf("sender calls at check-in = %d, want 1", calls)
	}
}
