// Package mail renders the host mail sent when UbyPort does not take a batch,
// byte for byte as the Python code does.
//
// Port of App/app/mail_notify.py: build_submission_problem (594-692),
// _build_text (695-721), _button (724-738), _build_html (741-824) and the
// helpers they reach: _clamp_reason (114), _stay_label (208), _reason_text
// (214), the _block_* helpers (240-373), _footer_line_html (471-481), _shell
// (484-542), and validation.py parse_iso_date and fmt_date. The English strings
// are copied from host_i18n.STRINGS["en"]. The golden test in
// submission_problem_test.go compares every byte with App/tests/golden/mail.
package mail

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"
)

// Stay is one reservation linked from the mail. PropertyName is the
// apartment's internal name; Python reads it per stay.
type Stay struct {
	ID           int64
	PropertyName string
	DateFrom     string
	DateTo       string
	Summary      string
}

// Content is the subject, text part and HTML part of one message.
type Content struct {
	Subject string
	Text    string
	HTML    string
}

// ErrLanguage is returned for every language except English. Python falls back
// to English for an unknown code; the port refuses instead.
var ErrLanguage = errors.New("mail: only lang en is ported")

const (
	colInk          = "#20201e"
	colInkSecondary = "#50504c"
	colInkMuted     = "#73736e"
	colCanvas       = "#f7f7f5"
	colSurface      = "#ffffff"
	colLine         = "#e4e4e1"
	colBrandAction  = "#ad4942"
	colBrandInk     = "#963e38"
	colBrandSoft    = "#f9e9e7"
	fontStack       = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
	logoPath        = "/static/ubyhost-logo.jpg"
	logoWidth       = 180
	maxReasonChars  = 1000
)

// mail.submission_problem.subject
const strSubject = "UbyPort did not accept your report - %(property)s"

// mail.submission_problem.subject_transport
const strSubjectTransport = "Report for %(property)s not delivered yet: retrying automatically"

// mail.submission_problem.intro
const strIntro = "UbyPort did not take the guest report for %(property)s. Nothing from this attempt reached the register, so these guests are not declared yet."

// mail.submission_problem.intro_transport
const strIntroTransport = "UbyHost could not deliver the guest report for %(property)s to UbyPort. Nothing from this attempt reached the register, so these guests are not declared yet."

// mail.submission_problem.footer
const strFooter = "You are receiving this because a guest report for %(property)s was not accepted."

// mail.submission_problem.preheader
const strPreheader = "Nothing reached the register. Open the stay and send the report again."

// mail.submission_problem.preheader_transport
const strPreheaderTransport = "UbyHost will try again automatically. Nothing for you to do yet."

// mail.submission_problem.reason_label
const strReasonLabel = "What UbyPort reported"

// mail.submission_problem.reason_label_transport
const strReasonLabelTransport = "What happened"

// mail.submission_problem.next_label
const strNextLabel = "What to do next"

// mail.submission_problem.next_steps
const strNextSteps = "Open the stay, check the guest's nationality, date of birth and document number against their travel document, then send the report again."

// mail.submission_problem.next_steps_transport
const strNextStepsTransport = "Nothing to do now: UbyHost sends it again on the next run. If you get this e-mail again tomorrow, open the stay and send the report by hand."

// mail.submission_problem.next_transient
const strNextTransient = "An interrupted connection clears itself when the report is sent again. If the same record fails twice, check the data before sending again."

// mail.submission_problem.stays_label
const strStaysLabel = "Stays in this report"

// mail.submission_problem.action_dorucenka
const strActionDorucenka = "Open the report receipt (Doručenka)"

// mail.submission_problem.footer_support
const strFooterSupport = "Questions about UbyHost itself: support@ubyhost.com"

// mail.submission_problem.reason_transport
const strReasonTransport = "The connection to UbyPort failed before the report was delivered."

// mail.submission_problem.heading
const strHeading = "Your report was not accepted"

// mail.submission_problem.action_stay
const strActionStay = "Open the stay"

