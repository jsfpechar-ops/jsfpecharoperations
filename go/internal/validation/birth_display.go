package validation

import "time"

// DisplayBirthDate is Python display_birth_date for a stored birth date: the
// normalised DDMMYYYY shown as DD.MM.YYYY, or the stripped value when it is not
// a full 8-digit date. The stay page rows use it (guest.py _person_row).
func DisplayBirthDate(v string, today time.Time) string {
	n := normaliseBirthDate(v, today)
	if len(n) == 8 {
		digits := true
		for _, c := range n {
			if c < '0' || c > '9' {
				digits = false
				break
			}
		}
		if digits {
			return n[:2] + "." + n[2:4] + "." + n[4:]
		}
	}
	return pyStrip(v)
}
