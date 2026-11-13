package session

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Write side of the host session, ported from App/app/auth.py (brief 1280).
const (
	// DeviceCookieName is DEVICE_COOKIE.
	DeviceCookieName = "ubyhost_device"
	// SessionMaxAge is SESSION_MAX_AGE in seconds.
	SessionMaxAge = 12 * 60 * 60
	// SessionRememberMaxAge is SESSION_REMEMBER_MAX_AGE (sliding, 30 days).
	SessionRememberMaxAge = 30 * 24 * 60 * 60
	// SessionAbsoluteMaxAge is SESSION_ABSOLUTE_MAX_AGE (90 days from iat).
	SessionAbsoluteMaxAge = 90 * 24 * 60 * 60
	// SessionRefreshAfter is SESSION_REFRESH_AFTER (one day).
	SessionRefreshAfter = 24 * 60 * 60
	// DeviceMaxAge is DEVICE_MAX_AGE.
	DeviceMaxAge = 30 * 24 * 60 * 60
	// TwoFactorPendingMaxAge is TWO_FACTOR_PENDING_MAX_AGE.
	TwoFactorPendingMaxAge = 10 * 60
	// FreshLoginSeconds is FRESH_LOGIN_SECONDS.
	FreshLoginSeconds = 10 * 60
	// MaxRevealedGuests is MAX_REVEALED_GUESTS.
	MaxRevealedGuests = 50

	twoFactorSalt = "ubyhost-2fa-pending"
	deviceSalt    = "ubyhost-device"
)

// IssueOptions are the optional arguments of issue_session.
type IssueOptions struct {
	Workspace              int64  // workspace_user_id; 0 is None
	Remember               bool   // remember
	ImpersonationStartedAt *int64 // impersonation_started_at; nil uses now
	RevealedGuestIDs       []int64
	IssuedAt               *int64 // issued_at; nil uses now
}

// seconds is time.time() as a float, for the comparisons Python makes in float.
func seconds(now time.Time) float64 {
	return float64(now.UnixNano()) / 1e9
}

// IssueSession is auth.issue_session: the payload keys in Python order
// (uid, sv, iat, rf, rm, as, ast, rv), signed at now with salt ubyhost-session.
func IssueSession(secret string, userID, sessionVersion int64, opt IssueOptions, now time.Time) (string, error) {
	iat := now.Unix()
	if opt.IssuedAt != nil {
		iat = *opt.IssuedAt
	}
	fields := []pyField{{"uid", userID}, {"sv", sessionVersion}, {"iat", iat}, {"rf", now.Unix()}}
	if opt.Remember {
		fields = append(fields, pyField{"rm", int64(1)})
	}
	if opt.Workspace != 0 && opt.Workspace != userID {
		ast := now.Unix()
		if opt.ImpersonationStartedAt != nil {
			ast = *opt.ImpersonationStartedAt
		}
		fields = append(fields, pyField{"as", opt.Workspace}, pyField{"ast", ast})
		if len(opt.RevealedGuestIDs) > 0 {
			var unique []int64
			seen := map[int64]bool{}
			for _, id := range opt.RevealedGuestIDs {
				if !seen[id] {
					seen[id] = true
					unique = append(unique, id)
				}
			}
			if len(unique) > MaxRevealedGuests {
				unique = unique[len(unique)-MaxRevealedGuests:]
			}
			fields = append(fields, pyField{"rv", unique})
		}
	}
	return dumps(secret, salt, fields, now)
}

func dumps(secret, salt string, fields []pyField, now time.Time) (string, error) {
	return secure.NewTimedSerializer(secret, salt).Dumps(json.RawMessage(pyCompact(fields)), now)
}

// SessionMaxAgeFor is session_max_age(payload) in seconds.
func SessionMaxAgeFor(payload map[string]any) int {
	if truthy(payload["rm"]) {
		return SessionRememberMaxAge
	}
	return SessionMaxAge
}

