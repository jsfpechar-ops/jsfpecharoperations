package staydetail

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func TestComputeScheduledSendLabel(t *testing.T) {
	ci := time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC) // Monday
	hours24 := int64(24)
	ch15 := int64(15)
	at := time.Date(2026, 5, 29, 10, 0, 0, 0, time.UTC)

	scheduledStay := Stay{
		Reservation: stays.Reservation{
			ID: 1, Status: "active", Source: "manual",
			AutomationMode: "scheduled", SubmitAfterHours: &hours24,
		},
		CheckinHour: &ch15,
	}
	guestRow := []GuestRow{{
		Guest: Guest{
			StayGuest: stays.StayGuest{
				ID: 10, SubmitState: "pending",
				Row: validation.GuestRow{Nationality: "DEU"},
			},
			SubmittedRef: "2026-05-29T10:00:00Z",
		},
		Complete: true,
	}}

	// Pre-arrival form done Friday for Mon 15:00 check-in with 24h delay -> Tue 02.06.2026 15:00.
	if got := computeScheduledSendLabel(scheduledStay, "ready", false, guestRow, &ci, at); got != "02.06.2026 15:00" {
		t.Fatalf("scheduled label = %q, want 02.06.2026 15:00", got)
	}

	// Immediate mode for Mon 15:00 check-in -> Mon 01.06.2026 15:00.
	immStay := scheduledStay
	immStay.AutomationMode = "immediate"
	if got := computeScheduledSendLabel(immStay, "ready", false, guestRow, &ci, at); got != "01.06.2026 15:00" {
		t.Fatalf("immediate label = %q, want 01.06.2026 15:00", got)
	}

	// Manual mode, demo stay, or already-reported stay -> empty string.
	manStay := scheduledStay
	manStay.AutomationMode = "manual"
	if got := computeScheduledSendLabel(manStay, "ready", false, guestRow, &ci, at); got != "" {
		t.Fatalf("manual label = %q, want empty", got)
	}
	if got := computeScheduledSendLabel(scheduledStay, "reported", false, guestRow, &ci, at); got != "" {
		t.Fatalf("reported label = %q, want empty", got)
	}
	if got := computeScheduledSendLabel(scheduledStay, "ready", true, guestRow, &ci, at); got != "" {
		t.Fatalf("demo label = %q, want empty", got)
	}
}
