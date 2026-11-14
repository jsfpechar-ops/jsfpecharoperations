package booking

// The booking card of the public page: property_page.py _booking_view,
// _month_param, _href, _short_day and _guests (lines 98-166, 287-291).

import (
	"context"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// CellView is one calendar day with its link ("" when not clickable).
type CellView struct {
	Day         int
	State, Href string
}

// BookingView is everything the booking card shows.
type BookingView struct {
	Slug         string
	Year, Month  int
	Weeks        [][]CellView
	PrevHref     string
	NextHref     string
	Q            *Quote
	QError       string
	Guests       int
	GuestOptions []int
	MonthValue   string
	DateFrom     string
	DateTo       string
	Arrive       string
	Depart       string
	CityTaxRate  int
	TermsVersion string
	LangCS       string
	LangEN       string
}

// pyInt is int(str(value).strip()) with 0 for a value that is not a whole
// number (property_page._guests).
func pyInt(value string) int {
	n, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil {
		return 0
	}
	return n
}

// first10 is str(value)[:10] on characters.
func first10(s string) string { return runeSlice(s, 0, 10) }

// PageHref is property_page._href: the page URL with the month, the picked
// days and the guests, in this order, ending in #book.
func PageHref(slug, lang string, year, month int, dateFrom, dateTo string, guests int) string {
	q := "lang=" + url.QueryEscape(lang) + "&month=" + url.QueryEscape(strconv.Itoa(year)+"-"+twoDigits(month))
	if dateFrom != "" {
		q += "&date_from=" + url.QueryEscape(dateFrom)
	}
	if dateTo != "" {
		q += "&date_to=" + url.QueryEscape(dateTo)
	}
	if guests != 0 {
		q += "&guests=" + strconv.Itoa(guests)
	}
	return "/p/" + slug + "?" + q + "#book"
}

func twoDigits(n int) string {
	if n < 10 {
		return "0" + strconv.Itoa(n)
	}
	return strconv.Itoa(n)
}

// monthParam is _month_param: the requested month when it lies between this
// month and HorizonMonths later, else this month.
func monthParam(value string, now time.Time) (int, int) {
	today := now.In(Prague())
	ly, lm := today.Year(), int(today.Month())
	hy, hm := AddMonths(ly, lm, HorizonMonths)
	parts := strings.Split(value, "-")
	if len(parts) != 2 {
		return ly, lm
	}
	y, err1 := strconv.Atoi(strings.TrimSpace(parts[0]))
	m, err2 := strconv.Atoi(strings.TrimSpace(parts[1]))
	if err1 != nil || err2 != nil || y < 1 || y > 9999 || m < 1 || m > 12 {
		return ly, lm
	}
	if ymLess([2]int{y, m}, [2]int{ly, lm}) || ymLess([2]int{hy, hm}, [2]int{y, m}) {
		return ly, lm
	}
	return y, m
}

// shortDay is _short_day: "5. 12." in Czech, the ISO date otherwise.
func shortDay(iso, lang string) string {
	d, ok := ParseDay(iso)
	if !ok {
		return ""
	}
	if lang == "cs" {
		return strconv.Itoa(d.Day()) + ". " + strconv.Itoa(int(d.Month())) + "."
	}
	return d.Format("2006-01-02")
}

// BuildBookingView is _booking_view. param reads the query string (or the
// form values of a re-rendered page); an absent key is "".
func BuildBookingView(ctx context.Context, db DB, slug string, apartmentID int64, lang string, param func(string) string, now time.Time) (*BookingView, error) {
	s, err := LoadSettings(ctx, db, apartmentID)
	if err != nil {
		return nil, err
	}
	y, m := monthParam(param("month"), now)
	dateFrom, dateTo := first10(param("date_from")), first10(param("date_to"))
	cap := s.MaxGuests
	if cap == 0 {
		cap = 10
	}
	if cap > MaxGuests {
		cap = MaxGuests
	}
	raw := param("guests")
	if raw == "" {
		raw = "2"
	}
	guests := pyInt(raw)
	if guests < 1 {
		guests = 1
	}
	if guests > cap {
		guests = cap
	}
	grid, err := MonthGrid(ctx, db, apartmentID, y, m, dateFrom, dateTo, now)
	if err != nil {
		return nil, err
	}
	v := &BookingView{Slug: slug, Year: grid.Year, Month: grid.Month, Guests: guests,
		MonthValue: strconv.Itoa(y) + "-" + twoDigits(m), DateFrom: dateFrom, DateTo: dateTo,
		Arrive: shortDay(dateFrom, lang), Depart: shortDay(dateTo, lang),
		CityTaxRate: s.CityTaxCZK, TermsVersion: TermsVersion}
	for _, week := range grid.Weeks {
		row := make([]CellView, len(week))
		for i, c := range week {
			row[i] = CellView{Day: c.Day, State: c.State}
			if c.Pick != nil {
				row[i].Href = PageHref(slug, lang, y, m, c.Pick[0], c.Pick[1], guests)
			}
		}
		v.Weeks = append(v.Weeks, row)
	}
	if grid.Prev != nil {
		v.PrevHref = PageHref(slug, lang, grid.Prev[0], grid.Prev[1], dateFrom, dateTo, guests)
	}
	if grid.Next != nil {
		v.NextHref = PageHref(slug, lang, grid.Next[0], grid.Next[1], dateFrom, dateTo, guests)
	}
	for n := 1; n <= cap; n++ {
		v.GuestOptions = append(v.GuestOptions, n)
	}
	_, ok1 := ParseDay(dateFrom)
	_, ok2 := ParseDay(dateTo)
	if ok1 && ok2 {
		q, err := GetQuote(ctx, db, apartmentID, dateFrom, dateTo, guests, now)
		if err != nil {
			return nil, err
		}
		if q.Error != "" {
			v.QError = q.Error
		} else {
			v.Q = &q
		}
	}
	v.LangCS = PageHref(slug, "cs", y, m, dateFrom, dateTo, guests)
	v.LangEN = PageHref(slug, "en", y, m, dateFrom, dateTo, guests)
	return v, nil
}