// ReadPayload is auth._session_payload: 30 days at most, a remember-me
// session ends 90 days after iat, any other one 12 hours after signing.
// Verify, and so Load, use the same rule.
func ReadPayload(secret, token string, now time.Time) (map[string]any, bool) {
	if token == "" {
		return nil, false
	}
	s := secure.NewTimedSerializer(secret, salt)
	var raw json.RawMessage
	if err := s.Loads(token, SessionRememberMaxAge*time.Second, now, &raw); err != nil {
		return nil, false
	}
	payload, ok := decodePayload(raw)
	if !ok {
		return nil, false
	}
	if truthy(payload["rm"]) {
		iat, ok := intOrZero(payload, "iat")
		if !ok || seconds(now)-float64(iat) > SessionAbsoluteMaxAge {
			return nil, false
		}
		return payload, true
	}
	if err := s.Loads(token, SessionMaxAge*time.Second, now, &raw); err != nil {
		return nil, false
	}
	return payload, true
}

// intOrZero is int(payload.get(key, 0)) for integer values; ok is false
// where Python's int() would raise (a string, list or object).
func intOrZero(payload map[string]any, key string) (int64, bool) {
	v, present := payload[key]
	if !present {
		return 0, true
	}
	switch x := v.(type) {
	case int64:
		return x, true
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	}
	return 0, false
}

// SessionCookie is attach_session: HttpOnly, SameSite=Lax, Path=/, Secure when
// secure (hostweb.SecureCookies), 30 days with remember, else 12 hours.
func SessionCookie(token string, remember, secure bool) *http.Cookie {
	maxAge := SessionMaxAge
	if remember {
		maxAge = SessionRememberMaxAge
	}
	return &http.Cookie{Name: CookieName, Value: token, Path: "/", MaxAge: maxAge,
		HttpOnly: true, Secure: secure, SameSite: http.SameSiteLaxMode}
}

// ClearSessionCookie is clear_session: the same attributes, Max-Age=0.
func ClearSessionCookie(secure bool) *http.Cookie {
	return &http.Cookie{Name: CookieName, Value: "", Path: "/", MaxAge: -1,
		Expires: time.Unix(0, 0), HttpOnly: true, Secure: secure, SameSite: http.SameSiteLaxMode}
}

// RefreshSession is refresh_session_cookie: for a remember-me payload last
// signed a day or more ago, a re-signed cookie with the same iat, unless the
// response headers already set ubyhost_session. nil means leave the cookie.
func RefreshSession(secret string, payload map[string]any, header http.Header, secure bool, now time.Time) (*http.Cookie, error) {
	if !truthy(payload["rm"]) || !truthy(payload["uid"]) {
		return nil, nil
	}
	last, ok := intOrZero(payload, "iat")
	if _, present := payload["rf"]; present {
		last, ok = intOrZero(payload, "rf")
	}
	if !ok {
		return nil, errBadPayload
	}
	if seconds(now)-float64(last) < SessionRefreshAfter {
		return nil, nil
	}
	for _, v := range header.Values("Set-Cookie") {
		if strings.HasPrefix(v, CookieName+"=") {
			return nil, nil
		}
	}
	uid, _ := intOrZero(payload, "uid")
	sv, ok1 := intOrZero(payload, "sv")
	iat, ok2 := payload["iat"].(int64)
	if !ok1 || !ok2 {
		return nil, errBadPayload
	}
	opt := IssueOptions{Remember: true, IssuedAt: &iat}
	if as, ok := payload["as"].(int64); ok {
		opt.Workspace = as
	}
	if ast, ok := payload["ast"].(int64); ok {
		opt.ImpersonationStartedAt = &ast
	}
	if rv, ok := payload["rv"].([]any); ok {
		for _, e := range rv {
			if id, ok := e.(int64); ok {
				opt.RevealedGuestIDs = append(opt.RevealedGuestIDs, id)
			}
		}
	}
	token, err := IssueSession(secret, uid, sv, opt, now)
	if err != nil {
		return nil, err
	}
	return SessionCookie(token, true, secure), nil
}

// IssuedAt is session_issued_at for a loaded payload: int(payload["iat"]), or 0.
func IssuedAt(payload map[string]any) int64 {
	if iat, ok := payload["iat"].(int64); ok {
		return iat
	}
	return 0
}

// IsFresh is session_is_fresh: the login (iat) is at most limit seconds old.
// limit 0 means FreshLoginSeconds; payload nil means no signed-in user.
func IsFresh(payload map[string]any, limit int64, now time.Time) bool {
	if payload == nil {
		return false
	}
	if limit == 0 {
		limit = FreshLoginSeconds
	}
	iat := IssuedAt(payload)
	if iat <= 0 {
		return false
	}
	return seconds(now)-float64(iat) <= float64(limit)
}

