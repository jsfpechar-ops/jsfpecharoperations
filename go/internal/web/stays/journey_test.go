package stays

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func ptrInt(v int) *int { return &v }

func TestBuildJourney_FiveStepAndManualPaths(t *testing.T) {
	// Future arrival (calm waiting) vs check-in day (amber nudge)
	beforeCheckIn := time.Date(2026, 6, 8, 0, 0, 0, 0, time.UTC)
	checkInDay := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)
	baseRes := Reservation{
		ID: 1, Status: "active", Source: "airbnb", InternalName: "Vinohrady 1",
		DateFrom: "2026-06-10", DateTo: "2026-06-14", AutomationMode: "scheduled",
	}

	t.Run("cancelled stay without reported guests produces empty journey", func(t *testing.T) {
		r := baseRes
		r.Status = "cancelled"
		j := BuildJourney(r, Progress{}, JourneySignal{HasTTLock: true, FilesUbyPort: true}, checkInDay)
		if len(j.Steps) != 0 {
			t.Fatalf("expected 0 steps for cancelled stay without filing, got %d", len(j.Steps))
		}
	})

	t.Run("cancelled stay AFTER police filing keeps red warning step", func(t *testing.T) {
		r := baseRes
		r.Status = "cancelled"
		j := BuildJourney(r, Progress{ReportedCount: 2}, JourneySignal{FilesUbyPort: true}, checkInDay)
		if len(j.Steps) != 1 || j.Steps[0].Key != "police" || j.Steps[0].Tone != "bad" || j.Steps[0].StateKey != "cancelled_after_report" {
			t.Fatalf("got %+v, want single bad cancelled_after_report police step", j.Steps)
		}
		sum, tone := JourneySummary("cs", j)
		if tone != "bad" || !strings.Contains(sum, "Zrušeno po hlášení") {
			t.Fatalf("summary = (%q, %q), want bad cancelled_after_report", sum, tone)
		}
	})

	t.Run("future stay without ttlock has 4 calm waiting steps", func(t *testing.T) {
		j := BuildJourney(baseRes, Progress{Filled: 0, Expected: ptrInt(2)}, JourneySignal{FilesUbyPort: true}, beforeCheckIn)
		if len(j.Steps) != 4 {
			t.Fatalf("expected 4 steps (email, opened, form, police), got %d", len(j.Steps))
		}
		want := []struct{ key, icon, tone string }{
			{"email", "mail", "waiting"},
			{"opened", "mail-open", "waiting"},
			{"form", "users", "waiting"},
			{"police", "police", "waiting"},
		}
		for i, w := range want {
			if j.Steps[i].Key != w.key || j.Steps[i].Icon != w.icon || j.Steps[i].Tone != w.tone {
				t.Errorf("step %d = %+v, want %+v", i, j.Steps[i], w)
			}
		}
		if j.Steps[2].Counter != "0/2" {
			t.Errorf("form counter = %q, want 0/2", j.Steps[2].Counter)
		}
	})

	t.Run("check-in day with empty form nudges email and form to amber", func(t *testing.T) {
		j := BuildJourney(baseRes, Progress{Filled: 0, Expected: ptrInt(2)}, JourneySignal{FilesUbyPort: true}, checkInDay)
		if j.Steps[0].Tone != "progress" || j.Steps[0].StateKey != "not_sent" {
			t.Errorf("email = %+v, want progress/not_sent", j.Steps[0])
		}
		if j.Steps[2].Tone != "progress" || j.Steps[2].StateKey != "missing_today" {
			t.Errorf("form = %+v, want progress/missing_today", j.Steps[2])
		}
	})

	t.Run("SES email sending, sent-unopened, and failed/bounced states", func(t *testing.T) {
		sending := BuildJourney(baseRes, Progress{Expected: ptrInt(2)}, JourneySignal{
			ClaimState: "provisional", ClaimMailState: "queued", FilesUbyPort: true,
		}, beforeCheckIn)
		if sending.Steps[0].Tone != "progress" || sending.Steps[0].StateKey != "sending" {
			t.Errorf("sending email = %+v", sending.Steps[0])
		}
		if sending.Steps[1].Tone != "progress" || sending.Steps[1].StateKey != "unopened" {
			t.Errorf("sending opened = %+v", sending.Steps[1])
		}

		sent := BuildJourney(baseRes, Progress{Expected: ptrInt(2)}, JourneySignal{
			ClaimState: "provisional", ClaimMailState: "sent", FilesUbyPort: true,
		}, beforeCheckIn)
		if sent.Steps[0].Tone != "done" || sent.Steps[0].StateKey != "sent" {
			t.Errorf("sent email = %+v, want done/sent", sent.Steps[0])
		}
		if sent.Steps[1].Tone != "progress" || sent.Steps[1].StateKey != "unopened" {
			t.Errorf("sent opened = %+v, want progress/unopened", sent.Steps[1])
		}

		bounced := BuildJourney(baseRes, Progress{Expected: ptrInt(2)}, JourneySignal{
			ClaimState: "provisional", ClaimMailState: "bounced", FilesUbyPort: true,
		}, beforeCheckIn)
		if bounced.Steps[0].Tone != "bad" || bounced.Steps[0].Icon != "mail-x" || bounced.Steps[0].StateKey != "failed" {
			t.Errorf("bounced email = %+v, want bad/mail-x/failed", bounced.Steps[0])
		}
		if bounced.Steps[1].Tone != "waiting" {
			t.Errorf("bounced opened = %+v, want waiting (only email red)", bounced.Steps[1])
		}
		sum, tone := JourneySummary("en", bounced)
		if tone != "bad" || !strings.Contains(sum, "Magic link email failed") {
			t.Errorf("bounced summary = (%q, %q)", sum, tone)
		}
	})

	t.Run("full 5-step journey all done with ttlock", func(t *testing.T) {
		sig := JourneySignal{
			ClaimState:         "claimed",
			ClaimMailState:     "sent",
			HasTTLock:          true,
			DoorCodeState:      "issued",
			DoorCodeNotifiedAt: "2026-06-09T12:00:00Z",
			FilesUbyPort:       true,
			AutomationMode:     "scheduled",
		}
		prog := Progress{
			Filled: 2, Expected: ptrInt(2), ReportedCount: 2, ReportableCount: 2,
			Status: "reported", Cell: layout.DeadlineCell{State: "filed_on_time"},
		}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if len(j.Steps) != 5 {
			t.Fatalf("expected 5 steps, got %d", len(j.Steps))
		}
		want := []struct{ key, icon, tone, state string }{
			{"email", "mail", "done", "sent"},
			{"opened", "mail-open", "done", "opened"},
			{"form", "users", "done", "complete"},
			{"code", "key-round", "done", "sent"},
			{"police", "police", "done", "filed"},
		}
		for i, w := range want {
			if j.Steps[i].Key != w.key || j.Steps[i].Icon != w.icon || j.Steps[i].Tone != w.tone || j.Steps[i].StateKey != w.state {
				t.Errorf("step %d = %+v, want %+v", i, j.Steps[i], w)
			}
		}
		if j.Steps[2].LinkHref != "/housebook" {
			t.Errorf("complete form step should link to /housebook, got %q", j.Steps[2].LinkHref)
		}
	})

	t.Run("auto-scheduled police filing uses calm blue scheduled tone with timestamp", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "claimed", FilesUbyPort: true, AutomationMode: "scheduled"}
		prog := Progress{
			Filled: 2, Expected: ptrInt(2), ReportableCount: 2,
			Status: "ready", ScheduledSendLabel: "11.06. 15:00",
		}
		j := BuildJourney(baseRes, prog, sig, beforeCheckIn)
		pol := j.Steps[3]
		if pol.Tone != "scheduled" || pol.StateKey != "scheduled" || pol.Extra != "11.06. 15:00" {
			t.Fatalf("police = %+v, want scheduled/scheduled/11.06. 15:00", pol)
		}
		sum, tone := JourneySummary("cs", j)
		if tone != "scheduled" || sum != "Naplánováno · 11.06. 15:00" {
			t.Fatalf("summary = (%q, %q), want scheduled timestamp", sum, tone)
		}
	})

	t.Run("manual mode ready shows amber ready_manual", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "claimed", FilesUbyPort: true, AutomationMode: "manual"}
		prog := Progress{Filled: 2, Expected: ptrInt(2), ReportableCount: 2, Status: "ready"}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[3].Tone != "progress" || j.Steps[3].StateKey != "ready_manual" {
			t.Fatalf("police = %+v, want progress/ready_manual", j.Steps[3])
		}
	})

	t.Run("manual host guest entry resolves email and opened cleanly without glitch", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "unclaimed", FilesUbyPort: true, AutomationMode: "manual"}
		prog := Progress{Filled: 2, Expected: ptrInt(2), ReportableCount: 2, Status: "ready"}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[0].Tone != "done" || j.Steps[0].StateKey != "manual" {
			t.Errorf("email = %+v, want done/manual", j.Steps[0])
		}
		if j.Steps[1].Tone != "done" || j.Steps[1].StateKey != "manual" {
			t.Errorf("opened = %+v, want done/manual", j.Steps[1])
		}
		if j.Steps[2].Tone != "done" || j.Steps[2].StateKey != "complete" {
			t.Errorf("form = %+v, want done/complete", j.Steps[2])
		}
	})

	t.Run("manual host rescue after SES bounce clears red email once form is complete", func(t *testing.T) {
		sig := JourneySignal{
			ClaimState: "provisional", ClaimMailState: "bounced",
			FilesUbyPort: true, AutomationMode: "scheduled",
		}
		prog := Progress{Filled: 2, Expected: ptrInt(2), ReportableCount: 2, Status: "ready"}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[0].Tone != "done" || j.Steps[0].StateKey != "manual" || j.Steps[0].Icon != "mail" {
			t.Errorf("rescued email = %+v, want done/manual/mail", j.Steps[0])
		}
		if j.Steps[1].Tone != "done" || j.Steps[1].StateKey != "manual" {
			t.Errorf("rescued opened = %+v, want done/manual", j.Steps[1])
		}
	})

	t.Run("manual filed by hand turns police green even without UbyPort credentials", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "unclaimed", FilesUbyPort: false}
		prog := Progress{
			Filled: 1, Expected: ptrInt(1), ReportedCount: 1, ReportableCount: 1,
			Status: "reported", Cell: layout.DeadlineCell{State: "filed_late", ByHand: true},
		}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[3].Tone != "done" || j.Steps[3].StateKey != "filed_manual" {
			t.Fatalf("police = %+v, want done/filed_manual", j.Steps[3])
		}
	})

	t.Run("Czech-only stay shows done not_required even without UbyPort credentials", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "claimed", FilesUbyPort: false}
		prog := Progress{Filled: 2, Expected: ptrInt(2), ReportableCount: 0, Status: "not_required"}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[3].Tone != "done" || j.Steps[3].StateKey != "not_required" {
			t.Fatalf("police = %+v, want done/not_required", j.Steps[3])
		}
		sum, tone := JourneySummary("cs", j)
		if tone != "done" || !strings.Contains(sum, "ČR") {
			t.Fatalf("summary = (%q, %q), want done CZ", sum, tone)
		}
	})

	t.Run("partial early police filing shows amber progress counter instead of waiting", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "claimed", FilesUbyPort: true}
		prog := Progress{
			Filled: 2, Expected: ptrInt(3), ReportedCount: 2, ReportableCount: 2,
			Status: "incomplete",
		}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[3].Tone != "progress" || j.Steps[3].StateKey != "partial" || j.Steps[3].Counter != "2/3" {
			t.Fatalf("police = %+v, want progress/partial/2/3", j.Steps[3])
		}
		sum, tone := JourneySummary("en", j)
		if tone != "progress" || sum != "Partially filed (2/3)" {
			t.Fatalf("summary = (%q, %q)", sum, tone)
		}
	})

	t.Run("awaiting_verification shows amber verify_id", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "claimed", FilesUbyPort: true}
		prog := Progress{Filled: 1, Expected: ptrInt(1), ReportableCount: 1, Status: "awaiting_verification"}
		j := BuildJourney(baseRes, prog, sig, checkInDay)
		if j.Steps[3].Tone != "progress" || j.Steps[3].StateKey != "verify_id" {
			t.Fatalf("police = %+v, want progress/verify_id", j.Steps[3])
		}
	})

	t.Run("demo stay hides police step", func(t *testing.T) {
		r := baseRes
		r.Source = "demo"
		j := BuildJourney(r, Progress{Filled: 1}, JourneySignal{FilesUbyPort: true}, checkInDay)
		if len(j.Steps) != 3 {
			t.Fatalf("expected 3 steps for demo stay (email, opened, form), got %d", len(j.Steps))
		}
	})
}

