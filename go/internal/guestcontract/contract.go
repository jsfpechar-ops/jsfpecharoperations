// Package guestcontract is the contract between the app and the guest program
// (plan docs/plans/guest-form-isolation.md section 3): the contract version,
// the form config JSON of guest_form_snapshot, the payload of guest_inbox and
// its encoding, and the guest checks that need no database. Both programs
// compile this one package, so they cannot disagree on a field or a check.
// Brief 1835; the tables are migration 00020 (brief 1834).
package guestcontract

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"regexp"
)

// V1 is contract version 1. Current is the version this build writes.
const (
	V1      = 1
	Current = V1
)

// Supported reports whether a row of contract version v can be read: the
// current version N and the one before it, N-1 (plan section 3 rule 5).
func Supported(v int) bool {
	return v >= V1 && (v == Current || v == Current-1)
}

var idempotencyKeyRE = regexp.MustCompile(`^[0-9a-f]{32}$`)

// TokenHash is the SHA-256 hex of a guest link key, as claim.token_hash in
// App/app/claim.py. It is the token_hash column of both contract tables.
func TokenHash(linkKey string) string {
	sum := sha256.Sum256([]byte(linkKey))
	return hex.EncodeToString(sum[:])
}

// NewIdempotencyKey returns 32 lower-case hex characters (128 random bits).
// The form page makes one when it is drawn, so a repeated post is one row.
func NewIdempotencyKey() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(b[:]), nil
}

// ValidIdempotencyKey matches the CHECK on guest_inbox.idempotency_key.
func ValidIdempotencyKey(key string) bool {
	return idempotencyKeyRE.MatchString(key)
}
