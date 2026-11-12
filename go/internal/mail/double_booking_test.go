package mail

import (
	"strings"
	"testing"
)

func TestBuildDoubleBooking(t *testing.T) {
	c := BuildDoubleBooking("https://app.example.test", "https://app.example.test", "Test flat",
		StaySpan{From: "2027-05-05", To: "2027-05-08", Source: "airbnb"},
		StaySpan{From: "2027-05-07", To: "2027-05-10", Source: "booking"}, 42)
	if !strings.Contains(c.Subject, "Test flat") || !strings.Contains(c.Subject, "05.05.2027") {
		t.Fatalf("subject missing property or date: %q", c.Subject)
	}
	for _, want := range []string{"05.05.2027", "08.05.2027", "07.05.2027", "10.05.2027", "airbnb", "booking"} {
		if !strings.Contains(c.Text, want) {
			t.Fatalf("text missing %q:\n%s", want, c.Text)
		}
	}
	if !strings.Contains(c.HTML, "/reservations/42") {
		t.Fatalf("html missing the stay button")
	}
}
