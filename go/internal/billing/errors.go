package billing

import "errors"

// Error is a billing refusal with a stable code. The codes are the messages of
// the Python ValueError the same rule raises (App/app/billing.py,
// billing_order.py), so the golden file compares them as plain strings.
// Callers test with errors.Is(err, billing.ErrAlreadyOrdered) or compare
// billing.Code(err). A wrapped error keeps its code: the text after the code
// is detail for a log, never for a page.
type Error struct{ code string }

// Error returns the code.
func (e *Error) Error() string { return e.code }

// Code returns the code of the first billing Error in err's chain, or "".
func Code(err error) string {
	var e *Error
	if errors.As(err, &e) {
		return e.code
	}
	return ""
}

// The sentinels. Python raise -> Go error:
//
//	unknown status: <x>                  ErrUnknownStatus
//	one change at a time, from ...       ErrOneChange
//	no ordered plan to change            ErrNoOrderedPlan
//	whitelabel_unavailable               ErrWhitelabelUnavailable
//	discount_out_of_range                ErrDiscountOutOfRange
//	reason_missing                       ErrReasonMissing
//	no_plan                              ErrNoPlan
//	og                                   ErrNoAccount
//	already_ordered                      ErrAlreadyOrdered
//	bad_days                             ErrBadDays
//	unknown plan or interval: <x> <y>    ErrUnknownPlan (from quote)
//
// ErrBadValue has no Python twin: Python takes any object as the value of a
// change, Go takes int, int64, bool and string and refuses the rest.
var (
	ErrUnknownStatus         = &Error{"unknown status"}
	ErrOneChange             = &Error{"one change at a time, from CHANGE_COLUMNS"}
	ErrNoOrderedPlan         = &Error{"no ordered plan to change"}
	ErrWhitelabelUnavailable = &Error{"whitelabel_unavailable"}
	ErrDiscountOutOfRange    = &Error{"discount_out_of_range"}
	ErrReasonMissing         = &Error{"reason_missing"}
	ErrNoPlan                = &Error{"no_plan"}
	ErrNoAccount             = &Error{"og"}
	ErrAlreadyOrdered        = &Error{"already_ordered"}
	ErrBadDays               = &Error{"bad_days"}
	ErrUnknownPlan           = &Error{"unknown plan or interval"}
	ErrBadValue              = &Error{"bad value"}
)
