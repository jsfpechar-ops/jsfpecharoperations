// Package deadlines is the statutory three-working-day reporting deadline,
// ported from App/app/deadlines.py. The Python file is the reference: every
// function here must give the same answer as its Python twin, and
// testdata/golden.json (written by App/scripts/deadlines_golden.py from the
// real Python) is compared in deadlines_test.go.
//
// Nothing calls this package yet. Times are "naive" like Python's naive
// datetimes: a time.Time in UTC whose clock fields are the Prague wall clock.
// LocalNow turns a real instant into that wall clock; the other functions take
// the wall clock as `now`.
package deadlines

import (
	"fmt"
	"math"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container
)

// ReportingWorkingDays is deadlines.REPORTING_WORKING_DAYS.
const ReportingWorkingDays = 3

// UrgencyOrder is deadlines.URGENCY_ORDER.
var UrgencyOrder = map[string]int{"overdue": 0, "urgent": 1, "soon": 2, "ok": 3, "future": 4}

var prague = mustLoadPrague()

func mustLoadPrague() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("deadlines: embedded Prague zone missing: " + err.Error())
	}
	return loc
}

// dateOnly keeps the Y/M/D of t and drops the clock and the zone.
func dateOnly(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// IsWorkingDay is deadlines.is_working_day: Monday to Friday. Public holidays
// count as working days (decision 2026-10-31). The Y/M/D of day are used.
func IsWorkingDay(day time.Time) bool {
	wd := dateOnly(day).Weekday()
	return wd != time.Saturday && wd != time.Sunday
}

// AddWorkingDays is deadlines.add_working_days: the date (UTC midnight) the
// count-th working day of a window opening on start falls on. The start day is
// the first working day when it is one; a weekend start opens the count on the
// next working day.
func AddWorkingDays(start time.Time, count int) time.Time {
	current := dateOnly(start)
	remaining := count
	if IsWorkingDay(current) {
		remaining = count - 1
	}
	for remaining > 0 {
		current = current.AddDate(0, 0, 1)
		if IsWorkingDay(current) {
			remaining--
		}
	}
	return current
}

// ReportingDeadline is deadlines.reporting_deadline: 23:59:59 on the third
// working day of the window that opens on checkIn, as a naive time.
func ReportingDeadline(checkIn time.Time) time.Time {
	day := AddWorkingDays(checkIn, ReportingWorkingDays)
	return time.Date(day.Year(), day.Month(), day.Day(), 23, 59, 59, 0, time.UTC)
}

// LocalNow is deadlines.local_now for an instant: the naive Prague wall clock.
// (Python also accepts an already naive value and returns it unchanged; here
// the caller simply passes that value on without calling LocalNow.)
func LocalNow(now time.Time) time.Time {
	l := now.In(prague)
	return time.Date(l.Year(), l.Month(), l.Day(), l.Hour(), l.Minute(), l.Second(), l.Nanosecond(), time.UTC)
}

// HoursLeft is deadlines.hours_left. now is the naive Prague wall clock.
func HoursLeft(checkIn, now time.Time) float64 {
	return ReportingDeadline(checkIn).Sub(now).Seconds() / 3600.0
}

// Urgency is deadlines.urgency: "future", "ok", "soon", "urgent" or "overdue".
func Urgency(checkIn, now time.Time) string {
	if dateOnly(checkIn).After(dateOnly(now)) {
		return "future"
	}
	left := HoursLeft(checkIn, now)
	switch {
	case left < 0:
		return "overdue"
	case left <= 24:
		return "urgent"
	case left <= 48:
		return "soon"
	}
	return "ok"
}

// TimeLeftParts is deadlines.time_left_parts: (kind, amount) for the countdown.
func TimeLeftParts(checkIn, now time.Time) (string, int) {
	if dateOnly(checkIn).After(dateOnly(now)) {
		return "arrives_days", int(dateOnly(checkIn).Sub(dateOnly(now)) / (24 * time.Hour))
	}
	left := HoursLeft(checkIn, now)
	if left < 0 {
		over := math.Abs(left)
		if over < 48 {
			return "overdue_hours", int(over)
		}
		return "overdue_days", int(math.Floor(over / 24))
	}
	if left < 48 {
		return "hours_left", int(left)
	}
	return "days_left", int(math.Floor(left / 24))
}

// DescribeTimeLeft is deadlines.describe_time_left: the English countdown the
// Python app writes into logs and stored alert text. It is data, not host UI
// copy (templates use TimeLeftParts), so it ports byte for byte.
func DescribeTimeLeft(checkIn, now time.Time) string {
	kind, amount := TimeLeftParts(checkIn, now)
	switch kind {
	case "arrives_days":
		s := "s"
		if amount == 1 {
			s = ""
		}
		return fmt.Sprintf("arrives in %d day%s", amount, s)
	case "overdue_hours":
		return fmt.Sprintf("overdue by %d h", amount)
	case "overdue_days":
		return fmt.Sprintf("overdue by %d days", amount)
	case "hours_left":
		return fmt.Sprintf("%d h left", amount)
	}
	return fmt.Sprintf("%d days left", amount)
}
