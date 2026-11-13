package mail

// The billing_overdue mail (brief 1222): the reminders for an unpaid invoice, in
// Czech (mail_notify.build_billing_overdue). Strings are host_i18n cs
// mail.billing_overdue.*; the shell comes from billing_trial.go.

import "strings"

const (
	strBillingOverdueSubjectReminder = "Faktura %(number)s je po splatnosti"
	strBillingOverdueSubjectSecond   = "Připomínka: faktura %(number)s"
	strBillingOverdueSubjectPaused   = "Účet UbyHost je jen pro čtení"
	strBillingOverdueAction          = "Otevřít předplatné"
	strBillingOverdueBodyReminder    = "Faktura %(number)s na %(amount)s Kč byla splatná %(due)s a platbu jsme zatím nepřijali. Pokud jste už zaplatili, tento e-mail prosím ignorujte. Fakturu i QR Platbu najdete v přehledu předplatného."
	strBillingOverdueBodyPaused      = "Platbu faktury %(number)s na %(amount)s Kč jsme do %(date)s nepřijali, proto je účet jen pro čtení. Hosty, kteří už vyplnili údaje, cizinecké policii hlásíme dál. Po zaplacení se účet znovu otevře."
)

// BuildBillingOverdue is build_billing_overdue. stage is reminder, second or
// paused; any other stage (the monthly repeats) reads as second. due and today are
// formatted (DD.MM.YYYY).
func BuildBillingOverdue(appBaseURL, publicBaseURL, supportEmail, stage, number string, amountCZK int64, due, today string) Content {
	subjectText := strBillingOverdueSubjectSecond
	switch stage {
	case "reminder":
		subjectText = strBillingOverdueSubjectReminder
	case "paused":
		subjectText = strBillingOverdueSubjectPaused
	}
	replacer := strings.NewReplacer(
		"%(number)s", number, "%(amount)s", thousands(amountCZK), "%(due)s", due, "%(date)s", today)
	bodyText := strBillingOverdueBodyReminder
	if stage == "paused" {
		bodyText = strBillingOverdueBodyPaused
	}
	return billingServiceContent(appBaseURL, publicBaseURL, supportEmail,
		replacer.Replace(subjectText), replacer.Replace(bodyText), strBillingOverdueAction)
}
