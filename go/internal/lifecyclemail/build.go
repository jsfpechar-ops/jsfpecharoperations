package lifecyclemail

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
)

// Content is the subject, text part and HTML part of one message.
type Content struct {
	Subject string
	Text    string
	HTML    string
}

// ErrLanguage is returned for every language except English. Python falls back
// to English for an unknown code; the port refuses instead (the job only ever
// asks for mail_notify.HOST_MAIL_LANGUAGE, "en").
var ErrLanguage = errors.New("lifecyclemail: only lang en is ported")

// ErrKind is returned for a kind that is not a lifecycle kind.
var ErrKind = errors.New("lifecyclemail: unknown lifecycle kind")

// hostMailLanguage is mail_notify.HOST_MAIL_LANGUAGE.
const hostMailLanguage = "en"

const (
	colInk          = "#20201e"
	colInkSecondary = "#50504c"
	colInkMuted     = "#73736e"
	colCanvas       = "#f7f7f5"
	colSurface      = "#ffffff"
	colLine         = "#e4e4e1"
	colBrandAction  = "#ad4942"
	fontStack       = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
	logoPath        = "/static/ubyhost-logo.jpg"
	logoWidth       = "180"
)

// preheaderSpacer is PREHEADER_SPACER: 40 repeats of a figure space, a
// zero-width no-break space and a combining grapheme joiner.
var preheaderSpacer = strings.Repeat("\u2007\ufeff\u034f", 40)

// actions is mail_notify.LIFECYCLE_ACTIONS, in the order of lifecycle_mail.TRIGGERS.
var actions = map[string]string{
	"lifecycle_no_property": "/apartments/new",
	"lifecycle_no_calendar": "/apartments",
	"lifecycle_no_guest":    "/apartments#property-summaries",
}

// tipCopy is host_i18n.STRINGS["en"], keys mail.lifecycle.<kind>.<part>.
type tipCopy struct{ subject, heading, intro, next, action string }

var copies = map[string]tipCopy{
	"lifecycle_no_property": {
		subject: "Add your first property to UbyHost",
		heading: "Add your first property",
		intro:   "You signed in to UbyHost a few days ago but have not added a property yet.",
		next:    "It takes about five minutes: the address, your UbyPort access and what guests need to know on arrival. After that, UbyHost can collect guest details and file the police reports for you.",
		action:  "Add a property",
	},
	"lifecycle_no_calendar": {
		subject: "Connect your booking calendar",
		heading: "Connect your booking calendar",
		intro:   "Your property is set up, but no booking calendar is connected yet.",
		next:    "Paste the iCal link from Airbnb, Booking.com or your channel manager into the property. UbyHost then picks up every stay on its own, so no guest is missed.",
		action:  "Connect a calendar",
	},
	"lifecycle_no_guest": {
		subject: "Send your guests the registration link",
		heading: "Send your guests the registration link",
		intro:   "Your calendar is connected, but no guest has completed registration yet.",
		next:    "Put the property's guest link in your booking message. Guests fill in their details on their phone, and UbyHost files the report.",
		action:  "Open guest links",
	},
}

// mail.lifecycle.signoff, .footer and .unsubscribe_label.
const (
	strSignoff          = "Questions? Reply to this e-mail or write to %(support)s."
	strFooter           = "You are receiving this because you created a UbyHost account and have not finished setting it up. Don't want these setup tips? %(unsubscribe)s. You will still receive essential account and service e-mails. Sender: %(name)s, IČO %(ico)s, %(address)s. Privacy: %(privacy)s."
	strUnsubscribeLabel = "Unsubscribe with one click"
)

var escaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;", "'", "&#x27;")

// esc is Python's html.escape(quote=True).
func esc(s string) string { return escaper.Replace(s) }

// markerRE is _FooterSentence._MARKER (Python's \w is Unicode).
var markerRE = regexp.MustCompile(`%\(([\p{L}\p{N}_]+)\)s`)

type link struct{ label, href string }

// footerSentence is mail_notify._FooterSentence: text with %(name)s markers
// and the links they stand for.
type footerSentence struct {
	text  string
	links map[string]link
}

// parts is _parts: re.split alternates text and marker names.
func (f footerSentence) parts() (texts []string, marks []link) {
	last := 0
	for _, m := range markerRE.FindAllStringSubmatchIndex(f.text, -1) {
		texts = append(texts, f.text[last:m[0]])
		marks = append(marks, f.links[f.text[m[2]:m[3]]])
		last = m[1]
	}
	texts = append(texts, f.text[last:])
	return texts, marks
}

func (f footerSentence) plain() string {
	texts, marks := f.parts()
	var b strings.Builder
	for i, t := range texts {
		b.WriteString(t)
		if i < len(marks) {
			if marks[i].label != "" {
				b.WriteString(marks[i].label + " (" + marks[i].href + ")")
			} else {
				b.WriteString(marks[i].href)
			}
		}
	}
	return b.String()
}