// preheaderSpacer is PREHEADER_SPACER: 40 repeats of a figure space, a
// zero-width no-break space and a combining grapheme joiner.
var preheaderSpacer = strings.Repeat("\u2007\ufeff\u034f", 40)

// isoDateRE is the strptime("%Y-%m-%d") pattern Python uses, anchored at both ends.
var isoDateRE = regexp.MustCompile(`^([0-9]{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12][0-9]|0[1-9]|[1-9]| [1-9])$`)

var escaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;", "'", "&#x27;")

// esc is Python's html.escape(quote=True).
func esc(s string) string {
	return escaper.Replace(s)
}

// fill is the "%" pass of host_i18n.lookup for the keys that take a property:
// %(property)s is replaced and %% becomes %. The generator refuses any other %.
func fill(tmpl, property string) string {
	parts := strings.Split(tmpl, "%(property)s")
	for i, p := range parts {
		parts[i] = strings.ReplaceAll(p, "%%", "%")
	}
	return strings.Join(parts, property)
}

// normaliseLanguage is host_i18n.normalise_language for the one ported language.
func normaliseLanguage(lang string) string {
	code := []rune(strings.ToLower(lang))
	if len(code) > 2 {
		code = code[:2]
	}
	if len(code) == 0 {
		return "en"
	}
	return string(code)
}

// fmtDate is validation.fmt_date: the first ten characters must parse as
// strptime("%Y-%m-%d"); anything else is returned unchanged.
func fmtDate(value string) string {
	prefix := []rune(value)
	if len(prefix) > 10 {
		prefix = prefix[:10]
	}
	m := isoDateRE.FindStringSubmatch(string(prefix))
	if m == nil {
		return value
	}
	year, _ := strconv.Atoi(m[1])
	month, _ := strconv.Atoi(m[2])
	day, _ := strconv.Atoi(strings.TrimSpace(m[3]))
	if year < 1 {
		return value
	}
	d := time.Date(year, time.Month(month), day, 0, 0, 0, 0, time.UTC)
	if d.Year() != year || int(d.Month()) != month || d.Day() != day {
		return value
	}
	return fmt.Sprintf("%02d.%02d.%d", day, month, year)
}

// stayLabel is _stay_label.
func stayLabel(s Stay) string {
	summary := strings.TrimSpace(s.Summary)
	dates := fmtDate(s.DateFrom) + " - " + fmtDate(s.DateTo)
	if summary != "" {
		return summary + " (" + dates + ")"
	}
	return dates
}

// clampReason is _clamp_reason: strip, cut at 1000 characters, rstrip, add an ellipsis.
func clampReason(reason string) string {
	text := strings.TrimSpace(reason)
	runes := []rune(text)
	if len(runes) <= maxReasonChars {
		return text
	}
	return strings.TrimRightFunc(string(runes[:maxReasonChars]), unicode.IsSpace) + "…"
}

// reasonLine is _reason_text.
func reasonLine(state, reason string, transport bool) string {
	if transport {
		return strReasonTransport
	}
	if detail := clampReason(reason); detail != "" {
		return detail
	}
	return state
}

func blockHeading(text string) string {
	return `<tr><td style="padding:20px 24px 0 24px;"><h1 style="margin:0;font:600 22px/1.3 ` +
		fontStack + `;color:` + colInk + `;">` + esc(text) + `</h1></td></tr>`
}

func blockParagraph(text string, muted bool) string {
	colour, size := colInkSecondary, "16"
	if muted {
		colour, size = colInkMuted, "14"
	}
	return `<tr><td style="padding:12px 24px 0 24px;"><p style="margin:0;font:400 ` + size +
		`px/1.6 ` + fontStack + `;color:` + colour + `;">` + esc(text) + `</p></td></tr>`
}

func blockSection(label, body string) string {
	return `<tr><td style="padding:24px 24px 0 24px;"><div style="font:600 14px/1.4 ` + fontStack +
		`;color:` + colInk + `;padding:0 0 8px 0;">` + esc(label) + `</div>` +
		`<p style="margin:0;font:400 15px/1.6 ` + fontStack + `;color:` + colInkSecondary + `;">` +
		esc(body) + `</p></td></tr>`
}

