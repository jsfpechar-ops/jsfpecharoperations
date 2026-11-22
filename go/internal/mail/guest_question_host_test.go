package mail

import (
	"strings"
	"testing"
)

// Copied from guest_handoff.build_mail via App (HOST_MAIL_LANGUAGE=en).
const (
	pySubject = "A guest at Test Flat has a question for you"
	pyText    = "A guest at Test Flat asked something your guest guide does not answer yet. Leon (AI) told the guest you will reply. Answer in UbyHost; the guest sees it on the guide page.\n\nAnswer the question: https://ubyhost.example/apartments/11/guide/questions\n\n--\nUbyHost\nYou get this mail once per batch of open questions. Further questions wait for you in the app."
)

func TestBuildGuestQuestionHostMailMatchesPython(t *testing.T) {
	got := BuildGuestQuestionHostMail("https://ubyhost.example", "Test Flat", "https://ubyhost.example/apartments/11/guide/questions")
	if got.Subject != pySubject {
		t.Fatalf("subject %q", got.Subject)
	}
	if got.Text != pyText {
		t.Fatalf("text %q", got.Text)
	}
	if !strings.HasPrefix(got.HTML, "<!doctype html>\n<html lang=\"en\">") {
		t.Fatal("html shell")
	}
}