func (f footerSentence) html() string {
	texts, marks := f.parts()
	var b strings.Builder
	for i, t := range texts {
		b.WriteString(esc(t))
		if i < len(marks) {
			label := marks[i].label
			if label == "" {
				label = marks[i].href
			}
			b.WriteString(`<a href="` + esc(marks[i].href) + `" style="color:` + colInkSecondary +
				`;text-decoration:underline;">` + esc(label) + `</a>`)
		}
	}
	return b.String()
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

func blockButton(url, label string) string {
	return `<tr><td style="padding:8px 24px 0 24px;">` +
		`<table role="presentation" cellpadding="0" cellspacing="0" border="0" ` +
		`style="border-collapse:separate;margin:0 0 8px 0;">` +
		`<tr><td style="background:` + colBrandAction + `;border-radius:8px;padding:14px 24px;">` +
		`<a href="` + esc(url) + `" style="display:block;padding:0;font:600 16px/20px ` + fontStack +
		`;color:` + colSurface + `;text-decoration:none;">` + esc(label) + `</a>` +
		`</td></tr></table></td></tr>`
}

// shell is mail_notify._shell. footerHTML holds the footer lines already
// rendered (the first one bare, the others in the padded div).
func shell(publicBaseURL, lang, title, preheader string, blocks []string, footerHTML string) string {
	preheaderHTML := ""
	if preheader != "" {
		preheaderHTML = `<div style="display:none;font-size:1px;line-height:1px;max-height:0;` +
			`max-width:0;opacity:0;overflow:hidden;mso-hide:all;">` + esc(preheader) + preheaderSpacer + `</div>`
	}
	logoURL := publicBaseURL + logoPath
	return `<!doctype html>
<html lang="` + esc(lang) + `">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<title>` + esc(title) + `</title>
</head>
<body style="margin:0;padding:0;background:` + colCanvas + `;">
` + preheaderHTML + `
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:` + colCanvas + `;border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:` + colSurface + `;border:1px solid ` + colLine + `;border-radius:14px;border-collapse:separate;">
<tr><td style="padding:28px 24px 0 24px;">
<img src="` + esc(logoURL) + `" width="` + logoWidth + `" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:` + logoWidth + `px;max-width:100%;height:auto;">
</td></tr>
` + strings.Join(blocks, "") + `
<tr><td style="padding:28px 24px 28px 24px;">
<div style="border-top:1px solid ` + colLine + `;padding:16px 0 0 0;font:400 13px/1.6 ` + fontStack + `;color:` + colInkMuted + `;">
` + footerHTML + `
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
`
}

// BuildLifecycle is mail_notify.build_lifecycle: the tip for kind, with the
// unsubscribe link in the footer. Python's lang falls back to English; here
// any other language is ErrLanguage.
func (c Config) BuildLifecycle(kind, unsubscribeURL, lang string) (Content, error) {
	cp, ok := copies[kind]
	if !ok {
		return Content{}, fmt.Errorf("%w %s", ErrKind, kind)
	}
	if lang == "" {
		lang = hostMailLanguage
	}
	if len(lang) > 2 {
		lang = lang[:2]
	}
	if strings.ToLower(lang) != "en" {
		return Content{}, ErrLanguage
	}
	lang = "en"
	actionURL := c.appBaseURL() + actions[kind]
	signoff := strings.NewReplacer("%(support)s", c.OperatorEmail).Replace(strSignoff)
	footer := footerSentence{
		text: strings.NewReplacer(
			"%(name)s", c.OperatorName,
			"%(ico)s", c.OperatorICO,
			"%(address)s", c.OperatorAddress,
			"%(unsubscribe)s", "%(unsubscribe)s",
			"%(privacy)s", "%(privacy)s",
		).Replace(strFooter),
		links: map[string]link{
			"unsubscribe": {strUnsubscribeLabel, unsubscribeURL},
			"privacy":     {"", c.PublicBaseURL + "/privacy?lang=" + lang},
		},
	}
	text := strings.Join([]string{
		cp.intro,
		"",
		cp.next,
		"",
		cp.action + ": " + actionURL,
		"",
		signoff,
		"",
		"--",
		"UbyHost",
		footer.plain(),
	}, "\n")
	blocks := []string{
		blockHeading(cp.heading),
		blockParagraph(cp.intro, false),
		blockParagraph(cp.next, false),
		blockButton(actionURL, cp.action),
		blockParagraph(signoff, true),
	}
	footerHTML := `<div>` + esc("UbyHost") + `</div>` +
		`<div style="padding:4px 0 0 0;">` + footer.html() + `</div>`
	return Content{
		Subject: cp.subject,
		Text:    text,
		HTML:    shell(c.PublicBaseURL, lang, cp.heading, cp.intro, blocks, footerHTML),
	}, nil
}
