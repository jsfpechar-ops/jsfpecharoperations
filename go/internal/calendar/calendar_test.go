package calendar

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
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

func TestUrgencyBuckets(t *testing.T) {
	checkIn := time.Date(2026, 11, 2, 0, 0, 0, 0, time.UTC)
	deadline := reportingDeadlineNaive(checkIn)
	cases := []struct {
		name string
		now  time.Time
		want string
	}{
		{"future", time.Date(2026, 11, 1, 12, 0, 0, 0, time.UTC), "future"},
		{"urgent", deadline.Add(-1 * time.Hour), "urgent"},
		{"soon", deadline.Add(-30 * time.Hour), "soon"},
		{"ok", deadline.Add(-60 * time.Hour), "ok"},
		{"overdue", deadline.Add(time.Hour), "overdue"},
	}
	for _, c := range cases {
		if got := urgency(checkIn, c.now); got != c.want {
			t.Errorf("%s: got %q want %q", c.name, got, c.want)
		}
	}
}

func TestAnchorDate(t *testing.T) {
	stay := stayRow{dateFrom: "2026-11-02", dateTo: "2026-11-04"}
	guests := []guestRow{
		{row: validation.GuestRow{StayFrom: "2026-11-05"}},
		{row: validation.GuestRow{StayFrom: "2026-11-03"}},
		{row: validation.GuestRow{StayFrom: "bogus"}},
	}
	if got, ok := anchorDate(stay, guests); !ok || got.Format("2006-01-02") != "2026-11-03" {
		t.Errorf("earliest guest stay_from: got %v %v", got, ok)
	}
	if got, ok := anchorDate(stay, nil); !ok || got.Format("2006-01-02") != "2026-11-02" {
		t.Errorf("date_from fallback: got %v %v", got, ok)
	}
}

func TestProgressStatuses(t *testing.T) {
	stay := stayRow{dateFrom: "2026-11-02", dateTo: "2026-11-04"}
	one, two := int64(1), int64(2)
	stayWith := func(declared *int64) stayRow { s := stay; s.declared = declared; return s }
	yes := func(guestRow) bool { return true }
	no := func(guestRow) bool { return false }
	sentByHand := guestRow{nationality: "DE", submitState: "sent", manualFiledAt: "2026-11-01T10:00:00", identityVerifiedAt: "x"}
	cases := []struct {
		name     string
		stay     stayRow
		guests   []guestRow
		complete func(guestRow) bool
		want     string
	}{
		{"failed", stayWith(&one), []guestRow{{nationality: "DE", submitState: "error"}}, no, "failed"},
		{"awaiting_guest", stayWith(nil), nil, no, "awaiting_guest"},
		{"incomplete via missing", stayWith(&two), []guestRow{{nationality: "DE", identityVerifiedAt: "x"}}, yes, "incomplete"},
		{"incomplete via unfinished guest", stayWith(&one), []guestRow{{nationality: "DE"}}, no, "incomplete"},
		{"awaiting_verification", stayWith(&one), []guestRow{{nationality: "DE"}}, yes, "awaiting_verification"},
		{"ready", stayWith(&one), []guestRow{{nationality: "DE", identityVerifiedAt: "x"}}, yes, "ready"},
		{"reported", stayWith(&one), []guestRow{sentByHand}, no, "reported"},
		{"not_required", stayWith(&one), []guestRow{{nationality: "CZE"}}, yes, "not_required"},
	}
	for _, c := range cases {
		if got := progressWith(c.stay, c.guests, c.complete).status; got != c.want {
			t.Errorf("%s: got %q want %q", c.name, got, c.want)
		}
	}
	override := int64(3)
	s := stayWith(&one)
	s.override = &override
	if got := expectedCount(s); got == nil || *got != 3 {
		t.Errorf("override wins: got %v", got)
	}
}

// 1095: a lead reduction below the base wins; one above it is ignored.
func TestExpectedCountLeadReduction(t *testing.T) {
	override, declared, low, high := int64(4), int64(6), int64(2), int64(9)
	if got := expectedCount(stayRow{override: &override, declared: &declared, reduced: &low}); got == nil || *got != 2 {
		t.Fatalf("reduction below the host count: got %v, want 2", got)
	}
	if got := expectedCount(stayRow{override: &override, declared: &declared, reduced: &high}); got == nil || *got != 4 {
		t.Fatalf("reduction above the host count: got %v, want 4", got)
	}
	if got := expectedCount(stayRow{declared: &declared}); got == nil || *got != 6 {
		t.Fatalf("no reduction: got %v, want 6", got)
	}
}

func TestEventKeyOrder(t *testing.T) {
	b, err := json.Marshal(eventOut{ID: 1, PropertyID: 2, Property: "A", URL: "/x"})
	if err != nil {
		t.Fatal(err)
	}
	keys := []string{`"id"`, `"propertyId"`, `"property"`, `"label"`, `"start"`, `"end"`, `"displayStart"`, `"displayEnd"`, `"timingFallback"`, `"guests"`, `"complete"`, `"expected"`, `"status"`, `"tone"`, `"preview"`, `"source"`, `"url"`}
	last := -1
	for _, k := range keys {
		i := strings.Index(string(b), k)
		if i <= last {
			t.Fatalf("key %s out of order in %s", k, b)
		}
		last = i
	}
}
