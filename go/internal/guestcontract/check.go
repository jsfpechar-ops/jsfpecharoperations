package guestcontract

import (
	"strconv"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// UnderSignAge is reporting.UNDER_SIGN_AGE: a guest under 15 on arrival does
// not sign.
const UnderSignAge = 15

const (
	partySizeMessage = "Please enter how many people are staying (1–60)."
	legalAckMessage  = "Please confirm that you have read the legal information."
)

// CheckNewGuest runs the checks of the guest save route (App/app/routes/guest.py,
// guest_form_save) that need no database, for a NEW guest (no stored row), in
// the route's order: validate_guest, validate_stay_dates,
// validate_stay_date_text, party size, signature, legal acknowledgement.
// Messages are the English ones; the form localises by field, as
// _localize_issues does.
//
// Not here, because they need the database or a stored row: editing an
// existing guest (its stored stay dates and kept signature), "signed_by" (the
// list of adults on the stay), the passport photo (stored photo and policy
// decision), and the PIN.
//
// Known difference: Python int() also reads "1_0" and non-ASCII digits as a
// party size; strconv.Atoi does not. Such a post is refused here and would
// be accepted by Python.
func CheckNewGuest(g GuestForm, cfg FormConfig, st Stay, today time.Time) []validation.Issue {
	raw := validation.GuestFormRaw(g.Fields(), cfg.DefaultPurpose)
	values := validation.NormaliseGuest(raw, today)
	from := isoDate(st.DateFrom)
	to := isoDate(st.DateTo)
	signature := validation.Strip(g.Signature)
	child := validation.CertainlyUnderAge(values.BirthDate, from, UnderSignAge)
	if child {
		signature = ""
	}
	issues := validation.ValidateGuestForm(values, from, to, today, raw)
	issues = append(issues, validation.ValidateStayDates(from, to, from, to)...)
	issues = append(issues, validation.ValidateStayDateText(st.DateFrom, st.DateTo)...)
	if st.ExpectedGuests == nil {
		n, err := strconv.Atoi(validation.Strip(g.PartySize))
		if err != nil {
			n = 0
		}
		if n < 1 || n > 60 {
			issues = append(issues, validation.Issue{Field: "party_size", Message: partySizeMessage, Severity: "error"})
		}
	}
	if sig := validation.GuestFormSignatureIssue(signature, child); sig != nil {
		issues = append(issues, *sig)
	}
	if !g.LegalAck {
		issues = append(issues, validation.Issue{Field: "legal_ack", Message: legalAckMessage, Severity: "error"})
	}
	return issues
}

func isoDate(s string) *time.Time {
	t, ok := validation.ParseISODate(s)
	if !ok {
		return nil
	}
	return &t
}
