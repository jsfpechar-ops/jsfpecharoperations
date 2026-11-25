package hostweb

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

// A ready stay with no UbyPort login (files=false) must not get a needs-you line.
func TestNeedsYouReadyStayWithoutFiles(t *testing.T) {
	row := stays.Row{
		Reservation: stays.Reservation{ID: 7, DateFrom: "2026-12-01", DateTo: "2026-12-03", AutomationMode: "manual", InternalName: "Test stay"},
		Progress:    stays.Progress{Status: "ready"},
	}
	today := time.Date(2026, 11, 24, 0, 0, 0, 0, time.UTC)

	noFiles, _ := needsYouLines([]stays.Row{row}, today, "cs", false, map[int64]bool{})
	if len(noFiles) != 0 {
		t.Fatalf("files=false: want 0 lines, got %d", len(noFiles))
	}

	withFiles, _ := needsYouLines([]stays.Row{row}, today, "cs", false, map[int64]bool{7: true})
	if len(withFiles) != 1 || withFiles[0].Tone != "amber" {
		t.Fatalf("files=true: want 1 amber line, got %+v", withFiles)
	}
}
