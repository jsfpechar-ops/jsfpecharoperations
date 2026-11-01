package mail

// Port of App/app/mail_notify.py cancelled_with_guests (1131-1190): the host
// e-mail for a cancelled stay that already had guest forms. The English strings
// are copied from host_i18n.STRINGS["en"]. The shell is the one in
// submission_problem.go; its footer lines differ, so it is rendered here.
// The golden test in cancelled_with_guests_test.go compares every byte with
// App/tests/golden/mail (made by scripts/mail_golden.py).

import (
	"errors"
	"strconv"
	"strings"
)

// ErrCancelledVariant is returned for a variant other than cancelled or disappeared.
var ErrCancelledVariant = errors.New("mail: unknown cancelled_with_guests variant")

const (
	strCancelledTitleCancelled   = "Stay from %(date)s with guest forms was cancelled."
	strCancelledTitleDisappeared = "Stay from %(date)s with guest forms left the calendar."
	strCancelledDetail           = "Nothing will be reported for it. If the booking only moved, set the stay back to Active."
	strCancelledSubject          = "%(property)s: stay from %(date)s cancelled in the calendar"
	strCancelledAction           = "Open stay"
	strCancelledFooterSupport    = "Questions: support@ubyhost.com"
)

// BuildCancelledWithGuests composes subject, text and HTML of the host mail.
// propertyName is the apartment's internal name, or "UbyHost" when empty (the
// caller does that, as Python does). appBaseURL carries the stay link and
// publicBaseURL the logo, as in BuildSubmissionProblem.
func BuildCancelledWithGuests(appBaseURL, publicBaseURL, lang, propertyName, dateFrom, variant string, reservationID int64) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	var titleTmpl string
	switch variant {
	case "cancelled":
		titleTmpl = strCancelledTitleCancelled
	case "disappeared":
		titleTmpl = strCancelledTitleDisappeared
	default:
		return Content{}, ErrCancelledVariant
	}
	date := fmtDate(dateFrom)
	title := strings.ReplaceAll(titleTmpl, "%(date)s", date)
	stayURL := appBaseURL + "/reservations/" + strconv.FormatInt(reservationID, 10)
	text := strings.Join([]string{title, "", strCancelledDetail, "", strCancelledAction + ": " + stayURL}, "\n")
	html := shell(publicBaseURL, propertyName, title, []string{
		blockHeading(title),
		blockParagraph(strCancelledDetail, false),
		blockButton(stayURL, strCancelledAction),
	}, []string{"UbyHost", strCancelledFooterSupport})
	subject := strings.NewReplacer("%(property)s", propertyName, "%(date)s", date).Replace(strCancelledSubject)
	return Content{Subject: subject, Text: text, HTML: html}, nil
}
