package hostweb

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

const (
	maxPropertyRails = 5
	maxCardsPerRail  = 5
)

// railCard is one compact stay card inside a phone per-property horizontal rail.
type railCard struct {
	Row    stays.Row
	Label  string
	Nights int
	Kind   string // "today" | "tomorrow" | "leaves" | "in_house" | "upcoming"
	Urgent bool
}

// propertyRail is one property's swipeable horizontal stay carousel on phone.
type propertyRail struct {
	ID           int64
	Name         string
	CalendarHref string
	MoreHref     string
	Cards        []railCard
	HasMore      bool
	TotalStays   int
	urgent       bool
	soonestISO   string
	origIdx      int
}

// desktopStayRow is one row in the desktop Today / Next 7 days table.
type desktopStayRow struct {
	Row      stays.Row
	Nights   int
	Arriving bool
	InToday  bool
	DateISO  string
}

func buildPropertyRails(apts []apartmentRow, rows []stays.Row, today time.Time) (rails []propertyRail, totalActive int) {
	todayISO := today.Format("2006-01-02")
	tomorrowISO := today.AddDate(0, 0, 1).Format("2006-01-02")

	byApt := make(map[int64][]stays.Row)
	for _, r := range rows {
		if r.Reservation.Status != "" && r.Reservation.Status != "active" {
			continue
		}
		// Keep in-house, departing today, or upcoming stays.
		to := strings.TrimSpace(r.Reservation.DateTo)
		from := strings.TrimSpace(r.Reservation.DateFrom)
		if to != "" && to < todayISO && from < todayISO {
			continue
		}
		byApt[r.Reservation.ApartmentID] = append(byApt[r.Reservation.ApartmentID], r)
	}

	var all []propertyRail
	for idx, a := range apts {
		if !a.Active {
			continue
		}
		totalActive++
		aptRows := byApt[a.ID]
		sort.SliceStable(aptRows, func(i, j int) bool {
			return aptRows[i].Reservation.DateFrom < aptRows[j].Reservation.DateFrom
		})

		rail := propertyRail{
			ID:           a.ID,
			Name:         a.Name,
			CalendarHref: fmt.Sprintf("/?cal_view=calendar&cal_property=%d", a.ID),
			MoreHref:     fmt.Sprintf("/reservations?apartment=%d", a.ID),
			TotalStays:   len(aptRows),
			soonestISO:   "9999-99-99",
			origIdx:      idx,
		}

		for _, r := range aptRows {
			from := strings.TrimSpace(r.Reservation.DateFrom)
			to := strings.TrimSpace(r.Reservation.DateTo)
			kind := railStayKind(from, to, todayISO, tomorrowISO)
			urg := railStayUrgent(r, today)
			if urg {
				rail.urgent = true
			}
			if from != "" && from < rail.soonestISO {
				rail.soonestISO = from
			}
			if len(rail.Cards) < maxCardsPerRail {
				rail.Cards = append(rail.Cards, railCard{
					Row:    r,
					Label:  stayLabel(r.Reservation),
					Nights: todayNights(r.Reservation),
					Kind:   kind,
					Urgent: urg,
				})
			}
		}
		rail.HasMore = len(aptRows) > maxCardsPerRail
		all = append(all, rail)
	}

	sort.SliceStable(all, func(i, j int) bool {
		if all[i].urgent != all[j].urgent {
			return all[i].urgent
		}
		if all[i].soonestISO != all[j].soonestISO {
			return all[i].soonestISO < all[j].soonestISO
		}
		return all[i].origIdx < all[j].origIdx
	})

	if len(all) > maxPropertyRails {
		all = all[:maxPropertyRails]
	}
	return all, totalActive
}

func railStayKind(from, to, todayISO, tomorrowISO string) string {
	switch {
	case from == todayISO:
		return "today"
	case to == todayISO:
		return "leaves"
	case from < todayISO && to > todayISO:
		return "in_house"
	case from == tomorrowISO:
		return "tomorrow"
	default:
		return "upcoming"
	}
}

func railStayUrgent(r stays.Row, today time.Time) bool {
	st := r.Progress.Status
	if st == "reported" || st == "not_required" {
		return false
	}
	if st == "failed" || r.Progress.Cell.Level == "overdue" || st == "incomplete" {
		return true
	}
	if st == "awaiting_guest" {
		if from, ok := validation.ParseISODate(r.Reservation.DateFrom); ok {
			return !from.After(today.AddDate(0, 0, 3))
		}
	}
	return false
}

// buildDesktopWindow builds the Today / Next 7 days desktop table rows.
// When rawWindow is empty, defaults to "today" if TodayRows is non-empty,
// otherwise auto-switches to "next7" so the desktop table stays useful.
func buildDesktopWindow(rows []stays.Row, todayRows []todayRow, rawWindow string, today time.Time) (window string, out []desktopStayRow) {
	todayISO := today.Format("2006-01-02")
	endISO := today.AddDate(0, 0, 7).Format("2006-01-02")

	switch strings.ToLower(strings.TrimSpace(rawWindow)) {
	case "today":
		window = "today"
	case "next7":
		window = "next7"
	default:
		if len(todayRows) > 0 {
			window = "today"
		} else {
			window = "next7"
		}
	}

	if window == "today" {
		out = make([]desktopStayRow, 0, len(todayRows))
		for _, tr := range todayRows {
			out = append(out, desktopStayRow{
				Row:      tr.Row,
				Nights:   tr.Nights,
				Arriving: tr.Arriving,
				InToday:  true,
				DateISO:  todayISO,
			})
		}
		return window, out
	}

	for _, r := range rows {
		if r.Reservation.Status != "" && r.Reservation.Status != "active" {
			continue
		}
		from := strings.TrimSpace(r.Reservation.DateFrom)
		to := strings.TrimSpace(r.Reservation.DateTo)
		arrInWin := from >= todayISO && from <= endISO
		depInWin := to >= todayISO && to <= endISO
		if !arrInWin && !depInWin {
			continue
		}
		evDate := from
		if !arrInWin {
			evDate = to
		}
		out = append(out, desktopStayRow{
			Row:      r,
			Nights:   todayNights(r.Reservation),
			Arriving: arrInWin,
			InToday:  evDate == todayISO,
			DateISO:  evDate,
		})
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].DateISO != out[j].DateISO {
			return out[i].DateISO < out[j].DateISO
		}
		return out[i].Row.Reservation.ID < out[j].Row.Reservation.ID
	})
	return window, out
}

func calPropID(apts []apartmentRow, name string) int64 {
	for _, a := range apts {
		if a.Name == name && a.Active {
			return a.ID
		}
	}
	return 0
}