func TestRenderJourneyStripBarSummaryAndLegend(t *testing.T) {
	j := StayJourney{Steps: []JourneyStep{
		{Key: "email", Icon: "mail", Tone: "done", StateKey: "sent"},
		{Key: "opened", Icon: "mail-open", Tone: "done", StateKey: "opened"},
		{Key: "form", Icon: "users", Tone: "done", Counter: "2/2", StateKey: "complete", LinkHref: "/housebook", LinkKey: "stays.journey.housebook_link"},
		{Key: "code", Icon: "key-round", Tone: "waiting", StateKey: "waiting"},
		{Key: "police", Icon: "police", Tone: "scheduled", StateKey: "scheduled", Extra: "11.06. 15:00"},
	}}
	strip := string(RenderJourneyStrip("cs", j))
	if !strings.Contains(strip, `class="stay-journey"`) || !strings.Contains(strip, `data-step="police" data-tone="scheduled"`) {
		t.Fatalf("unexpected strip html: %s", strip)
	}
	if !strings.Contains(strip, `2/2`) || !strings.Contains(strip, `E-mail: odeslán`) || !strings.Contains(strip, `Odkaz: otevřen`) {
		t.Fatalf("strip missing counter or cs aria labels: %s", strip)
	}
	if strings.Contains(strip, "@") {
		t.Fatalf("privacy violation: email address leaked into strip: %s", strip)
	}
	bar := string(RenderJourneyBar("en", j))
	if !strings.Contains(bar, `class="stay-journey-bar"`) || !strings.Contains(bar, `href="/housebook"`) || !strings.Contains(bar, `scheduled · 11.06. 15:00`) {
		t.Fatalf("unexpected bar html: %s", bar)
	}
	summary := string(RenderJourneySummary("en", j))
	if !strings.Contains(summary, `data-tone="scheduled"`) || !strings.Contains(summary, `Scheduled · 11.06. 15:00`) {
		t.Fatalf("unexpected summary html: %s", summary)
	}
	legend := string(RenderJourneyLegend("cs"))
	if !strings.Contains(legend, `class="journey-legend"`) || !strings.Contains(legend, `data-tone="scheduled"`) {
		t.Fatalf("unexpected legend html: %s", legend)
	}
}

