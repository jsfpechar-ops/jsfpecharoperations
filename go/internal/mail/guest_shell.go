package mail

import (
	"strconv"
	"strings"
)

// guestShell is mail_notify._shell for guest messages: the html lang attribute
// is the raw language tag (escaped), not the normalised catalogue code.
func guestShell(publicBaseURL, lang, pageTitle, preheader string, blocks []string, footerLines []any) string {
	var footerHTML strings.Builder
	for i, line := range footerLines {
		if i > 0 {
			footerHTML.WriteString(`<div style="padding:4px 0 0 0;">` + guestFooterLineHTML(line) + `</div>`)
		} else {
			footerHTML.WriteString(`<div>` + guestFooterLineHTML(line) + `</div>`)
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
<html lang="` + esc(lang) + `">
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

type invoicePanelRow struct {
	label, value string
}

// blockInvoicePanel is _block_panel for the invoice money slot.
func blockInvoicePanel(title string, rows []invoicePanelRow, actionURL, actionLabel string) string {
	rendered := make([]string, 0, len(rows))
	for _, row := range rows {
		rendered = append(rendered, "<tr>"+
			`<td style="padding:0 12px 8px 0;font:400 13px/1.5 `+fontStack+`;color:`+colInkMuted+
			`;vertical-align:top;white-space:nowrap;">`+esc(row.label)+`</td>`+
			`<td style="padding:0 0 8px 0;text-align:right;font:600 15px/1.5 `+fontStack+`;color:`+colInk+
			`;vertical-align:top;">`+esc(row.value)+`</td>`+
			"</tr>")
	}
	parts := []string{
		`<div style="font:600 15px/1.4 ` + fontStack + `;color:` + colInk + `;padding:0 0 10px 0;">` + esc(title) + `</div>`,
		`<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">` +
			strings.Join(rendered, "") + `</table>`,
	}
	if actionURL != "" {
		parts = append(parts, `<div style="padding:14px 0 0 0;">`+button(actionURL, actionLabel)+`</div>`)
	}
	return `<tr><td style="padding:24px 24px 0 24px;">` +
		`<div style="background:` + colCanvas + `;border:1px solid ` + colLine + `;` +
		`border-radius:12px;padding:18px 20px;">` + strings.Join(parts, "") + `</div></td></tr>`
}
