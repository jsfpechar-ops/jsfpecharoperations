package staydetail

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

func handRow(state, nationality, filedAt, markedAt, reference string) GuestRow {
	return GuestRow{Guest: Guest{
		StayGuest: stays.StayGuest{SubmitState: state, ManualFiledAt: filedAt,
			Row: validation.GuestRow{Nationality: nationality}},
		ManualMarkedAt: markedAt, ManualReference: reference,
	}}
}

func TestIsDemoStay(t *testing.T) {
	if !isDemoStay("demo") || isDemoStay("") || isDemoStay("airbnb") {
		t.Fatal("isDemoStay must be source == \"demo\"")
	}
}

func TestHandFilingView(t *testing.T) {
	now := time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)
	ago := func(d time.Duration) string { return now.Add(-d).Format("2006-01-02T15:04:05") }

	empty := handFilingView(nil, now)
	if empty.Count != 0 || empty.Candidates != 0 || empty.CanUndo || empty.FiledAt != nil || empty.UndoUntil != nil ||
		empty.DefaultFiledAt != deadlines.LocalNow(now).Format("2006-01-02T15:04") {
		t.Fatalf("empty: %+v", empty)
	}

	cand := handFilingView([]GuestRow{
		handRow("error", "DEU", "", "", ""),
		handRow("error", "CZE", "", "", ""),
		handRow("pending", "FRA", "", "", ""),
		handRow("sent", "DEU", "", "", ""),
	}, now)
	if cand.Candidates != 2 || cand.Count != 0 || cand.CanUndo {
		t.Fatalf("candidates: %+v", cand)
	}

	two := handFilingView([]GuestRow{
		handRow("sent", "DEU", ago(31*time.Hour), ago(30*time.Hour), "R-0"),
		handRow("sent", "DEU", ago(3*time.Hour), ago(2*time.Hour), "R-1"),
	}, now)
	wantUndo := deadlines.LocalNow(now.Add(-2 * time.Hour).Add(24 * time.Hour))
	wantFiled := deadlines.LocalNow(now.Add(-3 * time.Hour))
	if two.Count != 2 || !two.CanUndo || two.Reference != "R-1" ||
		two.UndoUntil == nil || !two.UndoUntil.Equal(wantUndo) ||
		two.FiledAt == nil || !two.FiledAt.Equal(wantFiled) {
		t.Fatalf("two: %+v", two)
	}

	old := handFilingView([]GuestRow{handRow("sent", "DEU", ago(31*time.Hour), ago(30*time.Hour), "")}, now)
	if old.Count != 1 || old.CanUndo || old.UndoUntil != nil {
		t.Fatalf("old: %+v", old)
	}
}
