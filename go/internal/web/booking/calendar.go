package booking

import (
	"context"
	"strings"
	"time"
)

// HorizonMonths is booking_calendar.HORIZON_MONTHS.
const HorizonMonths = 12

// Cell is one day of a month grid. State is pad, past, taken, free, start,
// range or end; Pick is the (date_from, date_to) the day's link sets, nil
// when the day is not clickable.
type Cell struct {
	Day   int        `json:"day"`
	ISO   string     `json:"iso"`
	State string     `json:"state"`
	Pick  *[2]string `json:"pick"`
}

// Grid is booking_calendar.month_grid. Prev and Next are (year, month) or nil.
type Grid struct {
	Year  int      `json:"year"`
	Month int      `json:"month"`
	Weeks [][]Cell `json:"weeks"`
	Prev  *[2]int  `json:"prev"`
	Next  *[2]int  `json:"next"`
}

// ParseDay is booking_calendar.parse_day: the stripped value as an ISO date.
func ParseDay(value string) (time.Time, bool) {
	return ParseISODate(strings.TrimSpace(value))
}

// AddMonths is booking_calendar.add_months.
func AddMonths(year, month, n int) (int, int) {
	index := year*12 + (month - 1) + n
	y := floorDiv(index, 12)
	return y, index - y*12 + 1
}

// TakenNights is booking_calendar.taken_nights: ISO dates in [start, end)
// whose night is booked (active reservation) or held (live hold).
func TakenNights(ctx context.Context, db DB, apartmentID int64, start, end, now time.Time) (map[string]bool, error) {
	out := map[string]bool{}
	type span struct{ from, to string }
	var spans []span
	read := func(sql string, args ...any) error {
		rows, err := db.Query(ctx, sql, args...)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var s span
			if err := rows.Scan(&s.from, &s.to); err != nil {
				return err
			}
			spans = append(spans, s)
		}
		return rows.Err()
	}
	if err := read(`SELECT date_from, date_to FROM reservation WHERE apartment_id = $1
		AND status = 'active' AND date_from < $2 AND date_to > $3`,
		apartmentID, isoDay(end), isoDay(start)); err != nil {
		return nil, err
	}
	if err := read(`SELECT date_from, date_to FROM booking_hold WHERE apartment_id = $1
		AND expires_at > $2 AND date_from < $3 AND date_to > $4`,
		apartmentID, StampAt(now), isoDay(end), isoDay(start)); err != nil {
		return nil, err
	}
	for _, s := range spans {
		from, ok1 := ParseISODate(prefix10(s.from))
		to, ok2 := ParseISODate(prefix10(s.to))
		if !ok1 || !ok2 {
			return nil, errBadStoredDate
		}
		if from.Before(start) {
			from = start
		}
		if to.After(end) {
			to = end
		}
		for day := from; day.Before(to); day = day.AddDate(0, 0, 1) {
			out[isoDay(day)] = true
		}
	}
	return out, nil
}

func prefix10(s string) string {
	if len(s) > 10 {
		return s[:10]
	}
	return s
}

// MonthGrid is booking_calendar.month_grid(apartment_id, year, month,
// date_from=..., date_to=...) with today = the Prague date of now.
func MonthGrid(ctx context.Context, db DB, apartmentID int64, year, month int, dateFrom, dateTo string, now time.Time) (Grid, error) {
	s, err := LoadSettings(ctx, db, apartmentID)
	if err != nil {
		return Grid{}, err
	}
	today := civil(now.In(prague))
	earliest := EarliestCheckIn(s, now)
	first, ok := civilDate(year, month, 1)
	if !ok {
		return Grid{}, errBadMonth
	}
	selFrom, haveFrom := ParseDay(dateFrom)
	selTo, haveTo := ParseDay(dateTo)
	if !haveFrom || (haveTo && !selTo.After(selFrom)) {
		haveTo = false
	}
	low := first
	if haveFrom && selFrom.Before(first) {
		low = selFrom
	}
	taken, err := TakenNights(ctx, db, apartmentID, low, first.AddDate(0, 0, 62), now)
	if err != nil {
		return Grid{}, err
	}
	nightsFree := func(a, b time.Time) bool {
		for day := a; day.Before(b); day = day.AddDate(0, 0, 1) {
			if taken[isoDay(day)] {
				return false
			}
		}
		return true
	}
	// calendar.Calendar(firstweekday=0).monthdatescalendar: Monday-first weeks.
	start := first.AddDate(0, 0, -((int(first.Weekday()) + 6) % 7))
	last := first.AddDate(0, 1, -1)
	var weeks [][]Cell
	for weekStart := start; !weekStart.After(last); weekStart = weekStart.AddDate(0, 0, 7) {
		row := make([]Cell, 0, 7)
		for i := 0; i < 7; i++ {
			day := weekStart.AddDate(0, 0, i)
			if int(day.Month()) != month {
				row = append(row, Cell{State: "pad"})
				continue
			}
			iso := isoDay(day)
			state := "free"
			if day.Before(earliest) {
				state = "past"
			} else if taken[iso] {
				state = "taken"
			}
			var pick *[2]string
			if haveFrom && !haveTo && day.After(selFrom) && nightsFree(selFrom, day) {
				pick = &[2]string{isoDay(selFrom), iso}
			} else if state == "free" {
				pick = &[2]string{iso, ""}
			}
			if haveFrom && iso == isoDay(selFrom) {
				state = "start"
			} else if haveTo && iso == isoDay(selTo) {
				state = "end"
			} else if haveFrom && haveTo && selFrom.Before(day) && day.Before(selTo) {
				state = "range"
			}
			row = append(row, Cell{Day: day.Day(), ISO: iso, State: state, Pick: pick})
		}
		weeks = append(weeks, row)
	}
	this := [2]int{today.Year(), int(today.Month())}
	py, pm := AddMonths(year, month, -1)
	ny, nm := AddMonths(year, month, 1)
	ly, lm := AddMonths(this[0], this[1], HorizonMonths)
	g := Grid{Year: year, Month: month, Weeks: weeks}
	if [2]int{py, pm} == this || ymLess(this, [2]int{py, pm}) {
		g.Prev = &[2]int{py, pm}
	}
	if !ymLess([2]int{ly, lm}, [2]int{ny, nm}) {
		g.Next = &[2]int{ny, nm}
	}
	return g, nil
}

func ymLess(a, b [2]int) bool {
	return a[0] < b[0] || (a[0] == b[0] && a[1] < b[1])
}
