package mail

// The billing_paid mail (brief 1558): the payment confirmation to a host, in
// Czech (mail_notify.build_billing_paid, lines 3111-3123). Strings are host_i18n
// cs mail.billing_paid.*; the action label is mail.billing_overdue.action and the
// shell is the one of billing_trial.go.

import "strings"

const (
	strBillingPaidSubject = "Faktura %(number)s je zaplacena"
	strBillingPaidBody    = "Platbu %(amount)s Kč za fakturu %(number)s jsme přijali %(date)s. Faktura je označená jako zaplacená. Děkujeme."
)

// BuildBillingPaid is build_billing_paid. paid is the formatted payment date
// (DD.MM.YYYY); amountCZK is whole crowns.
func BuildBillingPaid(appBaseURL, publicBaseURL, supportEmail, number string, amountCZK int64, paid string) Content {
	replacer := strings.NewReplacer("%(number)s", number, "%(amount)s", thousands(amountCZK), "%(date)s", paid)
	return billingServiceContent(appBaseURL, publicBaseURL, supportEmail,
		replacer.Replace(strBillingPaidSubject), replacer.Replace(strBillingPaidBody), strBillingOverdueAction)
}
