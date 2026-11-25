package guesthandoff

import "testing"

func TestMailEnabled(t *testing.T) {
	tests := []struct {
		backend string
		want    bool
	}{
		{"console", true},
		{"CONSOLE", true},
		{"ses", true},
		{" disabled ", false},
		{"", false},
		{"stub", false},
	}
	for _, tt := range tests {
		got := mailEnabled(func(k string) string {
			if k == "UBYHOST_MAIL_BACKEND" {
				return tt.backend
			}
			return ""
		})
		if got != tt.want {
			t.Fatalf("%q got %v", tt.backend, got)
		}
	}
}

func TestQuestionsURL(t *testing.T) {
	const id int64 = 42
	want := "/apartments/42/guide/questions"
	if got := questionsURL(id); got != want {
		t.Fatalf("got %q", got)
	}
}

func TestDedupeKey(t *testing.T) {
	if got := dedupeKey(9); got != "guest_question:9" {
		t.Fatalf("got %q", got)
	}
}
