package calendar

import (
	"testing"
	"time"
)

func TestParseRange(t *testing.T) {
	cases := []struct {
		name, from, to string
		ok             bool
	}{
		{"good", "2026-01-01", "2026-01-10", true},
		{"bad format", "2026/01/01", "2026-01-10", false},
		{"not a date", "2026-02-30", "2026-03-01", false},
		{"year 1899", "1899-12-31", "2026-01-10", false},
		{"year 2102", "2026-01-01", "2102-01-01", false},
		{"end equals start", "2026-01-01", "2026-01-01", false},
		{"end before start", "2026-01-10", "2026-01-01", false},
		{"370 days ok", "2026-01-01", "2027-01-06", true},
		{"371 days", "2026-01-01", "2027-01-07", false},
	}
	for _, c := range cases {
		_, _, err := parseRange(c.from, c.to)
		if (err == nil) != c.ok {
			t.Errorf("%s: got err %v, want ok=%v", c.name, err, c.ok)
		}
	}
}

func TestVisualHour(t *testing.T) {
	cases := map[string]struct {
		in   any
		want string
	}{
		"nil":   {nil, "12:00"},
		"-1":    {-1, "12:00"},
		"24":    {24, "12:00"},
		"str 7": {"7", "07:00"},
		"int 7": {7, "07:00"},
		"bad":   {"x", "12:00"},
	}
	for name, c := range cases {
		if got := visualHour(c.in); got != c.want {
			t.Errorf("%s: got %q want %q", name, got, c.want)
		}
	}
	if hourIsValid(nil) || hourIsValid(24) || !hourIsValid("7") {
		t.Errorf("hourIsValid wrong")
	}
}

func TestTone(t *testing.T) {
	statuses := []string{"ready", "reported", "not_required", "failed", "incomplete", "awaiting_verification", "awaiting_guest"}
	for _, s := range statuses {
		for _, level := range []string{"overdue", "ok"} {
			for _, preview := range []bool{false, true} {
				got := tone(level, s, preview)
				var want string
				switch {
				case level == "overdue" && s != "reported" && s != "not_required":
					want = "overdue"
				case s == "failed" || s == "incomplete" || s == "awaiting_verification":
					want = "action"
				case s == "ready" && !preview:
					want = "ready"
				case s == "reported" || s == "not_required":
					want = "done"
				default:
					want = "neutral"
				}
				if got != want {
					t.Errorf("tone(%s,%s,%v)=%s want %s", level, s, preview, got, want)
				}
			}
		}
	}
}

func TestDeadlineCell(t *testing.T) {
	due := time.Date(2026, 5, 10, 12, 0, 0, 0, time.UTC)
	onTime := due.Add(-time.Hour)
	late := due.Add(30 * time.Minute)
	lateTwo := due.Add(2*time.Hour + 10*time.Minute)

	if c := deadlineCell("ready", "soon", true, nil, &due, false); c.State != "countdown" || c.Level != "soon" {
		t.Errorf("countdown: %+v", c)
	}
	if c := deadlineCell("ready", "", false, nil, nil, false); c.Level != "future" {
		t.Errorf("no check-in: %+v", c)
	}
	if c := deadlineCell("reported", "", true, &onTime, &due, false); c.State != "filed_on_time" || c.Level != "done" {
		t.Errorf("on time: %+v", c)
	}
	if c := deadlineCell("reported", "", true, &late, &due, true); c.State != "filed_late" || c.LateHours != 1 || !c.ByHand {
		t.Errorf("late under an hour: %+v", c)
	}
	if c := deadlineCell("reported", "", true, &lateTwo, &due, false); c.State != "filed_late" || c.LateHours != 2 {
		t.Errorf("late hours floor: %+v", c)
	}
	if c := deadlineCell("reported", "", true, nil, &due, false); c.State != "none" {
		t.Errorf("reported without filing time: %+v", c)
	}
	if c := deadlineCell("not_required", "", true, nil, &due, false); c.State != "none" {
		t.Errorf("not required: %+v", c)
	}
}
