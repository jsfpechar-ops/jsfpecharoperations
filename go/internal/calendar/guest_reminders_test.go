package calendar

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
)

func TestDecideGuestReminder(t *testing.T) {
	prague, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		t.Fatal(err)
	}
	day := func(y int, m time.Month, d int) time.Time {
		return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
	}
	atPrague := func(y int, m time.Month, d, h, min int) time.Time {
		return time.Date(y, m, d, h, min, 0, 0, prague).UTC()
	}

	t.Run("day_before_respects_cooldown_and_quiet_hours", func(t *testing.T) {
		start := day(2026, 6, 2)
		today := day(2026, 6, 1)
		claimed := atPrague(2026, 6, 1, 14, 0).Format(time.RFC3339)

		// 2h59m after claim: too soon.
		if _, ok := DecideGuestReminder(10, start, today, 16, 15, claimed, atPrague(2026, 6, 1, 16, 59)); ok {
			t.Fatal("expected no reminder before 3h day-before cooldown")
		}
		// 3h00m after claim at 17:00 Prague: fires with existing day-before key.
		plan, ok := DecideGuestReminder(10, start, today, 17, 15, claimed, atPrague(2026, 6, 1, 17, 0))
		if !ok {
			t.Fatal("expected day_before reminder at 3h cooldown")
		}
		if plan.Stage != mailnotify.GuestReminderDayBefore || plan.Key != "reminder_guest:10:2026-06-02" {
			t.Fatalf("unexpected plan: %+v", plan)
		}
		// 21:00 Prague: quiet hours block sending overnight.
		if _, ok := DecideGuestReminder(10, start, today, 21, 15, claimed, atPrague(2026, 6, 1, 21, 0)); ok {
			t.Fatal("expected quiet hours to block 21:00 reminder")
		}
		// 08:59 Prague: quiet hours block early morning.
		earlyClaim := atPrague(2026, 5, 31, 12, 0).Format(time.RFC3339)
		if _, ok := DecideGuestReminder(10, start, today, 8, 15, earlyClaim, atPrague(2026, 6, 1, 8, 59)); ok {
			t.Fatal("expected quiet hours to block 08:59 reminder")
		}
	})

	t.Run("checkin_day_fires_3h_before_checkin_and_covers_late_claims", func(t *testing.T) {
		start := day(2026, 6, 2)
		today := day(2026, 6, 2)
		eveningClaim := atPrague(2026, 6, 1, 19, 30).Format(time.RFC3339)

		// 11:55 Prague for 15:00 check-in: before 12:00 lead window.
		if _, ok := DecideGuestReminder(11, start, today, 11, 15, eveningClaim, atPrague(2026, 6, 2, 11, 55)); ok {
			t.Fatal("expected no check-in-day reminder before checkin_hour - 3")
		}
		// 12:00 Prague for 15:00 check-in: fires final check-in-day reminder.
		plan, ok := DecideGuestReminder(11, start, today, 12, 15, eveningClaim, atPrague(2026, 6, 2, 12, 0))
		if !ok {
			t.Fatal("expected checkin_day reminder at 12:00 for 15:00 check-in")
		}
		if plan.Stage != mailnotify.GuestReminderCheckInDay || plan.Key != "reminder_guest:checkin:11:2026-06-02" || plan.CheckInHour != 15 {
			t.Fatalf("unexpected plan: %+v", plan)
		}

		// Early check-in hour (11:00) clamps send hour to 09:00.
		planEarly, ok := DecideGuestReminder(11, start, today, 9, 11, eveningClaim, atPrague(2026, 6, 2, 9, 0))
		if !ok || planEarly.Stage != mailnotify.GuestReminderCheckInDay || planEarly.CheckInHour != 11 {
			t.Fatalf("expected 09:00 clamp for 11:00 check-in, got ok=%v plan=%+v", ok, planEarly)
		}

		// Same-morning claim at 11:00 waits 2h before nudging at 13:00.
		morningClaim := atPrague(2026, 6, 2, 11, 0).Format(time.RFC3339)
		if _, ok := DecideGuestReminder(11, start, today, 12, 15, morningClaim, atPrague(2026, 6, 2, 12, 30)); ok {
			t.Fatal("expected 2h cooldown on check-in morning claim")
		}
		if _, ok := DecideGuestReminder(11, start, today, 13, 15, morningClaim, atPrague(2026, 6, 2, 13, 0)); !ok {
			t.Fatal("expected checkin_day reminder 2h after same-morning claim")
		}
	})

	t.Run("early_claim_gets_post_claim_nudge_after_6h_in_daytime", func(t *testing.T) {
		start := day(2026, 6, 5)
		today := day(2026, 6, 1)
		claimed := atPrague(2026, 6, 1, 10, 0).Format(time.RFC3339)

		if _, ok := DecideGuestReminder(12, start, today, 15, 15, claimed, atPrague(2026, 6, 1, 15, 59)); ok {
			t.Fatal("expected no post_claim reminder before 6h")
		}
		plan, ok := DecideGuestReminder(12, start, today, 16, 15, claimed, atPrague(2026, 6, 1, 16, 0))
		if !ok {
			t.Fatal("expected post_claim reminder at 6h")
		}
		if plan.Stage != mailnotify.GuestReminderPostClaim || plan.Key != "reminder_guest:post_claim:12:2026-06-05" {
			t.Fatalf("unexpected plan: %+v", plan)
		}
	})

	t.Run("invalid_or_missing_claimed_at_returns_false", func(t *testing.T) {
		start := day(2026, 6, 2)
		today := day(2026, 6, 1)
		now := atPrague(2026, 6, 1, 15, 0)
		for _, bad := range []string{"", "not-a-timestamp", atPrague(2026, 6, 1, 16, 0).Format(time.RFC3339)} {
			if _, ok := DecideGuestReminder(13, start, today, 15, 15, bad, now); ok {
				t.Fatalf("expected false for claimed_at=%q", bad)
			}
		}
	})
}

