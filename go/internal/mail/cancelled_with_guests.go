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
	html := cancelledShell(publicBaseURL, propertyName, title, []string{
		blockHeading(title),
		blockParagraph(strCancelledDetail, false),
		blockButton(stayURL, strCancelledAction),
	}, []string{"UbyHost", strCancelledFooterSupport})
	subject := strings.NewReplacer("%(property)s", propertyName, "%(date)s", date).Replace(strCancelledSubject)
	return Content{Subject: subject, Text: text, HTML: html}, nil
}

// cancelledShell is _shell in mail_notify.py: the same markup as msg.html() in
// submission_problem.go, with the page title, preheader, blocks and footer lines
// passed in.
func cancelledShell(publicBaseURL, pageTitle, preheader string, blocks, footerLines []string) string {
	var footerHTML strings.Builder
	for i, line := range footerLines {
		if i > 0 {
			footerHTML.WriteString(`<div style="padding:4px 0 0 0;">` + esc(line) + `</div>`)
		} else {
			footerHTML.WriteString(`<div>` + esc(line) + `</div>`)
		}
	}
	preheaderHTML := ""
	if preheader != "" {
		preheaderHTML = `<div style="display:none;font-size:1px;line-height:1px;max-height:0;` +
			`max-width:0;opacity:0;overflow:hidden;mso-hide:all;">` + esc(preheader) + preheaderSpacer + `</div>`
	}
	logoURL := publicBaseURL + logoPath
	width := strconv.Itoa(logoWidth)

	var b strings.Builder
	b.WriteString(`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<title>` + esc(pageTitle) + `</title>
</head>
<body style="margin:0;padding:0;background:` + colCanvas + `;">
` + preheaderHTML + `
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:` + colCanvas + `;border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:` + colSurface + `;border:1px solid ` + colLine + `;border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 24px 0 24px;">
<img src="` + esc(logoURL) + `" width="` + width + `" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:` + width + `px;max-width:100%;height:auto;">
</td></tr>
` + strings.Join(blocks, "") + `
<tr><td style="padding:28px 24px 28px 24px;">
<div style="border-top:1px solid ` + colLine + `;padding:16px 0 0 0;font:400 13px/1.6 ` + fontStack + `;color:` + colInkMuted + `;">
` + footerHTML.String() + `
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
`)
	return b.String()
}
