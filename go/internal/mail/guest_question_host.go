package mail

import (
	"fmt"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
)

// GuestQuestionHostMail is guest_handoff.build_mail (host language only).
type GuestQuestionHostMail struct {
	Subject string
	Text    string
	HTML    string
}

// mail strings from host_i18n en (mail_notify.HOST_MAIL_LANGUAGE).
const (
	gqSubject = "A guest at %s has a question for you"
	gqHeading = "A guest has a question"
	gqIntro   = "A guest at %s asked something your guest guide does not answer yet. Leon (AI) told the guest you will reply. Answer in UbyHost; the guest sees it on the guide page."
	gqAction  = "Answer the question"
	gqFooter  = "You get this mail once per batch of open questions. Further questions wait for you in the app."
)

// BuildGuestQuestionHostMail matches guest_handoff.build_mail for English hosts.
func BuildGuestQuestionHostMail(publicBaseURL, propertyName, questionsURL string) GuestQuestionHostMail {
	lang := "en"
	intro := fmt.Sprintf(gqIntro, propertyName)
	subject := fmt.Sprintf(gqSubject, propertyName)
	text := strings.Join([]string{
		intro,
		"",
		gqAction + ": " + questionsURL,
		"",
		"--",
		"UbyHost",
		gqFooter,
	}, "\n")
	blocks := mailnotify.GuestBlocks(gqHeading, intro, questionsURL, gqAction, nil)
	html := mailnotify.Shell(mailnotify.ShellParams{
		Lang:          lang,
		Title:         propertyName,
		Preheader:     intro,
		PublicBaseURL: publicBaseURL,
		Blocks:        blocks,
		FooterLines:   []any{"UbyHost", gqFooter},
	})
	return GuestQuestionHostMail{Subject: subject, Text: text, HTML: html}
}