func TestRunGuestReminders_EndToEndCadenceAndGuardrails(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	prague, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		t.Fatal(err)
	}
	atPrague := func(y int, m time.Month, d, h, min int) time.Time {
		return time.Date(y, m, d, h, min, 0, 0, prague).UTC()
	}

	var ownerID, leID, aptID int64
	if err := pool.QueryRow(ctx,
		`INSERT INTO user_account (username, password_hash, role, created_at)
		 VALUES ('host-gr@example.test', 'x', 'host', '2026-01-01T00:00:00Z') RETURNING id`).Scan(&ownerID); err != nil {
		t.Fatalf("insert user: %v", err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO legal_entity (owner_user_id, name, contact_email, seat, created_at)
		 VALUES ($1, 'Host Entity', 'owner-gr@example.test', 'Prague', '2026-01-01T00:00:00Z') RETURNING id`, ownerID).Scan(&leID); err != nil {
		t.Fatalf("insert entity: %v", err)
	}
	if err := pool.QueryRow(ctx,
		`INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, uby_name, permalink_token, active, checkin_hour, created_at)
		 VALUES ($1, $2, 'Harbour Flat', 'Harbour Flat', 'tok-gr', 1, 15, '2026-01-01T00:00:00Z') RETURNING id`, ownerID, leID).Scan(&aptID); err != nil {
		t.Fatalf("insert apartment: %v", err)
	}

	seedStay := func(uid, dateFrom, source, claimState, email, lang string, claimedAt time.Time) int64 {
		t.Helper()
		var resID int64
		if err := pool.QueryRow(ctx,
			`INSERT INTO reservation (apartment_id, uid, date_from, date_to, status, source, declared_guests, created_at, updated_at)
			 VALUES ($1, $2, $3, '2026-06-05', 'active', $4, 2, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z') RETURNING id`,
			aptID, uid, dateFrom, source).Scan(&resID); err != nil {
			t.Fatalf("insert reservation %s: %v", uid, err)
		}
		if claimState != "" {
			if _, err := pool.Exec(ctx,
				`INSERT INTO reservation_claim (reservation_id, state, email, email_masked, lang, claimed_at, created_at, updated_at)
				 VALUES ($1, $2, $3, 'g***@example.test', $4, $5, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')`,
				resID, claimState, email, lang, claimedAt.UTC().Format(time.RFC3339)); err != nil {
				t.Fatalf("insert claim %s: %v", uid, err)
			}
		}
		return resID
	}

	// 1. Normal day-before OTA link flow: arrives June 2, claimed June 1 at 11:00 Prague.
	normalID := seedStay("uid-normal", "2026-06-02", "ical", "claimed", "normal@example.test", "en", atPrague(2026, 6, 1, 11, 0))
	// 2. Evening-before claim (previously dead zone): arrives June 2, claimed June 1 at 19:30 Prague.
	eveningID := seedStay("uid-evening", "2026-06-02", "ical", "claimed", "evening@example.test", "cs", atPrague(2026, 6, 1, 19, 30))
	// 3. Guardrails: provisional (unconfirmed) and demo stays must never be mailed.
	seedStay("uid-prov", "2026-06-02", "ical", "provisional", "prov@example.test", "en", atPrague(2026, 6, 1, 10, 0))
	seedStay("uid-demo", "2026-06-02", "demo", "claimed", "demo@example.test", "en", atPrague(2026, 6, 1, 10, 0))

	getenv := func(k string) string {
		switch k {
		case "UBYHOST_MAIL_BACKEND":
			return "console"
		case "UBYHOST_PUBLIC_BASE_URL":
			return "https://app.example.test"
		case "UBYHOST_GUEST_LANGS":
			return "en,cs"
		}
		return os.Getenv(k)
	}

	// Mail off -> nothing queued.
	offEnv := func(k string) string {
		if k == "UBYHOST_MAIL_BACKEND" {
			return ""
		}
		return getenv(k)
	}
	if n, err := RunGuestReminders(ctx, pool, offEnv, atPrague(2026, 6, 1, 14, 30)); err != nil || n != 0 {
		t.Fatalf("mail off: n=%d err=%v", n, err)
	}

	// June 1 12:30 Prague: normalID is only 1.5h after claim -> 0 queued.
	if n, err := RunGuestReminders(ctx, pool, getenv, atPrague(2026, 6, 1, 12, 30)); err != nil || n != 0 {
		t.Fatalf("too soon: n=%d err=%v", n, err)
	}

	// June 1 14:30 Prague: normalID is 3.5h after claim -> queues day-before reminder once.
	n, err := RunGuestReminders(ctx, pool, getenv, atPrague(2026, 6, 1, 14, 30))
	if err != nil {
		t.Fatalf("day_before run: %v", err)
	}
	if n != 1 {
		t.Fatalf("expected 1 day_before reminder, got %d", n)
	}
	// Repeat run is idempotent.
	if n2, err := RunGuestReminders(ctx, pool, getenv, atPrague(2026, 6, 1, 15, 0)); err != nil || n2 != 0 {
		t.Fatalf("repeat day_before run: n=%d err=%v", n2, err)
	}

	// Verify day-before payload has reply_to and updated automatic-reminder copy.
	var payloadRaw, subject string
	if err := pool.QueryRow(ctx,
		`SELECT subject, payload::text FROM email_outbox WHERE idempotency_key = $1`,
		fmt.Sprintf("reminder_guest:%d:2026-06-02", normalID)).Scan(&subject, &payloadRaw); err != nil {
		t.Fatalf("query day_before outbox: %v", err)
	}
	var payload map[string]string
	if err := json.Unmarshal([]byte(payloadRaw), &payload); err != nil {
		t.Fatalf("unmarshal payload: %v", err)
	}
	if payload["reply_to"] != "owner-gr@example.test" {
		t.Fatalf("expected reply_to owner-gr@example.test, got %q", payload["reply_to"])
	}
	if !strings.Contains(payload["text"], "final reminder on check-in day") {
		t.Fatalf("expected updated day_before note in text, got: %s", payload["text"])
	}

	// June 2 11:30 Prague: before 12:00 (checkin_hour 15 - 3) -> 0 queued.
	if n, err := RunGuestReminders(ctx, pool, getenv, atPrague(2026, 6, 2, 11, 30)); err != nil || n != 0 {
		t.Fatalf("before checkin lead window: n=%d err=%v", n, err)
	}

	// June 2 12:05 Prague: BOTH normalID (still incomplete) AND eveningID (missed day-before!) receive check-in-day reminder.
	n, err = RunGuestReminders(ctx, pool, getenv, atPrague(2026, 6, 2, 12, 5))
	if err != nil {
		t.Fatalf("checkin_day run: %v", err)
	}
	if n != 2 {
		t.Fatalf("expected 2 checkin_day reminders (normal + evening), got %d", n)
	}

	var totalRows int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM email_outbox WHERE kind = 'reminder_guest'`).Scan(&totalRows); err != nil {
		t.Fatal(err)
	}
	if totalRows != 3 {
		t.Fatalf("expected 3 total outbox rows (1 day_before + 2 checkin_day, zero provisional/demo), got %d", totalRows)
	}

	// Verify Czech evening guest received localized check-in-day reminder.
	var csSubject string
	if err := pool.QueryRow(ctx,
		`SELECT subject FROM email_outbox WHERE idempotency_key = $1`,
		fmt.Sprintf("reminder_guest:checkin:%d:2026-06-02", eveningID)).Scan(&csSubject); err != nil {
		t.Fatalf("query cs checkin outbox: %v", err)
	}
	if !strings.Contains(csSubject, "Dnes příjezd v 15:00") {
		t.Fatalf("expected Czech check-in subject, got %q", csSubject)
	}
}
