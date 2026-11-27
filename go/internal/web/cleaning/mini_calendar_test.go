package cleaning

import (
	"strings"
	"testing"
	"time"
)

func TestRenderCleaningMiniMonthSVG(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)

	t.Run("empty month has 35 dots and today ring", func(t *testing.T) {
		svg := string(renderCleaningMiniMonthSVG(nil, nil, today))
		if strings.Count(svg, `class="mini-cal-dot"`) != 35 {
			t.Fatalf("expected 35 dots, got %d", strings.Count(svg, `class="mini-cal-dot"`))
		}
		if !strings.Contains(svg, `class="mini-cal-today"`) {
			t.Fatal("expected today ring")
		}
		if strings.Contains(svg, `mini-cal-bar`) {
			t.Fatalf("expected no bars, got %s", svg)
		}
	})

	t.Run("booking and cleaning bars without guest text", func(t *testing.T) {
		bookings := []*booking{{
			PropertyID: 1,
			Start:      "2026-06-12",
			End:        "2026-06-15",
			Label:      "Must not leak guest surname",
		}}
		cleanings := []*cleaningItem{{
			PropertyID: 1,
			Date:       "2026-06-18",
		}}
		svg := string(renderCleaningMiniMonthSVG(bookings, cleanings, today))
		if strings.Count(svg, `mini-cal-bar-calm`) < 1 {
			t.Fatalf("expected calm booking bar, got %s", svg)
		}
		if strings.Count(svg, `mini-cal-bar-warn`) != 1 {
			t.Fatalf("expected 1 cleaning warn bar, got %d in %s", strings.Count(svg, `mini-cal-bar-warn`), svg)
		}
		if strings.Contains(svg, "Must not leak") {
			t.Fatal("mini calendar SVG must not embed booking labels")
		}
	})
}

func TestBuildCleaningPicker(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)
	twoProps := &payload{
		Properties: []propOut{{ID: 1, Name: "Alpha"}, {ID: 2, Name: "Beta"}},
		Events: []any{
			&booking{PropertyID: 1, Start: "2026-06-12", End: "2026-06-14"},
		},
		Cleanings: []*cleaningItem{{PropertyID: 2, Date: "2026-06-11"}},
	}

	t.Run("single property skips picker", func(t *testing.T) {
		p := &payload{Properties: []propOut{{ID: 9, Name: "Only"}}}
		v := buildCleaningPicker(p, "", today)
		if v.ShowPicker || !v.SingleProperty || v.PropertyID != 9 {
			t.Fatalf("unexpected view: %+v", v)
		}
	})

	t.Run("multi property with no selection shows picker cards", func(t *testing.T) {
		v := buildCleaningPicker(twoProps, "", today)
		if !v.ShowPicker || v.SingleProperty || len(v.IndexCards) != 2 {
			t.Fatalf("unexpected picker: %+v", v)
		}
		if v.IndexCards[0].Href != "/cleaning?cal_property=1" {
			t.Fatalf("href = %q", v.IndexCards[0].Href)
		}
		if !strings.Contains(string(v.IndexCards[0].MiniSVG), `class="mini-cal-svg"`) {
			t.Fatal("picker card must embed mini calendar SVG")
		}
	})

	t.Run("valid cal_property enters single-property mode with back", func(t *testing.T) {
		v := buildCleaningPicker(twoProps, "2", today)
		if v.ShowPicker || !v.SingleProperty || !v.ShowBackToAll || v.PropertyID != 2 || v.PropertyName != "Beta" {
			t.Fatalf("unexpected selected view: %+v", v)
		}
	})

	t.Run("unknown cal_property falls back to picker", func(t *testing.T) {
		v := buildCleaningPicker(twoProps, "999", today)
		if !v.ShowPicker || v.SingleProperty {
			t.Fatalf("expected picker fallback, got %+v", v)
		}
	})
}