package mail

// The billing_invoice mail (brief 1221): UbyHost's invoice to a host, in Czech
// (mail_notify.BILLING_MAIL_LANGUAGE). Strings are host_i18n cs
// mail.billing_invoice.*; the shell and blocks are the ones in
// submission_problem.go, with the html lang switched to cs.

import (
	"strconv"
	"strings"
)

const (
	strBillingInvoiceSubject = "Faktura %(number)s od UbyHost"
	strBillingInvoiceAction  = "Otevřít předplatné"
	strBillingInvoiceBody    = "Posíláme fakturu %(number)s na %(amount)s Kč za období %(period)s se splatností %(due)s, variabilní symbol %(vs)s. Faktura je v příloze, QR Platba je přímo v ní."
	strBillingFooterSupport  = "Dotazy: %(support)s"
)

// thousands is f"{n:,}".replace(",", " ").
func thousands(n int64) string {
	s := strconv.FormatInt(n, 10)
	sign := ""
	if strings.HasPrefix(s, "-") {
		sign, s = "-", s[1:]
	}
	var out []byte
	for i := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			out = append(out, ' ')
		}
		out = append(out, s[i])
	}
	return sign + string(out)
}

// BuildBillingInvoice is build_billing_invoice. due is the formatted due date
// (DD.MM.YYYY) and period the formatted range; appBaseURL and publicBaseURL as
// elsewhere in this package; supportEmail is the operator address.
func BuildBillingInvoice(appBaseURL, publicBaseURL, supportEmail, number, vs string, amountCZK int64, due, period string) Content {
	subject := strings.NewReplacer("%(number)s", number).Replace(strBillingInvoiceSubject)
	body := strings.NewReplacer(
		"%(number)s", number, "%(amount)s", thousands(amountCZK),
		"%(period)s", period, "%(due)s", due, "%(vs)s", vs,
	).Replace(strBillingInvoiceBody)
	footer := []string{"UbyHost", strings.NewReplacer("%(support)s", supportEmail).Replace(strBillingFooterSupport)}
	link := appBaseURL + "/predplatne"
	text := strings.Join(append([]string{body, "", strBillingInvoiceAction + ": " + link, "", "--"}, footer...), "\n")
	html := shell(publicBaseURL, subject, body, []string{
		blockHeading(subject),
		blockParagraph(body, false),
		blockButton(link, strBillingInvoiceAction),
	}, footer)
	html = strings.Replace(html, `<html lang="en">`, `<html lang="cs">`, 1)
	return Content{Subject: subject, Text: text, HTML: html}
}
