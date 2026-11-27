package mailnotify

import (
	"strings"
	"testing"
)

func TestBuildReminderGuestStagesAcrossLanguages(t *testing.T) {
	SetGuestLanguages("cs,de,en,es,fr,uk")
	t.Cleanup(func() { SetGuestLanguages("") })

	expected := 3
	langs := []string{"cs", "de", "en", "es", "fr", "uk"}
	stages := []string{GuestReminderPostClaim, GuestReminderDayBefore, GuestReminderCheckInDay}

	for _, lang := range langs {
		for _, stage := range stages {
			for _, withCount := range []bool{true, false} {
				var expPtr *int
				if withCount {
					expPtr = &expected
				}
				c := BuildReminderGuest("https://example.test", ReminderGuestInput{
					Lang:         lang,
					PropertyName: "Harbour Flat",
					StayURL:      "https://example.test/l/tok/10",
					Host:         &Host{Name: "Host s.r.o.", Email: "host@example.test"},
					Filled:       1,
					Expected:     expPtr,
					Stage:        stage,
					CheckInHour:  14,
				})
				for part, s := range map[string]string{"subject": c.Subject, "text": c.Text, "html": c.HTML} {
					if strings.TrimSpace(s) == "" {
						t.Errorf("lang=%s stage=%s count=%v %s is empty", lang, stage, withCount, part)
					}
					if strings.Contains(s, "mail_reminder_guest_") {
						t.Errorf("lang=%s stage=%s count=%v %s leaked raw key: %s", lang, stage, withCount, part, s)
					}
					if strings.Contains(s, "%(") {
						t.Errorf("lang=%s stage=%s count=%v %s has unformatted placeholder: %s", lang, stage, withCount, part, s)
					}
				}
				if stage == GuestReminderCheckInDay && !strings.Contains(c.Subject, "14:00") {
					t.Errorf("lang=%s checkin subject missing formatted hour 14:00: %q", lang, c.Subject)
				}
				if stage == GuestReminderDayBefore && strings.Contains(c.Text, GuestText(lang, "mail_reminder_guest_note", nil)) {
					t.Errorf("lang=%s day_before still uses legacy one-reminder-only note", lang)
				}
			}
		}
	}
}

func TestBuildReminderGuestCheckInDefaultHour(t *testing.T) {
	c := BuildReminderGuest("https://example.test", ReminderGuestInput{
		Lang:         "en",
		PropertyName: "Harbour Flat",
		StayURL:      "https://example.test/l/tok/10",
		Stage:        GuestReminderCheckInDay,
		CheckInHour:  -1,
	})
	if !strings.Contains(c.Subject, "15:00") {
		t.Fatalf("expected fallback 15:00 in subject, got %q", c.Subject)
	}
	if !strings.Contains(c.Text, "15:00") {
		t.Fatalf("expected fallback 15:00 in text, got %q", c.Text)
	}
}