func blockNote(label, body string) string {
	return `<tr><td style="padding:24px 24px 0 24px;"><div style="background:` + colBrandSoft +
		`;border-radius:10px;padding:16px 18px;"><div style="font:600 14px/1.4 ` + fontStack +
		`;color:` + colBrandInk + `;padding:0 0 8px 0;">` + esc(label) + `</div>` +
		`<div style="font:400 14px/1.6 ` + fontStack + `;color:` + colInk +
		`;white-space:pre-wrap;word-break:break-word;">` + esc(body) + `</div></div></td></tr>`
}

// button is _button.
func button(url, label string) string {
	return `<table role="presentation" cellpadding="0" cellspacing="0" border="0" ` +
		`style="border-collapse:separate;margin:0 0 8px 0;">` +
		`<tr><td style="background:` + colBrandAction + `;border-radius:8px;padding:14px 24px;">` +
		`<a href="` + esc(url) + `" style="display:block;padding:0;font:600 16px/20px ` + fontStack +
		`;color:` + colSurface + `;text-decoration:none;">` + esc(label) + `</a>` +
		`</td></tr></table>`
}

func blockButton(url, label string) string {
	return `<tr><td style="padding:8px 24px 0 24px;">` + button(url, label) + `</td></tr>`
}

func blockQuietLink(url, label string) string {
	return `<tr><td style="padding:14px 24px 0 24px;"><div style="font:400 14px/1.5 ` + fontStack +
		`;color:` + colInkSecondary + `;"><a href="` + esc(url) +
		`" style="color:` + colBrandAction + `;text-decoration:underline;">` + esc(label) +
		`</a></div></td></tr>`
}

// msg holds the composed pieces both parts are built from.
type msg struct {
	publicBaseURL string
	propertyName  string
	transport     bool
	intro         string
	preheader     string
	reasonLabel   string
	reasonText    string
	nextLabel     string
	nextSteps     string
	nextTransient string
	staysLabel    string
	actionReceipt string
	footer        string
	footerSupport string
	stays         []Stay
	stayURLs      []string
	submissionURL string
}

// text is _build_text.
func (m msg) text() string {
	lines := []string{m.intro, "", m.reasonLabel + ":", m.reasonText, "", m.nextLabel + ":", m.nextSteps, "", m.nextTransient}
	if len(m.stays) > 0 {
		lines = append(lines, "", m.staysLabel+":")
		for i, s := range m.stays {
			lines = append(lines, "- "+stayLabel(s)+": "+m.stayURLs[i])
		}
	}
	if m.submissionURL != "" {
		lines = append(lines, "", m.actionReceipt+": "+m.submissionURL)
	}
	lines = append(lines, "", "--", "UbyHost", m.footer, m.footerSupport)
	return strings.Join(lines, "\n")
}

