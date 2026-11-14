package exports

// Brief 1608: GET /settings/archived against the Python cases, and the
// layout's BodyAlerts path (the alert stack inside the page body, once).

import (
	"strings"
	"testing"
)

// TestArchivedPageMatchesPython replays the arch_ cases: signed out, every
// type in en/cs/vi, an unknown type, the empty states, a broken key (500).
func TestArchivedPageMatchesPython(t *testing.T) {
	if n := replayRoutes(t, "arch_"); n != 12 {
		t.Errorf("ran %d arch_ cases, want 12", n)
	}
}

// TestArchivedPageAlertsOnce: settings_archived.html includes the alert
// stack in its body and the base layout then leaves it out, so the open
// alert of the workspace is on the page exactly once.
func TestArchivedPageAlertsOnce(t *testing.T) {
	w, _ := newRoutesWorld(t)
	rec := w.do("GET", "/settings/archived", asOwner, nil, false)
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	body := rec.Body.String()
	if n := strings.Count(body, "Calendar sync failed"); n != 1 {
		t.Errorf("the alert is on the page %d times, want 1", n)
	}
	main := mainPart(body)
	if !strings.Contains(main, "Calendar sync failed") {
		t.Error("the alert is not inside <main>")
	}
}