func TestLoadJourneySignals_ReadsLatestClaimOutboxAndTTLockOnly(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	stamp := "2026-06-01T00:00:00"
	var ownerID int64
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at)
		VALUES ('journey-2097', 'x', 'host', 1, 1, $1) RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	var entityID int64
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (owner_user_id, name, created_at)
		VALUES ($1, 'Entity 2097', $2) RETURNING id`, ownerID, stamp).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	var aptID int64
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, permalink_token, automation_mode, checkin_hour, lock_provider, lock_id, uby_idub, uby_ws_user, uby_ws_password_enc, active, created_at)
		VALUES ($1, $2, 'Apt 2097', 'tok-2097', 'scheduled', 15, 'ttlock', 'lock-1', 'idub', 'user', 'enc', 1, $3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	var resID int64
	if err := pool.QueryRow(ctx, `INSERT INTO reservation (apartment_id, source, uid, date_from, date_to, status, created_at, updated_at)
		VALUES ($1, 'manual', 'uid-2097', '2026-06-10', '2026-06-12', 'active', $2, $2) RETURNING id`, aptID, stamp).Scan(&resID); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO reservation_claim (reservation_id, state, token_version, created_at, updated_at)
		VALUES ($1, 'provisional', 1, $2, $2)`, resID, stamp); err != nil {
		t.Fatal(err)
	}
	// Earlier claim failed, newer resend succeeded: LATERAL must pick the latest row.
	if _, err := pool.Exec(ctx, `INSERT INTO email_outbox (idempotency_key, kind, reservation_id, to_email, subject, payload, state, created_at, updated_at)
		VALUES ('claim:2097:v1', 'claim', $1, 'secret-guest@example.test', 'subj', '{}', 'failed', '2026-06-01T00:00:00', '2026-06-01T00:00:00'),
		       ('claim_resend:2097:v2', 'claim_resend', $1, 'secret-guest@example.test', 'subj', '{}', 'sent', '2026-06-02T00:00:00', '2026-06-02T00:00:00')`, resID); err != nil {
		t.Fatal(err)
	}
	sigs, err := LoadJourneySignals(ctx, pool, []int64{resID}, time.Date(2026, 6, 9, 0, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	sig := sigs[resID]
	if sig.ClaimState != "provisional" || sig.ClaimMailState != "sent" {
		t.Fatalf("got claim=%q mail=%q, want provisional/sent", sig.ClaimState, sig.ClaimMailState)
	}
	if !sig.HasTTLock || !sig.FilesUbyPort || sig.AutomationMode != "scheduled" || sig.CheckinHour == nil || *sig.CheckinHour != 15 {
		t.Fatalf("unexpected signal flags: %+v", sig)
	}
}
