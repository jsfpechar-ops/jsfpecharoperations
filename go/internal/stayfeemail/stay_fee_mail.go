package stayfeemail

// Port of App/app/mail_notify.py build_stay_fee_report and
// build_stay_fee_blocked (the two host mails of the daily stay_fee_mail job)
// and App/app/stay_fee_auto.py period_label. Unlike the other mails in this
// package they follow the host's language (cs, en, vi; any other code falls
// back to en as host_i18n.normalise_language does), so the strings come from
// the generated catalog i18n.json (keys in i18n_keys.txt, written by
// App/scripts/go_host_i18n.py) read through hostweb.Catalog.T, which is
// host_i18n.translate with its lookup() guard. The shell is rendered here
// because it needs the language in <html lang> and a footer link.
// Golden: App/scripts/stay_fee_mail_golden.py writes testdata/stay_fee_cases.json.

import (
	_ "embed"
	"strconv"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

//go:embed i18n.json
var stayFeeJSON []byte

var stayFeeStrings = hostweb.Load(stayFeeJSON)

const (
	stayFeeQRContentID  = "stayfeeqr" // mail.QR_CONTENT_ID
	stayFeeTurnOffPath  = "/settings/account#settings-stay-fee-emails"
	stayFeeQRImgPadding = `<tr><td style="padding:8px 24px 0 24px;">`
)

// StayFeeReport is the input of BuildStayFeeReport, as queue_stay_fee_report
// computes it. Amount is stay_fee.format_czk(TotalCZK) ("1 234 Kč"), Period is
// PeriodLabel, ReportURL the absolute report link.
type StayFeeReport struct {
	PropertyName string
	Period       string
	Amount       string
	TotalCZK     int
	Authority    string
	Databox      string
	Account      string
	VS           string
	HasQR        bool
	ReportURL    string
}

// stayFeeLang is host_i18n.normalise_language (cs, en, vi).
func stayFeeLang(lang string) string {
	switch code := normaliseLanguage(lang); code {
	case "cs", "vi":
		return code
	}
	return "en"
}

// stayFeeT is mail_notify._text: pairs are name, value, name, value.
func stayFeeT(lang, key string, pairs ...string) string {
	if len(pairs) == 0 {
		return stayFeeStrings.T(lang, key, nil)
	}
	params := make(map[string]any, len(pairs)/2)
	for i := 0; i+1 < len(pairs); i += 2 {
		params[pairs[i]] = pairs[i+1]
	}
	return stayFeeStrings.T(lang, key, params)
}

// PeriodLabel is stay_fee_auto.period_label: "Q2 2026" for a quarterly
// cadence, else "<month name> <year>", in the host's language.
func PeriodLabel(lang, cadence string, year, month int) string {
	lang = stayFeeLang(lang)
	if cadence == "quarterly" {
		return stayFeeStrings.T(lang, "stay_fees.quarter", map[string]any{
			"n": (month-1)/3 + 1, "year": year,
		})
	}
	return stayFeeStrings.T(lang, "month."+strconv.Itoa(month), nil) + " " + strconv.Itoa(year)
}

// stayFeeShell is _shell with the language and the footer given as HTML lines.
func stayFeeShell(publicBaseURL, lang, title, preheader string, blocks, footerHTML []string) string {
	var footer strings.Builder
	for i, line := range footerHTML {
		if i > 0 {
			footer.WriteString(`<div style="padding:4px 0 0 0;">` + line + `</div>`)
		} else {
			footer.WriteString(`<div>` + line + `</div>`)
		}
	}
	preheaderHTML := ""
	if preheader != "" {
		preheaderHTML = `<div style="display:none;font-size:1px;line-height:1px;max-height:0;` +
			`max-width:0;opacity:0;overflow:hidden;mso-hide:all;">` + esc(preheader) + preheaderSpacer + `</div>`
	}
	logoURL := publicBaseURL + logoPath
	width := strconv.Itoa(logoWidth)
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
<img src="` + esc(logoURL) + `" width="` + width + `" alt="UbyHost" style="display:block;border:0;outline:none;text-decoration:none;width:` + width + `px;max-width:100%;height:auto;">
</td></tr>
` + strings.Join(blocks, "") + `
<tr><td style="padding:28px 24px 28px 24px;">
<div style="border-top:1px solid ` + colLine + `;padding:16px 0 0 0;font:400 13px/1.6 ` + fontStack + `;color:` + colInkMuted + `;">
` + footer.String() + `
</div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>
`
}

// stayFeeFooter is footer_lines=["UbyHost", footer, [_FooterLink(turn_off, url)]].
func stayFeeFooter(footer, turnOff, turnOffURL string) []string {
	return []string{
		esc("UbyHost"),
		esc(footer),
		`<a href="` + esc(turnOffURL) + `" style="color:` + colInkSecondary + `;text-decoration:underline;">` + esc(turnOff) + `</a>`,
	}
}

// BuildStayFeeReport is build_stay_fee_report: the finished report mail (PDF
// attached and QR inline by the sender, not here). appBaseURL carries the
// "turn off" link and publicBaseURL the logo.
func BuildStayFeeReport(appBaseURL, publicBaseURL, lang string, r StayFeeReport) Content {
	lang = stayFeeLang(lang)
	zero := r.TotalCZK == 0
	var subject string
	if zero {
		subject = stayFeeT(lang, "mail.stay_fee.subject_zero", "period", r.Period, "property", r.PropertyName)
	} else {
		subject = stayFeeT(lang, "mail.stay_fee.subject", "period", r.Period, "amount", r.Amount, "property", r.PropertyName)
	}
	intro := stayFeeT(lang, "mail.stay_fee.intro", "period", r.Period, "property", r.PropertyName)
	var stepSend string
	if r.Databox != "" {
		stepSend = stayFeeT(lang, "mail.stay_fee.step_send", "authority", r.Authority, "databox", r.Databox)
	} else {
		stepSend = stayFeeT(lang, "mail.stay_fee.step_send_plain", "authority", r.Authority)
	}
	var stepPay string
	switch {
	case zero:
		stepPay = stayFeeT(lang, "mail.stay_fee.zero")
	case r.HasQR:
		stepPay = stayFeeT(lang, "mail.stay_fee.step_pay", "amount", r.Amount, "account", r.Account, "vs", r.VS)
	default:
		stepPay = stayFeeT(lang, "mail.stay_fee.step_pay_plain", "amount", r.Amount, "vs", r.VS)
	}
	qrAlt := stayFeeT(lang, "mail.stay_fee.qr_alt")
	fix := stayFeeT(lang, "mail.stay_fee.fix")
	openLabel := stayFeeT(lang, "mail.stay_fee.open")
	footer := stayFeeT(lang, "mail.stay_fee.footer")
	turnOff := stayFeeT(lang, "mail.stay_fee.turn_off")
	turnOffURL := appBaseURL + stayFeeTurnOffPath
	showQR := r.HasQR && !zero

	lines := []string{intro, "", stepSend, stepPay}
	if showQR {
		lines = append(lines, qrAlt)
	}
	lines = append(lines, "", fix, r.ReportURL, "", "--", "UbyHost", footer, turnOff+": "+turnOffURL)

	blocks := []string{blockParagraph(intro, false), blockParagraph(stepSend, false), blockParagraph(stepPay, false)}
	if showQR {
		blocks = append(blocks, stayFeeQRImgPadding+
			`<img src="cid:`+stayFeeQRContentID+`" width="200" height="200" alt="`+esc(qrAlt)+`" `+
			`style="display:block;border:0;width:200px;height:200px;"></td></tr>`)
	}
	blocks = append(blocks, blockParagraph(fix, false), blockButton(r.ReportURL, openLabel))
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    stayFeeShell(publicBaseURL, lang, r.PropertyName, intro, blocks, stayFeeFooter(footer, turnOff, turnOffURL)),
	}
}

// BuildStayFeeBlocked is build_stay_fee_blocked: the "what to fix" mail. issues
// are catalog keys (stay_fee.report_issues plus stay_fees.issue.unsigned); a
// key the catalog lacks prints as the key itself, as in Python.
func BuildStayFeeBlocked(appBaseURL, publicBaseURL, lang, propertyName, period string, issues []string, reportURL string) Content {
	lang = stayFeeLang(lang)
	subject := stayFeeT(lang, "mail.stay_fee_blocked.subject", "period", period, "property", propertyName)
	intro := stayFeeT(lang, "mail.stay_fee_blocked.intro", "period", period, "property", propertyName)
	items := make([]string, 0, len(issues))
	for _, key := range issues {
		items = append(items, stayFeeT(lang, key))
	}
	after := stayFeeT(lang, "mail.stay_fee_blocked.after")
	openLabel := stayFeeT(lang, "mail.stay_fee.open")
	footer := stayFeeT(lang, "mail.stay_fee.footer")
	turnOff := stayFeeT(lang, "mail.stay_fee.turn_off")
	turnOffURL := appBaseURL + stayFeeTurnOffPath

	lines := []string{intro, ""}
	for _, item := range items {
		lines = append(lines, "- "+item)
	}
	lines = append(lines, "", after, reportURL, "", "--", "UbyHost", footer, turnOff+": "+turnOffURL)

	blocks := []string{blockParagraph(intro, false)}
	for _, item := range items {
		blocks = append(blocks, blockParagraph(item, false))
	}
	blocks = append(blocks, blockParagraph(after, false), blockButton(reportURL, openLabel))
	return Content{
		Subject: subject,
		Text:    strings.Join(lines, "\n"),
		HTML:    stayFeeShell(publicBaseURL, lang, propertyName, intro, blocks, stayFeeFooter(footer, turnOff, turnOffURL)),
	}
}
