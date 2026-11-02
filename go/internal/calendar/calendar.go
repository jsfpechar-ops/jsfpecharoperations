// Package calendar serves GET /dashboard/calendar, the owner-scoped reservation
// data for the dashboard calendar. It ports App/app/routes/dashboard_calendar.py.
//
// This file holds the pure parts of the port: range parsing, visual hour
// placement, the row tone and the deadline cell. The database-backed events
// list and the route are not wired yet (see docs/tasks/0682-report.md).
package calendar

import (
	"fmt"
	"strconv"
	"strings"
	"time"
)

// finished mirrors reporting.FINISHED_STATUSES.
var finished = map[string]bool{"reported": true, "not_required": true}

// parseDates mirrors dashboard_calendar.parse_dates: stay dates describe
// occupied nights, so checkout is exclusive. Dates must be YYYY-MM-DD, within
// 1900..2101, and the end must be after the start.
func parseDates(start, end string) (time.Time, time.Time, error) {
	first, ok := isoDate(start)
	if !ok {
		return time.Time{}, time.Time{}, fmt.Errorf("invalid dates")
	}
	last, ok := isoDate(end)
	if !ok {
		return time.Time{}, time.Time{}, fmt.Errorf("invalid dates")
	}
	if first.Year() < 1900 || last.Year() > 2101 || !last.After(first) {
		return time.Time{}, time.Time{}, fmt.Errorf("invalid range")
	}
	return first, last, nil
}

// isoDate accepts only the ASCII shape dddd-dd-dd, then checks the calendar.
func isoDate(s string) (time.Time, bool) {
	if len(s) != 10 || s[4] != '-' || s[7] != '-' {
		return time.Time{}, false
	}
	for i, c := range []byte(s) {
		if i == 4 || i == 7 {
			continue
		}
		if c < '0' || c > '9' {
			return time.Time{}, false
		}
	}
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		return time.Time{}, false
	}
	return t, true
}

// parseRange mirrors dashboard_calendar.parse_range: a read may span at most
// 370 days.
func parseRange(start, end string) (time.Time, time.Time, error) {
	first, last, err := parseDates(start, end)
	if err != nil {
		return time.Time{}, time.Time{}, err
	}
	if int(last.Sub(first).Hours()/24) > 370 {
		return time.Time{}, time.Time{}, fmt.Errorf("invalid range")
	}
	return first, last, nil
}

// hourOf converts a stored hour the way Python's int() does for the values
// the column can hold: nil, an int, or a string. ok is false for anything else.
func hourOf(value any) (int, bool) {
	switch v := value.(type) {
	case nil:
		return 0, false
	case int:
		return v, true
	case int64:
		return int(v), true
	case string:
		n, err := strconv.Atoi(strings.TrimSpace(v))
		if err != nil {
			return 0, false
		}
		return n, true
	}
	return 0, false
}

// hourIsValid mirrors _hour_is_valid.
func hourIsValid(value any) bool {
	h, ok := hourOf(value)
	return ok && h >= 0 && h <= 23
}

// visualHour mirrors _visual_hour: a property hour as "HH:00", or the
// noon-only fallback "12:00".
func visualHour(value any) string {
	if h, ok := hourOf(value); ok && h >= 0 && h <= 23 {
		return fmt.Sprintf("%02d:00", h)
	}
	return "12:00"
}

// displayAt mirrors _display_at.
func displayAt(day, hour string) string {
	return day + "T" + hour
}

// tone mirrors the tone choice in events(). level is the deadline cell level.
func tone(level, status string, preview bool) string {
	switch {
	case level == "overdue" && !finished[status]:
		return "overdue"
	case status == "failed" || status == "incomplete" || status == "awaiting_verification":
		return "action"
	case status == "ready" && !preview:
		return "ready"
	case finished[status]:
		return "done"
	}
	return "neutral"
}

// DeadlineCell is the subset of reporting.deadline_cell the calendar reads.
type DeadlineCell struct {
	State     string // countdown, filed_on_time, filed_late or none
	Level     string // CSS level of the badge
	LateHours int
	ByHand    bool
}

// deadlineCell mirrors reporting.deadline_cell. urgencyLevel is the value of
// deadlines.urgency for the check-in date (used only while counting down; pass
// "future" when there is no check-in). filedAt and due are nil when unknown.
// due is the reporting deadline; a filing after it is late, by whole hours
// floored and never less than one.
func deadlineCell(status, urgencyLevel string, hasCheckIn bool, filedAt, due *time.Time, byHand bool) DeadlineCell {
	cell := DeadlineCell{State: "countdown", Level: "future"}
	if hasCheckIn {
		cell.Level = urgencyLevel
	}
	if status == "not_required" {
		return DeadlineCell{State: "none", Level: "none"}
	}
	if status != "reported" {
		return cell
	}
	cell.ByHand = byHand
	if filedAt == nil {
		// Reported without a filing time on record: no countdown either.
		return DeadlineCell{State: "none", Level: "none", ByHand: byHand}
	}
	if due != nil && filedAt.After(*due) {
		hours := int(filedAt.Sub(*due).Hours())
		if hours < 1 {
			hours = 1
		}
		cell.State, cell.Level, cell.LateHours = "filed_late", "neutral", hours
		return cell
	}
	cell.State, cell.Level = "filed_on_time", "done"
	return cell
}
