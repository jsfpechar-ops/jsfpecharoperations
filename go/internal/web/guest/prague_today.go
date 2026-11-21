package guest

import (
	"time"
)

// PragueToday is claim.prague_today for booked_level windows.
func PragueToday(now func() time.Time) time.Time {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		loc = time.UTC
	}
	t := now().In(loc)
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC)
}
