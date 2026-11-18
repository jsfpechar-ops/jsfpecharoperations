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