package validation

import "time"

// NormaliseName is validation.normalise_name.
func NormaliseName(v string) string { return normaliseName(v) }

// NormaliseDocument is validation.normalise_document.
func NormaliseDocument(v string) string { return normaliseDocument(v) }

// NormaliseBirthDate is validation.normalise_birth_date with today injected.
func NormaliseBirthDate(v string, today time.Time) string { return normaliseBirthDate(v, today) }

// KnownCountry reports whether code is in the ISO 3166-1 country list.
func KnownCountry(code string) bool { return knownCountry(code) }
