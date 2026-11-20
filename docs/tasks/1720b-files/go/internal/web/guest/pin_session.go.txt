package guest

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"net/http"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	pinCookieName  = "ubyhost_pin"
	pinCookieAge   = 60 * 60 * 24 * 7
	pinSessionSalt = "ubyhost-guest-pin"
)

func pinMatches(secret, token, entered, expected string) bool {
	return hmac.Equal(
		[]byte(secure.PinFingerprint(secret, token, entered)),
		[]byte(secure.PinFingerprint(secret, token, expected)),
	)
}

func issuePinSession(secret, token, pin string, now time.Time) (string, error) {
	return secure.NewTimedSerializer(secret, pinSessionSalt).Dumps(map[string]any{
		"token": token,
		"pin":   secure.PinFingerprint(secret, token, pin),
	}, now)
}

func pinSessionValid(r *http.Request, secret, token, pin string, now time.Time) bool {
	raw := hostweb.Cookie(r, pinCookieName)
	if raw == "" {
		return false
	}
	var payload map[string]any
	if err := secure.NewTimedSerializer(secret, pinSessionSalt).Loads(raw, pinCookieAge, now, &payload); err != nil {
		return false
	}
	tok, _ := payload["token"].(string)
	fp, _ := payload["pin"].(string)
	return hmac.Equal([]byte(tok), []byte(token)) &&
		hmac.Equal([]byte(fp), []byte(secure.PinFingerprint(secret, token, pin)))
}

func attachPinSession(w http.ResponseWriter, secret, token, pin string, getenv func(string) string, now time.Time) error {
	val, err := issuePinSession(secret, token, pin, now)
	if err != nil {
		return err
	}
	http.SetCookie(w, &http.Cookie{
		Name:     pinCookieName,
		Value:    val,
		Path:     "/",
		MaxAge:   pinCookieAge,
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Secure:   hostweb.SecureCookies(getenv),
	})
	return nil
}

// PinSessionValid is exported for briefs 1720c+ (_require_pin parity).
func PinSessionValid(r *http.Request, getenv func(string) string, token, pin string, now time.Time) bool {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return false
	}
	return pinSessionValid(r, secret, token, pin, now)
}

// PinLockKey is token:pin_fingerprint for per-link lockouts (WP19).
func PinLockKey(secret, lockToken, expectedPin string) string {
	return lockToken + ":" + secure.PinFingerprint(secret, lockToken, expectedPin)
}

// GuestCSRF mints a page token bound to the ubyhost_csrf cookie (render_guest).
func guestCSRF(r *http.Request, secret string, getenv func(string) string, now time.Time) (string, *http.Cookie, error) {
	nonce := hostweb.Cookie(r, "ubyhost_csrf")
	var cookie *http.Cookie
	if nonce == "" {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return "", nil, err
		}
		nonce = base64.RawURLEncoding.EncodeToString(buf)
		cookie = &http.Cookie{
			Name: "ubyhost_csrf", Value: nonce, Path: "/", MaxAge: 60 * 60 * 24,
			HttpOnly: true, SameSite: http.SameSiteStrictMode, Secure: hostweb.SecureCookies(getenv),
		}
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(secret, "ubyhost-csrf").Dumps(map[string]any{
		"nonce": hex.EncodeToString(sum[:]),
	}, now)
	return token, cookie, err
}
