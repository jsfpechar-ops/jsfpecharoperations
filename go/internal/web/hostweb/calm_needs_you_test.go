package hostweb

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func TestCalmNeedsYouBackfillAndPastCutoff(t *testing.T) {
	today := time.Date(2026, 11, 26, 0, 0, 0, 0, time.UTC)
	overdueCell := layout.DeadlineCell{Level: "overdue", State: "overdue"}

	rows := []stays.Row{
		// 1. iCal stay before feed connected (2026-11-20), 0 guests -> suppressed.
		{
			Reservation: stays.Reservation{ID: 1, ApartmentID: 10, DateFrom: "2026-11-18", DateTo: "2026-11-21", Source: "airbnb", InternalName: "Flat A"},
			Progress:    stays.Progress{Status: "awaiting_guest", Filled: 0, Cell: overdueCell},
		},
		// 2. Manual stay before feed connected, >7d old checkout, 0 guests -> suppressed by 7d cutoff.
		{
			Reservation: stays.Reservation{ID: 2, ApartmentID: 10, DateFrom: "2026-11-10", DateTo: "2026-11-12", Source: "manual", InternalName: "Flat A"},
			Progress:    stays.Progress{Status: "awaiting_guest", Filled: 0, Cell: overdueCell},
		},
		// 3. Past stay WITH submitted guest + failed UbyPort filing -> MUST stay visible (Rule 1).
		{
			Reservation: stays.Reservation{ID: 3, ApartmentID: 10, DateFrom: "2026-11-01", DateTo: "2026-11-03", Source: "airbnb", InternalName: "Flat A"},
			Progress:    stays.Progress{Status: "failed", Filled: 1, Cell: overdueCell},
		},
	}

	files := map[int64]bool{1: true, 2: true, 3: true}
	meta := map[int64]aptNudgeMeta{10: {EarliestFeedDate: "2026-11-20", HasAnyClaim: true}}
	lines, n := calmNeedsYouLines(rows, today, "en", false, files, meta, false)
	if n != 1 || lines[0].StayID != 3 || lines[0].Tone != "red" {
		t.Fatalf("want only Rule-1 stay #3 red, got %+v", lines)
	}
}

func TestCalmNeedsYouZeroClaimsCollapseAndSnooze(t *testing.T) {
	today := time.Date(2026, 11, 26, 0, 0, 0, 0, time.UTC)
	overdueCell := layout.DeadlineCell{Level: "overdue", State: "overdue"}

	rows := []stays.Row{
		{
			Reservation: stays.Reservation{ID: 11, ApartmentID: 20, DateFrom: "2026-11-24", DateTo: "2026-11-27", Source: "booking", InternalName: "Flat B"},
			Progress:    stays.Progress{Status: "awaiting_guest", Filled: 0, Cell: overdueCell},
		},
		{
			Reservation: stays.Reservation{ID: 12, ApartmentID: 20, DateFrom: "2026-11-26", DateTo: "2026-11-29", Source: "booking", InternalName: "Flat B"},
			Progress:    stays.Progress{Status: "awaiting_guest", Filled: 0},
		},
		{
			Reservation: stays.Reservation{ID: 13, ApartmentID: 21, DateFrom: "2026-11-25", DateTo: "2026-11-28", Source: "airbnb", InternalName: "Flat C"},
			Progress:    stays.Progress{Status: "awaiting_guest", Filled: 0},
		},
		{
			Reservation: stays.Reservation{ID: 14, ApartmentID: 21, DateFrom: "2026-11-26", DateTo: "2026-11-30", Source: "airbnb", InternalName: "Flat C"},
			Progress:    stays.Progress{Status: "awaiting_guest", Filled: 0},
		},
	}

	files := map[int64]bool{11: true, 12: true, 13: true, 14: true}
	meta := map[int64]aptNudgeMeta{
		20: {EarliestFeedDate: "2026-11-20", HasAnyClaim: false},
		21: {EarliestFeedDate: "2026-11-20", HasAnyClaim: false},
	}

	lines, n := calmNeedsYouLines(rows, today, "en", false, files, meta, false)
	if n != 1 || lines[0].Kind != guestLinkNudgeKind || lines[0].Tone != "amber" {
		t.Fatalf("want 1 collapsed guest_link_nudge card, got %+v", lines)
	}
	if lines[0].Href != propertyGuestsURL(20) {
		t.Fatalf("unexpected href %q", lines[0].Href)
	}

	// Snoozed hides the collapsed nudge card.
	snoozedLines, sn := calmNeedsYouLines(rows, today, "en", false, files, meta, true)
	if sn != 0 {
		t.Fatalf("snoozed: want 0 lines, got %+v", snoozedLines)
	}
}

func TestIsNudgeSnoozed(t *testing.T) {
	today := time.Date(2026, 11, 26, 0, 0, 0, 0, time.UTC)
	if !isNudgeSnoozed("2026-11-20T10:00:00Z", today) {
		t.Fatal("6 days ago should be snoozed")
	}
	if isNudgeSnoozed("2026-11-01T10:00:00Z", today) {
		t.Fatal("25 days ago should not be snoozed")
	}
}