// EndAllSessions is end_all_sessions: bump session_version.
func EndAllSessions(ctx context.Context, db *pgxpool.Pool, userID int64) error {
	_, err := db.Exec(ctx, `UPDATE user_account SET session_version = session_version + 1 WHERE id = $1`, userID)
	return err
}

// IssueTwoFactorPending is issue_two_factor_pending: {"uid","rm","next"}.
func IssueTwoFactorPending(secret string, userID int64, remember bool, nextPath string, now time.Time) (string, error) {
	return dumps(secret, twoFactorSalt, []pyField{{"uid", userID}, {"rm", remember}, {"next", nextPath}}, now)
}

// ReadTwoFactorPending is read_two_factor_pending: 10 minutes, an object with
// a truthy "uid", else false.
func ReadTwoFactorPending(secret, token string, now time.Time) (map[string]any, bool) {
	var raw json.RawMessage
	if err := secure.NewTimedSerializer(secret, twoFactorSalt).Loads(token, TwoFactorPendingMaxAge*time.Second, now, &raw); err != nil {
		return nil, false
	}
	payload, ok := decodePayload(raw)
	if !ok || !truthy(payload["uid"]) {
		return nil, false
	}
	return payload, true
}

// NewDeviceID is secrets.token_urlsafe(16).
func NewDeviceID() string {
	return tokenURLSafe(16)
}

// tokenURLSafe is secrets.token_urlsafe(n).
func tokenURLSafe(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

// DeviceToken is the value attach_device signs: {"uid","sv","did"}.
func DeviceToken(secret string, userID, sessionVersion int64, deviceID string, now time.Time) (string, error) {
	return dumps(secret, deviceSalt, []pyField{{"uid", userID}, {"sv", sessionVersion}, {"did", deviceID}}, now)
}

// DeviceCookie is attach_device's cookie: 30 days, HttpOnly, Lax, Path=/.
func DeviceCookie(token string, secure bool) *http.Cookie {
	return &http.Cookie{Name: DeviceCookieName, Value: token, Path: "/", MaxAge: DeviceMaxAge,
		HttpOnly: true, Secure: secure, SameSite: http.SameSiteLaxMode}
}

// devicePayload loads a device cookie value (30 days).
func devicePayload(secret, token string, now time.Time) (map[string]any, bool) {
	if token == "" {
		return nil, false
	}
	var raw json.RawMessage
	if err := secure.NewTimedSerializer(secret, deviceSalt).Loads(token, DeviceMaxAge*time.Second, now, &raw); err != nil {
		return nil, false
	}
	return decodePayload(raw)
}

// payloadInt is int(payload.get(key, -1)); ok is false where int() raises.
func payloadInt(payload map[string]any, key string) (int64, bool) {
	if _, present := payload[key]; !present {
		return -1, true
	}
	return intOrZero(payload, key)
}

// TrustedDevice is trusted_device: the device cookie belongs to the active
// account that logs in with email and carries its session_version. Python
// raises (HTTP 500) on a non-integer uid/sv; Go answers false.
func TrustedDevice(ctx context.Context, db *pgxpool.Pool, secret, token, email string, now time.Time) (bool, error) {
	if token == "" || email == "" {
		return false, nil
	}
	payload, ok := devicePayload(secret, token, now)
	if !ok {
		return false, nil
	}
	account, err := AccountByEmail(ctx, db, email)
	if err != nil || account == nil {
		return false, err
	}
	uid, ok1 := payloadInt(payload, "uid")
	sv, ok2 := payloadInt(payload, "sv")
	return ok1 && ok2 && account.Active == 1 && uid == account.ID && sv == account.SessionVersion, nil
}

// DeviceCookieValid is device_cookie_valid: signed, fresh, and the uid names
// an active account whose session_version matches.
func DeviceCookieValid(ctx context.Context, db *pgxpool.Pool, secret, token string, now time.Time) (bool, error) {
	payload, ok := devicePayload(secret, token, now)
	if !ok {
		return false, nil
	}
	uid, ok := payloadInt(payload, "uid")
	if !ok {
		return false, nil
	}
	account, err := accountWhere(ctx, db, `id = $1 AND active = 1`, uid)
	if err != nil || account == nil {
		return false, err
	}
	sv, ok := payloadInt(payload, "sv")
	return ok && account.Active == 1 && sv == account.SessionVersion, nil
}
