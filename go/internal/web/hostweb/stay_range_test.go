package hostweb

import "testing"

func TestStayRange(t *testing.T) {
	cases := []struct {
		name, lang, from, to, want string
	}{
		{"cs same month", "cs", "2026-12-04", "2026-12-07", "pá 4. – po 7. 12."},
		{"cs across months", "cs", "2026-12-30", "2027-01-02", "st 30. 12. – so 2. 1."},
		{"en same month", "en", "2026-12-04", "2026-12-07", "Fri 4 – Mon 7 Dec"},
		{"en across months", "en", "2026-12-30", "2027-01-02", "Wed 30 Dec – Sat 2 Jan"},
		{"vi", "vi", "2026-12-04", "2026-12-07", "T6 4/12 – T2 7/12"},
		{"unknown lang uses en", "de", "2026-12-04", "2026-12-07", "Fri 4 – Mon 7 Dec"},
		{"empty date", "cs", "", "2026-12-07", ""},
		{"bad date", "en", "2026-12-04", "bad", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := stayRange(c.lang, c.from, c.to); got != c.want {
				t.Fatalf("stayRange(%q, %q, %q) = %q, want %q", c.lang, c.from, c.to, got, c.want)
			}
		})
	}
}
