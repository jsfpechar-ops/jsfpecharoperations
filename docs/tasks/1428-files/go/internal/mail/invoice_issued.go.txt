package mail

// Port of mail_notify.build_invoice_issued (brief 1428): the host-sent invoice
// e-mail with one money panel and a download button. Golden:
// App/scripts/go_invoice_issued_golden.py -> testdata/invoice_issued_golden.json.

import "strings"

// BuildInvoiceIssued composes subject, text and HTML for kind invoice_issued.
// issuer is the host legal entity name; stayProperty, when non-empty, is added
// to the subject and panel. downloadURL often carries ClaimSecretMarker.
func BuildInvoiceIssued(publicBaseURL, lang, issuer, number, total, downloadURL string, host HostDetails, stayProperty string) Content {
	stayProperty = strings.TrimSpace(stayProperty)
	var subject string
	if stayProperty != "" {
		subject = GuestText(lang, "invoice_mail_issued_subject_stay", Args{
			"number": number, "stay_property": stayProperty,
		})
	} else {
		subject = GuestText(lang, "invoice_mail_issued_subject", Args{"number": number})
	}
	intro := GuestText(lang, "invoice_mail_issued_intro", Args{"property": issuer})
	footerLines := guestFooterLines(lang, issuer, host)
	btn := GuestText(lang, "invoice_mail_issued_button", nil)
	title := GuestText(lang, "mail_invoice_title", nil)

	var rows []invoicePanelRow
	rows = append(rows, invoicePanelRow{
		label: GuestText(lang, "mail_invoice_number", nil),
		value: number,
	})
	if stayProperty != "" {
		rows = append(rows, invoicePanelRow{
			label: GuestText(lang, "mail_invoice_property", nil),
			value: stayProperty,
		})
	}
	rows = append(rows, invoicePanelRow{
		label: GuestText(lang, "mail_invoice_total", nil),
		value: total,
	})

	blocks := []string{
		blockHeading(title),
		blockParagraph(intro, false),
		blockInvoicePanel(title, rows, downloadURL, btn),
	}
	textLines := []string{intro, ""}
	for _, r := range rows {
		textLines = append(textLines, r.label+": "+r.value)
	}
	textLines = append(textLines, btn+": "+downloadURL)
	textLines = append(textLines, "")
	textLines = append(textLines, "--")
	textLines = append(textLines, guestFooterText(footerLines)...)

	return Content{
		Subject: subject,
		Text:    strings.Join(textLines, "\n"),
		HTML:    guestShell(publicBaseURL, lang, issuer, subject, blocks, footerLines),
	}
}
