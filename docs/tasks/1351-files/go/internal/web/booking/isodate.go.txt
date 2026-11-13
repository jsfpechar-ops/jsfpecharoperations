package booking

import "time"

// ParseISODate is Python 3.13 date.fromisoformat (the C version): length 7,
// 8 or 10; YYYY-MM-DD, YYYYMMDD, YYYY-Www[-D] or YYYYWww[D]. Like CPython it
// ignores what follows a complete date in a 10-byte string ("2026120199").
// The result is midnight UTC.
func ParseISODate(s string) (time.Time, bool) {
	n := len(s)
	if n != 7 && n != 8 && n != 10 {
		return time.Time{}, false
	}
	p := 0
	digits := func(k int) (int, bool) {
		if p+k > n {
			return 0, false
		}
		v := 0
		for i := 0; i < k; i++ {
			c := s[p+i]
			if c < '0' || c > '9' {
				return 0, false
			}
			v = v*10 + int(c-'0')
		}
		p += k
		return v, true
	}
	year, ok := digits(4)
	if !ok {
		return time.Time{}, false
	}
	sep := p < n && s[p] == '-'
	if sep {
		p++
	}
	if p < n && s[p] == 'W' {
		p++
		week, ok := digits(2)
		if !ok {
			return time.Time{}, false
		}
		day := 1
		if p < n {
			if sep {
				if s[p] != '-' {
					return time.Time{}, false
				}
				p++
			}
			if day, ok = digits(1); !ok {
				return time.Time{}, false
			}
		}
		return isoWeekDate(year, week, day)
	}
	month, ok := digits(2)
	if !ok {
		return time.Time{}, false
	}
	if sep {
		if p >= n || s[p] != '-' {
			return time.Time{}, false
		}
		p++
	}
	day, ok := digits(2)
	if !ok {
		return time.Time{}, false
	}
	return civilDate(year, month, day)
}

// civilDate validates like the date() constructor.
func civilDate(year, month, day int) (time.Time, bool) {
	if year < 1 || year > 9999 || month < 1 || month > 12 || day < 1 {
		return time.Time{}, false
	}
	t := time.Date(year, time.Month(month), day, 0, 0, 0, 0, time.UTC)
	if t.Day() != day {
		return time.Time{}, false
	}
	return t, true
}

// isoWeekDate is CPython iso_to_ymd: week 1..52, or 53 in a long ISO year;
// day 1..7.
func isoWeekDate(year, week, day int) (time.Time, bool) {
	if year < 1 || year > 9999 {
		return time.Time{}, false
	}
	jan1 := time.Date(year, 1, 1, 0, 0, 0, 0, time.UTC)
	firstWeekday := (int(jan1.Weekday()) + 6) % 7 // Monday = 0
	if week <= 0 || week >= 53 {
		leap := year%4 == 0 && (year%100 != 0 || year%400 == 0)
		if week != 53 || !(firstWeekday == 3 || (firstWeekday == 2 && leap)) {
			return time.Time{}, false
		}
	}
	if day <= 0 || day >= 8 {
		return time.Time{}, false
	}
	// Monday of week 1 is the Monday on or before 4 January.
	jan4 := time.Date(year, 1, 4, 0, 0, 0, 0, time.UTC)
	monday := jan4.AddDate(0, 0, -((int(jan4.Weekday()) + 6) % 7))
	t := monday.AddDate(0, 0, (week-1)*7+day-1)
	if t.Year() < 1 || t.Year() > 9999 {
		return time.Time{}, false
	}
	return t, true
}
