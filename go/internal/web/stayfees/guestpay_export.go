package stayfees

// Brief 1701b: the two stay-fee helpers the Go property page needs, exported so
// it calls them instead of copying them (the way palette/slug_export.go
// exports EnsureGuestSlug). Both are thin wrappers of the code above.

import (
	"strings"
	"time"
)

// PragueToday is stay_fee_routes.rate_from_default: today in Prague, ISO.
func PragueToday(at time.Time) string {
	return pragueDay(at).Format("2006-01-02")
}

// GuestPayOperator is the part of guest_pay_operator_context the property page
// draws: whether the switch is on, whether an operator account is known, its
// display form, the sample QR (a data: URI) and the account box value.
type GuestPayOperator struct {
	On             bool
	HasAccount     bool
	AccountDisplay string
	PreviewQR      string
	FieldValue     string
}

// GuestPayOperatorFor is guest_pay_operator_context for a GET (no draft, no
// typed sample rate): bankAccount and iban are the operator's columns ("" when
// the property has no operator), aptRate the property's own stay fee rate.
func GuestPayOperatorFor(getenv func(string) string, bankAccount, iban string, aptRate int64) (GuestPayOperator, error) {
	if !guestPayOn(getenv) {
		return GuestPayOperator{}, nil
	}
	entity := &guestpayEntity{BankAccount: bankAccount, IBAN: iban}
	shown := bankAccount
	if shown == "" {
		shown = guestpayEntityAccount(entity)
	}
	out := GuestPayOperator{On: true, FieldValue: strings.TrimSpace(shown)}
	has, display, qr, err := guestpayContext(entity, "", nil, aptRate)
	if err != nil {
		return GuestPayOperator{}, err
	}
	out.HasAccount, out.AccountDisplay, out.PreviewQR = has, display, qr
	return out, nil
}
