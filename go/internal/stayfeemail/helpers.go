package stayfeemail

// Copies of the small helpers of go/internal/mail (submission_problem.go) and
// the constants of App/app/mail_notify.py they use: esc (html.escape), the
// language cut of host_i18n.normalise_language, blockParagraph, button and
// blockButton (_block_paragraph, _button, _block_button), the colours, font
// stack and the preheader spacer. Copied, not imported, because they are
// unexported there and that package is owned by another thread.

import "strings"

// Content is the subject, text part and HTML part of one message (same fields
// as mail.Content).
type Content struct {
	Subject string
	Text    string
	HTML    string
}

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
	logoWidth       = 180
)

// preheaderSpacer is PREHEADER_SPACER.
var preheaderSpacer = strings.Repeat("\u2007\ufeff\u034f", 40)

var escaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;", "'", "&#x27;")

func esc(s string) string {
	return escaper.Replace(s)
}

// normaliseLanguage cuts to two lower-case characters; empty is "en".
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

func blockParagraph(text string, muted bool) string {
	colour, size := colInkSecondary, "16"
	if muted {
		colour, size = colInkMuted, "14"
	}
	return `<tr><td style="padding:12px 24px 0 24px;"><p style="margin:0;font:400 ` + size +
		`px/1.6 ` + fontStack + `;color:` + colour + `;">` + esc(text) + `</p></td></tr>`
}

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
