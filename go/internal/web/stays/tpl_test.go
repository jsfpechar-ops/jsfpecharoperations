package stays

import (
	"strings"
	"testing"
)

func TestSourceLabelMatchesPython(t *testing.T) {
	t.Parallel()
	tests := []struct{ lang, source, want string }{
		{"en", "manual", "Direct booking"},
		{"cs", "manual", "Přímá rezervace"},
		{"en", "airbnb", "Airbnb"},
		{"cs", "airbnb", "Airbnb"},
		{"en", "booking", "Booking.com"},
		{"en", "ical", "Calendar import"},
		{"en", "new_portal", "New portal"},
	}
	for _, tt := range []struct{ lang, from, to, want string }{
		{"en", "2026-06-15", "2026-06-17", "Mon 15 – Wed 17 Jun"},
		{"cs", "2026-06-15", "2026-06-17", "po 15. – st 17. 6."},
	} {
		got := stayRange(tt.lang, tt.from, tt.to)
		if got != tt.want {
			t.Fatalf("stayRange(%q,%q,%q) = %q, want %q", tt.lang, tt.from, tt.to, got, tt.want)
		}
	}
	for _, tt := range tests {
		got := sourceLabel(tt.lang, tt.source)
		if got != tt.want {
			t.Fatalf("sourceLabel(%q, %q) = %q, want %q", tt.lang, tt.source, got, tt.want)
		}
		if strings.Contains(got, "stays.source.") {
			t.Fatalf("sourceLabel(%q, %q) returned raw key %q", tt.lang, tt.source, got)
		}
	}
}
