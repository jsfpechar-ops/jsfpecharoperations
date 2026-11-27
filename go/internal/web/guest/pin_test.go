package guest

import (
	"crypto/hmac"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

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

func TestPinSessionValidLastsSevenDays(t *testing.T) {
	secret := "test-secret-key-for-pin"
	issuedAt := time.Date(2026, 11, 27, 12, 0, 0, 0, time.UTC)
	val, err := issuePinSession(secret, "tok", "123456", issuedAt)
	if err != nil {
		t.Fatalf("issuePinSession: %v", err)
	}
	req := httptest.NewRequest(http.MethodGet, "/l/tok", nil)
	req.AddCookie(&http.Cookie{Name: pinCookieName, Value: val})

	// Must stay valid well past 1 second (e.g. 2 hours into filling out the form).
	if !pinSessionValid(req, secret, "tok", "123456", issuedAt.Add(2*time.Hour)) {
		t.Fatal("expected pin session to remain valid 2 hours after issue")
	}
	// Must expire after 7 days.
	if pinSessionValid(req, secret, "tok", "123456", issuedAt.Add(8*24*time.Hour)) {
		t.Fatal("expected pin session to expire after 7 days")
	}
}
