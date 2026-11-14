package ical

import (
	"fmt"
	"strings"
	"time"
)

// SampleAirbnbICS is sample_calendar.sample_airbnb_ics: the bundled Airbnb-shaped
// calendar of demo mode. today is the Czech civil date (deadlines.local_now().date());
// only its year, month and day are used.
func SampleAirbnbICS(today time.Time) string {
	day := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, time.UTC)
	lines := []string{
		"BEGIN:VCALENDAR",
		"PRODID;X-RICAL-TZSOURCE=TZINFO:-//Airbnb Inc//Hosting Calendar 0.8.8//EN",
		"CALSCALE:GREGORIAN",
		"VERSION:2.0",
		"X-WR-CALNAME:UbyHost sample calendar",
	}
	// One property cannot be booked twice: Reserved stays never overlap (each
	// DTSTART >= the previous DTEND, checkout day is exclusive). The "Not
	// available" block may sit in a gap; it is skipped at sync anyway.
	stays := []struct {
		name    string
		offset  int
		nights  int
		summary string
		phone   string
	}{
		{"past-open", -8, 3, "Reserved", "4401"},
		{"arrived-yesterday", -1, 1, "Reserved", "7788"},
		{"arriving-today", 0, 1, "Reserved", "0431"},
		{"tomorrow", 1, 2, "Reserved", "2201"},
		{"later", 3, 2, "Reserved", "2202"},
		{"assigned", 5, 2, "Reserved", "2203"},
		{"lock-me", 7, 2, "Reserved", "5501"},
		{"czech-visit", 12, 2, "Reserved", "3301"},
		{"far-ahead", 45, 4, "Reserved", "6601"},
		{"blocked", 20, 2, "Airbnb (Not available)", ""},
	}
	for _, s := range stays {
		start := day.AddDate(0, 0, s.offset)
		lines = append(lines,
			"BEGIN:VEVENT",
			"DTSTART;VALUE=DATE:"+start.Format("20060102"),
			"DTEND;VALUE=DATE:"+start.AddDate(0, 0, s.nights).Format("20060102"),
			"UID:sample-"+s.name+"@airbnb.com",
			"SUMMARY:"+s.summary,
		)
		if s.phone != "" {
			lines = append(lines, fmt.Sprintf(`DESCRIPTION:Reservation URL: https://www.airbnb.com/hosting/reservations/details/HMSAMPLE%s\nPhone Number (Last 4 Digits): %s`, s.phone, s.phone))
		}
		lines = append(lines, "END:VEVENT")
	}
	lines = append(lines, "END:VCALENDAR")
	return strings.Join(lines, "\r\n") + "\r\n"
}
