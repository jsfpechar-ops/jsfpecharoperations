package auth

import (
	"testing"
	"time"
)

const authGoldenTimeRFC3339 = "2026-06-15T12:00:00Z"

// authGoldenFixed is the wall clock for *GoldenDatabase tests so session iat/rf/ast
// match Python-generated fixtures (no live time.Now in Routes handlers).
func authGoldenFixed(t *testing.T) time.Time {
	t.Helper()
	fixed, err := time.Parse(time.RFC3339, authGoldenTimeRFC3339)
	if err != nil {
		t.Fatal(err)
	}
	return fixed
}

func authGoldenClock(fixed time.Time) func() time.Time {
	return func() time.Time { return fixed }
}
