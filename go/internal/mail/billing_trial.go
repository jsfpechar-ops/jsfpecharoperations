package mail

// The billing_trial mail (brief 1222): the trial-ending reminder, in Czech
// (mail_notify.build_billing_trial). Strings are host_i18n cs mail.billing_trial.*;
// the footer constant and helpers come from billing_invoice.go (brief 1221).

import "strings"

const (
	strBillingTrialSubject0 = "Zkušební doba UbyHost dnes končí"
	strBillingTrialSubject3 = "Zkušební doba UbyHost končí za 3 dny"
	strBillingTrialSubject7 = "Zkušební doba UbyHost končí za 7 dní"
	strBillingTrialAction   = "Vybrat plán"
	strBillingTrialBody     = "Zkušební doba UbyHost končí %(date)s. Když si do té doby vyberete plán, vše poběží dál bez přerušení. Bez plánu půjde účet jen prohlížet; hosty, kteří už vyplnili údaje, ale cizinecké policii ohlásíme dál."
)

// BuildBillingTrial is build_billing_trial. daysLeft is 7, 3 or 0; ends is the
// formatted end date (DD.MM.YYYY). Any other daysLeft uses the "today" subject.
func BuildBillingTrial(appBaseURL, publicBaseURL, supportEmail string, daysLeft int, ends string) Content {
	subject := strBillingTrialSubject0
	switch daysLeft {
	case 3:
		subject = strBillingTrialSubject3
	case 7:
		subject = strBillingTrialSubject7
	}
	body := strings.NewReplacer("%(date)s", ends).Replace(strBillingTrialBody)
	return billingServiceContent(appBaseURL, publicBaseURL, supportEmail, subject, body, strBillingTrialAction)
}

// billingServiceContent is the shape build_billing_trial and build_billing_overdue
// share: heading, paragraph, one button to /predplatne, the support footer.
func billingServiceContent(appBaseURL, publicBaseURL, supportEmail, subject, body, action string) Content {
	footer := []string{"UbyHost", strings.NewReplacer("%(support)s", supportEmail).Replace(strBillingFooterSupport)}
	link := appBaseURL + "/predplatne"
	text := strings.Join(append([]string{body, "", action + ": " + link, "", "--"}, footer...), "\n")
	html := shell(publicBaseURL, subject, body, []string{
		blockHeading(subject),
		blockParagraph(body, false),
		blockButton(link, action),
	}, footer)
	html = strings.Replace(html, `<html lang="en">`, `<html lang="cs">`, 1)
	return Content{Subject: subject, Text: text, HTML: html}
}
