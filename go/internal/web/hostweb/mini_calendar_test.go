package hostweb

import (
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func TestRenderMiniMonthSVG(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC) // Wednesday

	t.Run("empty property renders 35 dots and today ring", func(t *testing.T) {
		svg := string(RenderMiniMonthSVG(nil, today))
		if strings.Count(svg, `class="mini-cal-dot"`) != 35 {
			t.Fatalf("expected 35 dots, got %d", strings.Count(svg, `class="mini-cal-dot"`))
		}
		if strings.Contains(svg, `class="mini-cal-bar`) {
			t.Fatalf("expected 0 stay bars, got %s", svg)
		}
		if !strings.Contains(svg, `class="mini-cal-today"`) {
			t.Fatalf("expected today ring")
		}
	})

	t.Run("multi-week stay splits across week rows and distinguishes warn vs calm", func(t *testing.T) {
		rows := []stays.Row{
			{
				Reservation: stays.Reservation{ID: 1, Status: "active", DateFrom: "2026-06-12", DateTo: "2026-06-17"},
				Progress:    stays.Progress{Status: "reported"},
			},
			{
				Reservation: stays.Reservation{ID: 2, Status: "active", DateFrom: "2026-06-18", DateTo: "2026-06-20"},
				Progress:    stays.Progress{Status: "failed", Cell: layout.DeadlineCell{Level: "overdue"}},
			},
		}
		svg := string(RenderMiniMonthSVG(rows, today))
		if strings.Count(svg, `mini-cal-bar-calm`) != 2 {
			t.Fatalf("expected 2 calm segments across week boundary, got %d in %s", strings.Count(svg, `mini-cal-bar-calm`), svg)
		}
		if strings.Count(svg, `mini-cal-bar-warn`) != 1 {
			t.Fatalf("expected 1 warn segment, got %d", strings.Count(svg, `mini-cal-bar-warn`))
		}
	})
}

func TestBuildCalendarView_SingleVsMultiProperty(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)

	t.Run("single active property auto-skips picker", func(t *testing.T) {
		d := DashboardData{
			Lang:       "cs",
			Apartments: []apartmentRow{{ID: 7, Name: "Vinohrady", Active: true}},
		}
		cv := buildCalendarView(d, "", today)
		if cv.ShowPicker {
			t.Fatalf("expected ShowPicker=false for 1 property")
		}
		if !cv.SingleProperty || cv.ShowBackToAll || cv.PropertyID != 7 {
			t.Fatalf("unexpected single-property view: %+v", cv)
		}
	})

	t.Run("2+ active properties with no cal_property shows picker", func(t *testing.T) {
		d := DashboardData{
			Lang: "en",
			Apartments: []apartmentRow{
				{ID: 1, Name: "Alpha", Active: true},
				{ID: 2, Name: "Beta", Active: true},
				{ID: 3, Name: "Archived", Active: false},
			},
		}
		cv := buildCalendarView(d, "", today)
		if !cv.ShowPicker || len(cv.IndexCards) != 2 {
			t.Fatalf("expected picker with 2 cards, got %+v", cv)
		}
		if cv.IndexCards[0].Href != "/?cal_view=calendar&cal_property=1" {
			t.Fatalf("unexpected card href: %s", cv.IndexCards[0].Href)
		}
	})

	t.Run("2+ active properties with valid cal_property enters single-property mode with back link", func(t *testing.T) {
		d := DashboardData{
			Lang: "cs",
			Apartments: []apartmentRow{
				{ID: 1, Name: "Alpha", Active: true},
				{ID: 2, Name: "Beta", Active: true},
			},
		}
		cv := buildCalendarView(d, "2", today)
		if cv.ShowPicker || !cv.SingleProperty || !cv.ShowBackToAll || cv.PropertyID != 2 || cv.PropertyName != "Beta" {
			t.Fatalf("unexpected selected view: %+v", cv)
		}
	})

	t.Run("foreign cal_property falls back to picker", func(t *testing.T) {
		d := DashboardData{
			Lang: "cs",
			Apartments: []apartmentRow{
				{ID: 1, Name: "Alpha", Active: true},
				{ID: 2, Name: "Beta", Active: true},
			},
		}
		cv := buildCalendarView(d, "999", today)
		if !cv.ShowPicker || cv.PropertyID != 0 {
			t.Fatalf("expected fallback to picker for unknown property id, got %+v", cv)
		}
	})
}
