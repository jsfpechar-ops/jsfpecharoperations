package mailnotify

import (
	"strings"
	"testing"
)

func TestBuildReminderHost_CheckInStarted(t *testing.T) {
	exp := 2
	for _, lang := range []string{"cs", "en", "vi"} {
		c := BuildReminderHost("https://example.test", ReminderHostInput{
			Lang:           lang,
			PropertyName:   "Blue Loft",
			Date:           "01.06.2026",
			Assigned:       "a***@example.test",
			StayURL:        "https://app.example.test/reservations/42#now",
			Claimed:        true,
			Filled:         1,
			Expected:       &exp,
			CheckInStarted: true,
			CheckInHour:    15,
		})
		if !strings.Contains(c.Subject, "15:00") || !strings.Contains(c.Subject, "Blue Loft") {
			t.Fatalf("lang=%s subject=%q missing hour/property", lang, c.Subject)
		}
		if !strings.Contains(c.Text, "15:00") {
			t.Fatalf("lang=%s text missing 15:00: %q", lang, c.Text)
		}
		if strings.Contains(c.Subject, "\u2014") || strings.Contains(c.Text, "\u2014") {
			t.Fatalf("lang=%s must not contain em-dash", lang)
		}
	}

	unclaimed := BuildReminderHost("https://example.test", ReminderHostInput{
		Lang:           "en",
		PropertyName:   "Blue Loft",
		Date:           "01.06.2026",
		StayURL:        "https://app.example.test/reservations/42#now",
		Claimed:        false,
		Filled:         0,
		Expected:       nil,
		CheckInStarted: true,
		CheckInHour:    14,
	})
	if !strings.Contains(unclaimed.Subject, "14:00") {
		t.Fatalf("unclaimed subject=%q missing 14:00", unclaimed.Subject)
	}
}
