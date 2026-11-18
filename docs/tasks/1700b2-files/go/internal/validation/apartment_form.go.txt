package validation

// The property form normalisers of validation.py that the Go property create
// (brief 1700b2) needs: exported names for the rules this package already
// applies, plus normalise_reachback_days. Nothing here changes what
// ValidateApartment checks.

// ReachbackDaysDefault and ReachbackDaysMax are REACHBACK_DAYS_DEFAULT and
// REACHBACK_DAYS_MAX.
const (
	ReachbackDaysDefault = 365
	ReachbackDaysMax     = 3650
)

// NormaliseZip is validation.normalise_zip: the digits of the value (the same
// rule ValidateApartment reads the postcode with).
func NormaliseZip(value string) string { return digitsOnly(value) }

// IsPurposeCode reports whether code is in validation.PURPOSE_CODES.
func IsPurposeCode(code string) bool { return purposeCodes[code] }

// Upper is str.upper() as this package applies it.
func Upper(s string) string { return pyUpper(s) }

// NormaliseReachbackDays is validation.normalise_reachback_days: nil (Python
// None) or a value below one day is the default, a larger one is capped.
func NormaliseReachbackDays(days *int64) int64 {
	if days == nil || *days <= 0 {
		return ReachbackDaysDefault
	}
	return min(*days, ReachbackDaysMax)
}
