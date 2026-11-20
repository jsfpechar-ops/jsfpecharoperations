package guest

import (
	"crypto/hmac"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func TestPinMatchesUsesFingerprint(t *testing.T) {
	secret := "test-secret-key-for-pin"
	token := "tok"
	if !pinMatches(secret, token, "123456", "123456") {
		t.Fatal("same pin")
	}
	if pinMatches(secret, token, "000000", "123456") {
		t.Fatal("wrong pin")
	}
	want := secure.PinFingerprint(secret, token, "123456")
	got := secure.PinFingerprint(secret, token, "123456")
	if !hmac.Equal([]byte(want), []byte(got)) {
		t.Fatal("fingerprint drift")
	}
}

func TestSafeReturnToRejectsOutsidePrefix(t *testing.T) {
	got := safeReturnTo("/other/path", "tok", "en")
	want := GuestLink("tok", 0, "") + LangQuery("en", "")
	if got != want {
		t.Fatalf("got %q want %q", got, want)
	}
	if got := safeReturnTo("/l/tok/7", "tok", "cs"); got != "/l/tok/7" {
		t.Fatalf("stay path %q", got)
	}
}
