// Package headcount holds the one rule for how many guests a stay expects.
package headcount

// Expected mirrors reporting.expected_guest_count (App/app/reporting.py): the
// base is a non-zero host override, else the declared count (nil stays nil). A
// non-zero lead reduction wins when there is no base or it is below the base;
// it never raises the number. The shared cases are in testdata/cases.json,
// which the Python tests read too.
func Expected(override, declared, reduced *int64) *int64 {
	base := declared
	if override != nil && *override != 0 {
		base = override
	}
	if reduced != nil && *reduced != 0 && (base == nil || *reduced < *base) {
		return reduced
	}
	return base
}
