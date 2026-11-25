package guesthandoff

import (
	"context"
	"strings"
	"testing"
	"time"
)

// Mirrors App/tests/test_guest_handoff.py batching after the Go port (2037 / #1282).
func TestOnNewQuestionOneMailPerBatch(t *testing.T) {
	pool := handoffTestPool(t)
	ctx := context.Background()
	aptID, _, _ := handoffSeedApartment(t, pool)
	now := func() time.Time { return mustTime("2026-06-01T12:00:00Z") }

	q1 := handoffInsertQuestion(t, pool, aptID, 0)
	OnNewQuestion(ctx, pool, handoffTestEnv, now, q1)
	if n := handoffOutboxCount(t, pool, aptID); n != 1 {
		t.Fatalf("after first question outbox %d", n)
	}
	open, urgentOpen, err := OpenCounts(ctx, pool, aptID)
	if err != nil || open != 1 || urgentOpen != 0 {
		t.Fatalf("counts open=%d urgent=%d err=%v", open, urgentOpen, err)
	}

	q2 := handoffInsertQuestion(t, pool, aptID, 0)
	OnNewQuestion(ctx, pool, handoffTestEnv, now, q2)
	if n := handoffOutboxCount(t, pool, aptID); n != 1 {
		t.Fatalf("second question must not enqueue another mail, got %d", n)
	}
	if open, _, err = OpenCounts(ctx, pool, aptID); err != nil || open != 2 {
		t.Fatalf("open count %d err=%v", open, err)
	}
	var msg string
	key := dedupeKey(aptID)
	if err := pool.QueryRow(ctx, `SELECT message FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key).Scan(&msg); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(msg, "2 guest question") {
		t.Fatalf("alert message %q", msg)
	}
}

func TestRefreshAlertUrgentIsCritical(t *testing.T) {
	pool := handoffTestPool(t)
	ctx := context.Background()
	aptID, _, _ := handoffSeedApartment(t, pool)
	handoffInsertQuestion(t, pool, aptID, 1)

	_, err := RefreshAlert(ctx, pool, handoffTestEnv, func() time.Time { return mustTime("2026-06-01T12:00:00Z") }, aptID)
	if err != nil {
		t.Fatal(err)
	}
	if level := handoffOpenAlertLevel(t, pool, aptID); level != "critical" {
		t.Fatalf("level %q", level)
	}
}

func TestOnNewQuestionMailOffStillRaisesAlert(t *testing.T) {
	pool := handoffTestPool(t)
	ctx := context.Background()
	aptID, _, _ := handoffSeedApartment(t, pool)
	envOff := func(k string) string {
		if k == "UBYHOST_MAIL_BACKEND" {
			return ""
		}
		return handoffTestEnv(k)
	}
	q := handoffInsertQuestion(t, pool, aptID, 0)
	OnNewQuestion(ctx, pool, envOff, func() time.Time { return mustTime("2026-06-01T12:00:00Z") }, q)
	if n := handoffOutboxCount(t, pool, aptID); n != 0 {
		t.Fatalf("mail off wrote %d rows", n)
	}
	var n int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, dedupeKey(aptID)).Scan(&n); err != nil || n != 1 {
		t.Fatalf("alert count %d err=%v", n, err)
	}
}

func mustTime(s string) time.Time {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t
}
