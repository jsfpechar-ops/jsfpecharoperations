package mail

// Host e-mail for a double booking (brief 1170). English only, like every host
// mail (mail_notify.HOST_MAIL_LANGUAGE). The shell and blocks are the ones in
// submission_problem.go / cancelled_with_guests.go.

import (
	"strconv"
	"strings"
)

const (
	strDBSubject = "Double booking: %(property)s, %(dates)s"
	strDBTitle   = "%(property)s: two bookings overlap on %(dates)s."
	strDBIntro   = "Two bookings now cover the same nights:"
	strDBAfter   = "Only one of them can happen. Check both portals and cancel or move one of the bookings."
	strDBAction  = "Open stay"
)

// StaySpan is one booking in the mail: its dates and where it came from.
type StaySpan struct {
	From, To, Source string
}

// BuildDoubleBooking composes subject, text and HTML. propertyName is the
// apartment internal name ("UbyHost" when empty, the caller does that);
// openID is the newer reservation id the button opens.
func BuildDoubleBooking(appBaseURL, publicBaseURL, propertyName string, first, second StaySpan, openID int64) Content {
	rangeOf := func(s StaySpan) string { return fmtDate(s.From) + " \u2013 " + fmtDate(s.To) }
	sourceOf := func(s StaySpan) string {
		if s.Source == "" {
			return "ical"
		}
		return s.Source
	}
	dates := rangeOf(first)
	title := strings.NewReplacer("%(property)s", propertyName, "%(dates)s", dates).Replace(strDBTitle)
	subject := strings.NewReplacer("%(property)s", propertyName, "%(dates)s", dates).Replace(strDBSubject)
	line := func(s StaySpan) string { return rangeOf(s) + " (" + sourceOf(s) + ")" }
	stayURL := appBaseURL + "/reservations/" + strconv.FormatInt(openID, 10)
	text := strings.Join([]string{
		title, "", strDBIntro,
		"- " + line(first),
		"- " + line(second),
		"", strDBAfter, "", strDBAction + ": " + stayURL,
	}, "\n")
	html := shell(publicBaseURL, propertyName, title, []string{
		blockHeading(title),
		blockParagraph(strDBIntro, false),
		blockParagraph("- "+line(first), false),
		blockParagraph("- "+line(second), false),
		blockParagraph(strDBAfter, false),
		blockButton(stayURL, strDBAction),
	}, []string{"UbyHost", strCancelledFooterSupport})
	return Content{Subject: subject, Text: text, HTML: html}
}