// html is _build_html and _shell.
func (m msg) html() string {
	oneStay := len(m.stays) == 1 && !m.transport
	var rows strings.Builder
	for i, s := range m.stays {
		stayLink := ""
		if !oneStay {
			stayLink = `<div style="padding:6px 0 0 0;"><a href="` + esc(m.stayURLs[i]) +
				`" style="font:600 14px/1.4 ` + fontStack + `;color:` + colBrandAction +
				`;text-decoration:underline;">` + esc(strActionStay) + `</a></div>`
		}
		rows.WriteString(`<tr><td style="padding:0 0 10px 0;border-bottom:1px solid ` + colLine + `;">` +
			`<div style="font:600 15px/1.4 ` + fontStack + `;color:` + colInk + `;">` + esc(stayLabel(s)) + `</div>` +
			`<div style="font:400 14px/1.5 ` + fontStack + `;color:` + colInkSecondary + `;">` + esc(s.PropertyName) + `</div>` +
			stayLink + `</td></tr>` +
			`<tr><td style="height:10px;line-height:10px;font-size:0;">&nbsp;</td></tr>`)
	}

	blocks := []string{
		blockHeading(strHeading),
		blockParagraph(m.intro, false),
		blockNote(m.reasonLabel, m.reasonText),
		blockSection(m.nextLabel, m.nextSteps),
		blockParagraph(m.nextTransient, true),
	}
	if len(m.stays) > 0 {
		blocks = append(blocks,
			`<tr><td style="padding:24px 24px 0 24px;"><div style="font:600 14px/1.4 `+fontStack+
				`;color:`+colInk+`;padding:0 0 10px 0;">`+esc(m.staysLabel)+`</div>`+
				`<table role="presentation" width="100%" cellpadding="0" cellspacing="0" `+
				`border="0" style="border-collapse:collapse;">`+rows.String()+`</table>`+
				`</td></tr>`)
	}
	if oneStay {
		blocks = append(blocks, blockButton(m.stayURLs[0], strActionStay))
		if m.submissionURL != "" {
			blocks = append(blocks, blockQuietLink(m.submissionURL, m.actionReceipt))
		}
	} else if m.submissionURL != "" {
		blocks = append(blocks, blockButton(m.submissionURL, m.actionReceipt))
	}

	var footerHTML strings.Builder
	for i, line := range []string{m.footer, m.footerSupport} {
		if i > 0 {
			footerHTML.WriteString(`<div style="padding:4px 0 0 0;">` + esc(line) + `</div>`)
		} else {
			footerHTML.WriteString(`<div>` + esc(line) + `</div>`)
		}
	}
	preheaderHTML := ""
	if m.preheader != "" {
		preheaderHTML = `<div style="display:none;font-size:1px;line-height:1px;max-height:0;` +
			`max-width:0;opacity:0;overflow:hidden;mso-hide:all;">` + esc(m.preheader) + preheaderSpacer + `</div>`
	}
	logoURL := m.publicBaseURL + logoPath
	width := strconv.Itoa(logoWidth)

	var b strings.Builder
	b.WriteString(`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<title>` + esc(m.propertyName) + `</title>
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

// BuildSubmissionProblem composes the subject, text and HTML of one report.
//
// appBaseURL is UBYHOST_APP_BASE_URL, or UBYHOST_PUBLIC_BASE_URL when that is
// unset; publicBaseURL is UBYHOST_PUBLIC_BASE_URL. Both come without a trailing
// slash. The logo uses publicBaseURL and the links use appBaseURL, as in Python.
// submissionID 0 means no submission link, as in Python.
func BuildSubmissionProblem(appBaseURL, publicBaseURL, lang, propertyName, state, reason string, transport bool, stays []Stay, submissionID int64) (Content, error) {
	if normaliseLanguage(lang) != "en" {
		return Content{}, ErrLanguage
	}
	subject, intro, preheader := strSubject, strIntro, strPreheader
	reasonLabel, nextSteps := strReasonLabel, strNextSteps
	if transport {
		subject, intro, preheader = strSubjectTransport, strIntroTransport, strPreheaderTransport
		reasonLabel, nextSteps = strReasonLabelTransport, strNextStepsTransport
	}
	m := msg{
		publicBaseURL: publicBaseURL,
		propertyName:  propertyName,
		transport:     transport,
		intro:         fill(intro, propertyName),
		preheader:     preheader,
		reasonLabel:   reasonLabel,
		reasonText:    reasonLine(state, reason, transport),
		nextLabel:     strNextLabel,
		nextSteps:     nextSteps,
		nextTransient: strNextTransient,
		staysLabel:    strStaysLabel,
		actionReceipt: strActionDorucenka,
		footer:        fill(strFooter, propertyName),
		footerSupport: strFooterSupport,
		stays:         stays,
	}
	if submissionID != 0 {
		m.submissionURL = appBaseURL + "/submissions/" + strconv.FormatInt(submissionID, 10)
	}
	for _, s := range stays {
		m.stayURLs = append(m.stayURLs, appBaseURL+"/reservations/"+strconv.FormatInt(s.ID, 10))
	}
	return Content{
		Subject: fill(subject, propertyName),
		Text:    m.text(),
		HTML:    m.html(),
	}, nil
}
