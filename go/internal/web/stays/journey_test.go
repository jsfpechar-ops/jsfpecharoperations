package stays

import (
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func ptrInt(v int) *int { return &v }

func TestBuildJourney_AllStatesAndHiding(t *testing.T) {
	today := time.Date(2026, 6, 10, 0, 0, 0, 0, time.UTC)
	baseRes := Reservation{
		ID: 1, Status: "active", Source: "airbnb", InternalName: "Vinohrady 1",
		DateFrom: "2026-06-10", DateTo: "2026-06-14",
	}

	t.Run("cancelled stay produces empty journey", func(t *testing.T) {
		r := baseRes
		r.Status = "cancelled"
		j := BuildJourney(r, Progress{}, JourneySignal{HasTTLock: true, FilesUbyPort: true}, today)
		if len(j.Steps) != 0 {
			t.Fatalf("expected 0 steps for cancelled stay, got %d", len(j.Steps))
		}
	})

	t.Run("no lock and no ubyport shows 2 steps", func(t *testing.T) {
		j := BuildJourney(baseRes, Progress{Filled: 0, Expected: ptrInt(2)}, JourneySignal{}, today)
		if len(j.Steps) != 2 {
			t.Fatalf("expected 2 steps, got %d", len(j.Steps))
		}
		if j.Steps[0].Key != "link" || j.Steps[0].Tone != "waiting" {
			t.Errorf("step 0 = %+v, want link/waiting", j.Steps[0])
		}
		if j.Steps[1].Key != "form" || j.Steps[1].Tone != "waiting" || j.Steps[1].Counter != "0/2" {
			t.Errorf("step 1 = %+v, want form/waiting/0/2", j.Steps[1])
		}
	})

	t.Run("full 4-step journey all done with ttlock", func(t *testing.T) {
		sig := JourneySignal{
			ClaimState:         "claimed",
			HasTTLock:          true,
			DoorCodeState:      "issued",
			DoorCodeNotifiedAt: "2026-06-09T12:00:00Z",
			FilesUbyPort:       true,
		}
		prog := Progress{
			Filled: 2, Expected: ptrInt(2), Status: "reported",
			Cell: layout.DeadlineCell{State: "filed_on_time"},
		}
		j := BuildJourney(baseRes, prog, sig, today)
		if len(j.Steps) != 4 {
			t.Fatalf("expected 4 steps, got %d", len(j.Steps))
		}
		want := []struct{ key, icon, tone string }{
			{"link", "mail", "done"},
			{"form", "users", "done"},
			{"code", "key-round", "done"},
			{"police", "police", "done"},
		}
		for i, w := range want {
			if j.Steps[i].Key != w.key || j.Steps[i].Icon != w.icon || j.Steps[i].Tone != w.tone {
				t.Errorf("step %d = %+v, want %+v", i, j.Steps[i], w)
			}
		}
	})

	t.Run("in-progress form, failed ttlock, overdue police", func(t *testing.T) {
		sig := JourneySignal{
			ClaimState:    "provisional",
			HasTTLock:     true,
			DoorCodeState: "failed",
			FilesUbyPort:  true,
		}
		prog := Progress{
			Filled: 1, Expected: ptrInt(3), Status: "ready",
			Cell: layout.DeadlineCell{Level: "overdue"},
		}
		j := BuildJourney(baseRes, prog, sig, today)
		if j.Steps[0].Tone != "progress" {
			t.Errorf("link tone = %s, want progress", j.Steps[0].Tone)
		}
		if j.Steps[1].Tone != "progress" || j.Steps[1].Counter != "1/3" {
			t.Errorf("form step = %+v, want progress 1/3", j.Steps[1])
		}
		if j.Steps[2].Tone != "bad" || j.Steps[2].StateKey != "failed" {
			t.Errorf("code step = %+v, want bad/failed", j.Steps[2])
		}
		if j.Steps[3].Tone != "bad" || j.Steps[3].StateKey != "action" {
			t.Errorf("police step = %+v, want bad/action", j.Steps[3])
		}
	})

	t.Run("static entry code without smart lock hides code step", func(t *testing.T) {
		sig := JourneySignal{ClaimState: "claimed", HasEntryCode: true}
		j := BuildJourney(baseRes, Progress{Filled: 1}, sig, today)
		if len(j.Steps) != 2 {
			t.Fatalf("expected 2 steps when smart lock is unused, got %d", len(j.Steps))
		}
	})

	t.Run("demo stay hides police step", func(t *testing.T) {
		r := baseRes
		r.Source = "demo"
		j := BuildJourney(r, Progress{Filled: 1}, JourneySignal{FilesUbyPort: true}, today)
		if len(j.Steps) != 2 {
			t.Fatalf("expected 2 steps for demo stay (police hidden), got %d", len(j.Steps))
		}
	})

	t.Run("incomplete guest with zero complete guests is amber progress", func(t *testing.T) {
		j := BuildJourney(baseRes, Progress{Filled: 0, Incomplete: 1, Expected: ptrInt(2)}, JourneySignal{}, today)
		if j.Steps[1].Tone != "progress" || j.Steps[1].StateKey != "partial" {
			t.Errorf("form step = %+v, want progress/partial", j.Steps[1])
		}
	})
}

func TestRenderJourneyStripAndBar(t *testing.T) {
	j := StayJourney{Steps: []JourneyStep{
		{Key: "link", Icon: "mail", Tone: "done", StateKey: "verified"},
		{Key: "form", Icon: "users", Tone: "progress", Counter: "1/2", StateKey: "partial"},
		{Key: "code", Icon: "key-round", Tone: "waiting", StateKey: "waiting"},
		{Key: "police", Icon: "police", Tone: "bad", StateKey: "action"},
	}}
	strip := string(RenderJourneyStrip("cs", j))
	if !strings.Contains(strip, `class="stay-journey"`) || !strings.Contains(strip, `data-step="police" data-tone="bad"`) {
		t.Fatalf("unexpected strip html: %s", strip)
	}
	if !strings.Contains(strip, `1/2`) || !strings.Contains(strip, `Odkaz: ověřen`) {
		t.Fatalf("strip missing counter or cs aria label: %s", strip)
	}
	bar := string(RenderJourneyBar("en", j))
	if !strings.Contains(bar, `class="stay-journey-bar"`) || !strings.Contains(bar, `needs action`) {
		t.Fatalf("unexpected bar html: %s", bar)
	}
}
