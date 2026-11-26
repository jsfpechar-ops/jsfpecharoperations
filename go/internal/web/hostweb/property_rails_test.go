package hostweb

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func TestBuildPropertyRails_SortingCappingAndEmpty(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)

	apts := []apartmentRow{
		{ID: 1, Name: "Quiet Flat", Active: true},
		{ID: 2, Name: "Urgent Loft", Active: true},
		{ID: 3, Name: "Soon Studio", Active: true},
		{ID: 4, Name: "Empty Cabin", Active: true},
		{ID: 5, Name: "Fifth Room", Active: true},
		{ID: 6, Name: "Sixth Villa", Active: true},
		{ID: 7, Name: "Archived Apt", Active: false},
	}

	rows := []stays.Row{
		// Quiet Flat: calm stay in 10 days
		{Reservation: stays.Reservation{ID: 10, ApartmentID: 1, Status: "active", DateFrom: "2026-06-20", DateTo: "2026-06-23", InternalName: "Quiet Flat"}, Progress: stays.Progress{Status: "reported"}},
		// Urgent Loft: 6 upcoming stays, one overdue -> should sort #1 and cap at 5 cards with HasMore=true
		{Reservation: stays.Reservation{ID: 20, ApartmentID: 2, Status: "active", DateFrom: "2026-06-11", DateTo: "2026-06-13", InternalName: "Urgent Loft"}, Progress: stays.Progress{Status: "failed", Cell: layout.DeadlineCell{Level: "overdue"}}},
		{Reservation: stays.Reservation{ID: 21, ApartmentID: 2, Status: "active", DateFrom: "2026-06-14", DateTo: "2026-06-16", InternalName: "Urgent Loft"}, Progress: stays.Progress{Status: "reported"}},
		{Reservation: stays.Reservation{ID: 22, ApartmentID: 2, Status: "active", DateFrom: "2026-06-17", DateTo: "2026-06-19", InternalName: "Urgent Loft"}, Progress: stays.Progress{Status: "reported"}},
		{Reservation: stays.Reservation{ID: 23, ApartmentID: 2, Status: "active", DateFrom: "2026-06-20", DateTo: "2026-06-22", InternalName: "Urgent Loft"}, Progress: stays.Progress{Status: "reported"}},
		{Reservation: stays.Reservation{ID: 24, ApartmentID: 2, Status: "active", DateFrom: "2026-06-23", DateTo: "2026-06-25", InternalName: "Urgent Loft"}, Progress: stays.Progress{Status: "reported"}},
		{Reservation: stays.Reservation{ID: 25, ApartmentID: 2, Status: "active", DateFrom: "2026-06-26", DateTo: "2026-06-28", InternalName: "Urgent Loft"}, Progress: stays.Progress{Status: "reported"}},
		// Soon Studio: arriving today -> should sort #2 (before Quiet Flat)
		{Reservation: stays.Reservation{ID: 30, ApartmentID: 3, Status: "active", DateFrom: "2026-06-10", DateTo: "2026-06-12", InternalName: "Soon Studio"}, Progress: stays.Progress{Status: "reported"}},
		// Past stay on Empty Cabin -> ignored, rail stays empty
		{Reservation: stays.Reservation{ID: 40, ApartmentID: 4, Status: "active", DateFrom: "2026-06-01", DateTo: "2026-06-04", InternalName: "Empty Cabin"}, Progress: stays.Progress{Status: "reported"}},
	}

	rails, totalActive := buildPropertyRails(apts, rows, today)
	if totalActive != 6 {
		t.Fatalf("totalActive = %d, want 6", totalActive)
	}
	if len(rails) != 5 {
		t.Fatalf("len(rails) = %d, want 5 (capped)", len(rails))
	}
	if rails[0].ID != 2 {
		t.Errorf("rails[0].ID = %d, want 2 (Urgent Loft)", rails[0].ID)
	}
	if len(rails[0].Cards) != 5 || !rails[0].HasMore || rails[0].TotalStays != 6 {
		t.Errorf("rails[0] cards=%d hasMore=%v total=%d, want 5/true/6", len(rails[0].Cards), rails[0].HasMore, rails[0].TotalStays)
	}
	if rails[1].ID != 3 || rails[1].Cards[0].Kind != "today" {
		t.Errorf("rails[1] = id %d kind %q, want id 3 kind today", rails[1].ID, rails[1].Cards[0].Kind)
	}
	if rails[2].ID != 1 {
		t.Errorf("rails[2].ID = %d, want 1 (Quiet Flat)", rails[2].ID)
	}
	if rails[3].ID != 4 || len(rails[3].Cards) != 0 {
		t.Errorf("rails[3] = id %d cards %d, want id 4 cards 0", rails[3].ID, len(rails[3].Cards))
	}
}

func TestBuildDesktopWindow_AutoDefaultAndExplicit(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)
	rows := []stays.Row{
		{Reservation: stays.Reservation{ID: 1, Status: "active", DateFrom: "2026-06-12", DateTo: "2026-06-15"}},
		{Reservation: stays.Reservation{ID: 2, Status: "active", DateFrom: "2026-06-25", DateTo: "2026-06-28"}},
	}

	t.Run("empty today auto-switches to next7", func(t *testing.T) {
		win, out := buildDesktopWindow(rows, nil, "", today)
		if win != "next7" || len(out) != 1 || out[0].Row.Reservation.ID != 1 {
			t.Fatalf("got win=%q len=%d, want next7 len=1", win, len(out))
		}
	})

	t.Run("explicit window=today stays on today even when empty", func(t *testing.T) {
		win, out := buildDesktopWindow(rows, nil, "today", today)
		if win != "today" || len(out) != 0 {
			t.Fatalf("got win=%q len=%d, want today len=0", win, len(out))
		}
	})

	t.Run("non-empty today defaults to today", func(t *testing.T) {
		tr := []todayRow{{Row: rows[0], Nights: 3, Arriving: true}}
		win, out := buildDesktopWindow(rows, tr, "", today)
		if win != "today" || len(out) != 1 {
			t.Fatalf("got win=%q len=%d, want today len=1", win, len(out))
		}
	})
}
