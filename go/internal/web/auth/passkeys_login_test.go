package auth

// Tests for the passkey login routes (POST /login/passkey/options and
// POST /login/passkey) on Postgres. The software authenticator in
// passkeys_authenticator_test.go answers the ceremonies. The two fixtures in
// testdata/ tie the Go ceremony to py_webauthn: passkeys_python.json is made by
// Python (read here), passkeys_go.json is made here with PASSKEYS_WRITE_FIXTURE=1
// and verified by App/tests/test_go_passkeys_golden.py.

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/fxamacker/cbor/v2"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	lgSessionCookie = "ubyhost_session"
	lgDeviceCookie  = "ubyhost_device"
	lgAliceID       = int64(1)
	lgBobID         = int64(2)
	lgPythonFixture = "testdata/passkeys_python.json"
	lgGoFixture     = "testdata/passkeys_go.json"
	lgWriteEnv      = "PASSKEYS_WRITE_FIXTURE"
	lgExpired       = "2001-01-01T00:00:00.000000+00:00"
)

// --- helpers -----------------------------------------------------------------

// lgHarness is newPkHarness with another public base URL (the routes read
// their environment through getenv, so only the mux is mounted again).
func lgHarness(t *testing.T, base string) *pkHarness {
	t.Helper()
	h := newPkHarness(t)
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      pkTestSecret,
		"UBYHOST_DEPLOYMENT":      "local",
		"UBYHOST_PUBLIC_BASE_URL": base,
		"UBYHOST_APP_BASE_URL":    "https://app.ubyhost.example.test",
	}
	getenv := func(k string) string { return env[k] }
	h.mux = http.NewServeMux()
	for _, r := range PasskeyRoutes(h.pool, getenv, time.Now) {
		h.mux.HandleFunc(r.Pattern, r.Handler)
	}
	return h
}

// lgCOSE is the stored COSE key of the software authenticator: EC2 P-256, ES256.
func lgCOSE(t *testing.T, a *softAuthenticator) []byte {
	t.Helper()
	x := a.key.PublicKey.X.FillBytes(make([]byte, 32))
	y := a.key.PublicKey.Y.FillBytes(make([]byte, 32))
	raw, err := cbor.Marshal(map[int]any{1: 2, 3: -7, -1: 1, -2: x, -3: y})
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

// lgLoginOptions asks for a login challenge with no session.
func (h *pkHarness) lgLoginOptions() (*httptest.ResponseRecorder, string) {
	h.t.Helper()
	rec := h.post(pkRequest{path: "/login/passkey/options"})
	var o struct {
		Challenge string `json:"challenge"`
	}
	if rec.Code == http.StatusOK {
		if err := json.Unmarshal(rec.Body.Bytes(), &o); err != nil {
			h.t.Fatalf("login options body: %v", err)
		}
	}
	return rec, o.Challenge
}

// lgLogin posts a login body (a JSON object) to /login/passkey.
func (h *pkHarness) lgLogin(fields map[string]any) *httptest.ResponseRecorder {
	h.t.Helper()
	raw, err := json.Marshal(fields)
	if err != nil {
		h.t.Fatal(err)
	}
	return h.post(pkRequest{path: "/login/passkey", body: string(raw)})
}

// lgAssert is the assertion a browser sends for the challenge: user present and
// verified, the given counter, origin and rpId of this site. A nil handle is
// omitted from the response.
func lgAssert(t *testing.T, a *softAuthenticator, challenge string, counter uint32, handle []byte) map[string]any {
	t.Helper()
	return a.Assert(t, assertionInput{
		ceremonyInput: ceremonyInput{Challenge: challenge, Origin: pkOrigin, RPID: pkRPID},
		Counter:       counter,
		Flags:         flagUP | flagUV,
		UserHandle:    handle,
	})
}

// lgSignIn asks for a login challenge, answers it, and posts the login with
// the extra fields (remember and next default to true and "/").
func (h *pkHarness) lgSignIn(a *softAuthenticator, counter uint32, handle []byte, extra map[string]any) *httptest.ResponseRecorder {
	h.t.Helper()
	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		h.t.Fatalf("login options: %d %s", rec.Code, rec.Body.String())
	}
	fields := map[string]any{"credential": lgAssert(h.t, a, ch, counter, handle), "remember": true, "next": "/"}
	for k, v := range extra {
		fields[k] = v
	}
	return h.lgLogin(fields)
}

// lgSetHandle gives the account a WebAuthn user handle and returns its bytes.
func (h *pkHarness) lgSetHandle(uid int64) []byte {
	h.t.Helper()
	raw := make([]byte, passkeyHandleBytes)
	if _, err := rand.Read(raw); err != nil {
		h.t.Fatal(err)
	}
	if _, err := h.pool.Exec(h.ctx, `UPDATE user_account SET webauthn_user_handle = $1 WHERE id = $2`, b64url(raw), uid); err != nil {
		h.t.Fatal(err)
	}
	return raw
}

// lgHandle is the stored user handle of the account, decoded.
func (h *pkHarness) lgHandle(uid int64) []byte {
	h.t.Helper()
	var stored string
	if err := h.pool.QueryRow(h.ctx, `SELECT webauthn_user_handle FROM user_account WHERE id = $1`, uid).Scan(&stored); err != nil {
		h.t.Fatal(err)
	}
	return b64Decode(h.t, stored)
}

// lgSeed inserts a passkey row for the account, stored the way registration
// stores it (base64url COSE key, base64url credential id).
func (h *pkHarness) lgSeed(uid int64, a *softAuthenticator, signCount int64) int64 {
	h.t.Helper()
	var id int64
	err := h.pool.QueryRow(h.ctx, `INSERT INTO passkey (user_account_id, credential_id, public_key, sign_count, transports, name, backed_up, created_at)
		VALUES ($1, $2, $3, $4, NULL, 'seeded', 0, $5) RETURNING id`,
		uid, a.ID(), b64url(lgCOSE(h.t, a)), signCount, pkStamp).Scan(&id)
	if err != nil {
		h.t.Fatal(err)
	}
	return id
}

// lgPasskeyID is the row id of a stored credential id.
func (h *pkHarness) lgPasskeyID(credID string) int64 {
	h.t.Helper()
	var id int64
	if err := h.pool.QueryRow(h.ctx, `SELECT id FROM passkey WHERE credential_id = $1`, credID).Scan(&id); err != nil {
		h.t.Fatal(err)
	}
	return id
}

// lgPasskeyRow is the counter and the last use of one passkey row.
func (h *pkHarness) lgPasskeyRow(id int64) (int64, *string) {
	h.t.Helper()
	var sc int64
	var last *string
	if err := h.pool.QueryRow(h.ctx, `SELECT sign_count, last_used_at FROM passkey WHERE id = $1`, id).Scan(&sc, &last); err != nil {
		h.t.Fatal(err)
	}
	return sc, last
}

func lgHash(t *testing.T, challenge string) string {
	sum := sha256.Sum256(b64Decode(t, challenge))
	return hex.EncodeToString(sum[:])
}

// lgChallengeRow is the webauthn_challenge row of a challenge the server issued.
type lgChallengeRow struct {
	Purpose string
	NoUser  bool
	Used    bool
}

func (h *pkHarness) lgChallengeRow(challenge string) (lgChallengeRow, bool) {
	h.t.Helper()
	var row lgChallengeRow
	err := h.pool.QueryRow(h.ctx, `SELECT purpose, user_account_id IS NULL, used_at IS NOT NULL
		FROM webauthn_challenge WHERE challenge_hash = $1`, lgHash(h.t, challenge)).Scan(&row.Purpose, &row.NoUser, &row.Used)
	if err != nil {
		return row, false
	}
	return row, true
}

func (h *pkHarness) rateCount(scope string) int {
	h.t.Helper()
	var n int
	if err := h.pool.QueryRow(h.ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1`, scope).Scan(&n); err != nil {
		h.t.Fatal(err)
	}
	return n
}

// findAudit is the first audit row with this action and detail.
func (h *pkHarness) findAudit(action, detail string) (pkAudit, bool) {
	h.t.Helper()
	for _, a := range h.audits() {
		if a.Action == action && a.Detail == detail {
			return a, true
		}
	}
	return pkAudit{}, false
}

func lgCookie(rec *httptest.ResponseRecorder, name string) *http.Cookie {
	for _, c := range rec.Result().Cookies() {
		if c.Name == name {
			return c
		}
	}
	return nil
}

// wantRefused checks a 401 login refusal: the generic text, no-store, no
// session cookie, and the audit row with the reason.
func (h *pkHarness) wantRefused(rec *httptest.ResponseRecorder, reason string) {
	h.t.Helper()
	if rec.Code != http.StatusUnauthorized {
		h.t.Fatalf("status %d, want 401 (reason %s): %s", rec.Code, reason, rec.Body.String())
	}
	if got := decodeError(h.t, rec); got != pkText("passkeys.error.login_failed") {
		h.t.Errorf("error text %q", got)
	}
	h.assertNoCache(rec)
	if c := lgCookie(rec, lgSessionCookie); c != nil {
		h.t.Errorf("refused login set %s", lgSessionCookie)
	}
	a, ok := h.findAudit("passkey_login_failed", "reason="+reason)
	if !ok {
		h.t.Errorf("no passkey_login_failed reason=%s audit row: %+v", reason, h.audits())
		return
	}
	if a.Actor != "anonymous" || a.Owner != nil {
		h.t.Errorf("failure audit actor %q owner %v, want anonymous and none", a.Actor, a.Owner)
	}
}

// --- (1) options --------------------------------------------------------------

func TestPasskeyLoginOptionsShape(t *testing.T) {
	h := newPkHarness(t)
	rec, challenge := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	h.assertNoCache(rec)
	var raw map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &raw); err != nil {
		t.Fatalf("body is not JSON: %v", err)
	}
	if challenge == "" {
		t.Fatal("no challenge")
	}
	if raw["rpId"] != pkRPID {
		t.Errorf("rpId %v, want %s", raw["rpId"], pkRPID)
	}
	if raw["userVerification"] != "required" {
		t.Errorf("userVerification %v, want required", raw["userVerification"])
	}
	if list, ok := raw["allowCredentials"].([]any); ok && len(list) != 0 {
		t.Errorf("allowCredentials %v, want empty", list)
	}
	row, ok := h.lgChallengeRow(challenge)
	if !ok {
		t.Fatal("no webauthn_challenge row with sha256 of the challenge bytes")
	}
	if row.Purpose != passkeyLogin || !row.NoUser || row.Used {
		t.Errorf("row %+v, want purpose login, user_account_id NULL, unused", row)
	}
}

// --- (2) happy login, next, remember ------------------------------------------

func TestPasskeyLoginHappyPath(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	if rec := h.registerFor(h.aliceS, a, pkOrigin, pkRPID, "Login key"); rec.Code != http.StatusOK {
		t.Fatalf("register: %d %s", rec.Code, rec.Body.String())
	}
	id := h.lgPasskeyID(a.ID())
	before, _ := h.lgPasskeyRow(id)
	if before != 3 {
		t.Fatalf("registered sign_count %d, want 3", before)
	}

	rec := h.lgSignIn(a, 4, h.lgHandle(lgAliceID), map[string]any{"next": "/dashboard"})
	if rec.Code != http.StatusOK {
		t.Fatalf("login: %d %s", rec.Code, rec.Body.String())
	}
	h.assertNoCache(rec)
	var got map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil || got["redirect"] != "/dashboard" {
		t.Fatalf("body %q, want redirect /dashboard", rec.Body.String())
	}
	sc := lgCookie(rec, lgSessionCookie)
	if sc == nil || sc.Value == "" {
		t.Fatal("no session cookie")
	}
	if sc.MaxAge != session.SessionRememberMaxAge {
		t.Errorf("remember cookie Max-Age %d, want %d", sc.MaxAge, session.SessionRememberMaxAge)
	}
	if lgCookie(rec, lgDeviceCookie) == nil {
		t.Error("no device cookie")
	}
	var seen bool
	if err := h.pool.QueryRow(h.ctx, `SELECT last_login_at IS NOT NULL FROM user_account WHERE id = $1`, lgAliceID).Scan(&seen); err != nil || !seen {
		t.Errorf("last_login_at not set (err %v)", err)
	}
	audit, ok := h.findAudit(ActionLogin, fmt.Sprintf("method=passkey:%d", id))
	if !ok {
		t.Fatalf("no login audit row: %+v", h.audits())
	}
	if audit.Actor != "alice" || audit.Owner == nil || *audit.Owner != lgAliceID {
		t.Errorf("login audit actor %q owner %v", audit.Actor, audit.Owner)
	}
	if sc, last := h.lgPasskeyRow(id); sc != 4 || last == nil {
		t.Errorf("passkey after login sign_count %d last_used_at %v, want 4 and set", sc, last)
	}
	if n := h.countUsedLoginChallenges(); n != 1 {
		t.Errorf("used login challenges %d, want 1", n)
	}
}

func (h *pkHarness) countUsedLoginChallenges() int {
	h.t.Helper()
	var n int
	if err := h.pool.QueryRow(h.ctx, `SELECT COUNT(*) FROM webauthn_challenge WHERE purpose = 'login' AND used_at IS NOT NULL`).Scan(&n); err != nil {
		h.t.Fatal(err)
	}
	return n
}

// lgSeededAlice gives alice a handle and one seeded passkey with counter 0.
func (h *pkHarness) lgSeededAlice() (*softAuthenticator, int64) {
	h.t.Helper()
	a := newSoftAuthenticator(h.t)
	h.lgSetHandle(lgAliceID)
	return a, h.lgSeed(lgAliceID, a, 0)
}

func TestPasskeyLoginNextAndRemember(t *testing.T) {
	h := newPkHarness(t)
	a, _ := h.lgSeededAlice()

	rec := h.lgSignIn(a, 1, h.lgHandle(lgAliceID), map[string]any{"next": "//evil.example"})
	if rec.Code != http.StatusOK {
		t.Fatalf("login with //evil.example: %d %s", rec.Code, rec.Body.String())
	}
	if got := decodeRedirect(t, rec); got != "/" {
		t.Errorf("redirect %q for next=//evil.example, want /", got)
	}

	rec = h.lgSignIn(a, 2, h.lgHandle(lgAliceID), map[string]any{"remember": false, "next": "/"})
	if rec.Code != http.StatusOK {
		t.Fatalf("login remember false: %d %s", rec.Code, rec.Body.String())
	}
	c := lgCookie(rec, lgSessionCookie)
	if c == nil {
		t.Fatal("no session cookie")
	}
	// The spec said "no Max-Age". The Python reference (attach_session) sets
	// max_age=session_max_age(None), the 12-hour SESSION_MAX_AGE, so Go does too.
	if c.MaxAge != session.SessionMaxAge {
		t.Errorf("non-remember cookie Max-Age %d, want %d (Python session_max_age)", c.MaxAge, session.SessionMaxAge)
	}
	payload, ok := session.Verify(pkTestSecret, c.Value, time.Now())
	if !ok {
		t.Fatal("session token does not verify")
	}
	if rm, _ := payload["rm"].(bool); rm {
		t.Errorf("payload rm %v, want false", payload["rm"])
	}
}

func decodeRedirect(t *testing.T, rec *httptest.ResponseRecorder) string {
	t.Helper()
	var got map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("body %q is not JSON", rec.Body.String())
	}
	return got["redirect"]
}

// --- (3) replay ---------------------------------------------------------------

func TestPasskeyLoginReplay(t *testing.T) {
	h := newPkHarness(t)
	a, _ := h.lgSeededAlice()
	handle := h.lgHandle(lgAliceID)

	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	body := map[string]any{"credential": lgAssert(t, a, ch, 1, handle), "remember": true, "next": "/"}
	if rec := h.lgLogin(body); rec.Code != http.StatusOK {
		t.Fatalf("first login: %d %s", rec.Code, rec.Body.String())
	}
	replay := h.lgLogin(body)
	h.wantRefused(replay, "challenge")
}

// --- (4) counters -------------------------------------------------------------

func TestPasskeyLoginCounterRegressionIsClone(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	h.lgSetHandle(lgAliceID)
	id := h.lgSeed(lgAliceID, a, 5)

	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	rec = h.lgLogin(map[string]any{"credential": lgAssert(t, a, ch, 3, h.lgHandle(lgAliceID)), "remember": true, "next": "/"})
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("regressed counter: status %d, want 401: %s", rec.Code, rec.Body.String())
	}
	h.assertNoCache(rec)
	if lgCookie(rec, lgSessionCookie) != nil {
		t.Error("clone refusal set a session cookie")
	}
	audit, ok := h.findAudit("passkey_clone_suspected", fmt.Sprintf("passkey=%d", id))
	if !ok {
		t.Fatalf("no passkey_clone_suspected row: %+v", h.audits())
	}
	if audit.Actor != "alice" || audit.Owner == nil || *audit.Owner != lgAliceID {
		t.Errorf("clone audit actor %q owner %v", audit.Actor, audit.Owner)
	}
	if sc, _ := h.lgPasskeyRow(id); sc != 5 {
		t.Errorf("sign_count %d after refusal, want 5", sc)
	}
}

func TestPasskeyLoginSyncedZeroCounterAllowed(t *testing.T) {
	h := newPkHarness(t)
	a, id := h.lgSeededAlice()
	rec := h.lgSignIn(a, 0, h.lgHandle(lgAliceID), nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("stored 0 and assertion 0: %d %s", rec.Code, rec.Body.String())
	}
	if sc, _ := h.lgPasskeyRow(id); sc != 0 {
		t.Errorf("sign_count %d, want 0", sc)
	}
	if lgCookie(rec, lgSessionCookie) == nil {
		t.Error("no session cookie")
	}
}

// --- (5) origin, rpId, flags --------------------------------------------------

func TestPasskeyLoginCeremonyChecks(t *testing.T) {
	cases := []struct {
		name   string
		origin string
		rpID   string
		flags  byte
	}{
		{"wrong origin", "https://evil.example", pkRPID, flagUP | flagUV},
		{"wrong rpId", pkOrigin, "evil.example", flagUP | flagUV},
		{"user verification off", pkOrigin, pkRPID, flagUP},
		{"user presence off", pkOrigin, pkRPID, flagUV},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			h := newPkHarness(t)
			a, _ := h.lgSeededAlice()
			rec, ch := h.lgLoginOptions()
			if rec.Code != http.StatusOK {
				t.Fatalf("options: %d", rec.Code)
			}
			cred := a.Assert(t, assertionInput{
				ceremonyInput: ceremonyInput{Challenge: ch, Origin: tc.origin, RPID: tc.rpID},
				Counter:       1,
				Flags:         tc.flags,
				UserHandle:    h.lgHandle(lgAliceID),
			})
			h.wantRefused(h.lgLogin(map[string]any{"credential": cred, "remember": true}), "invalid")
		})
	}
}

// --- (6) unknown credential, inactive account, handles -------------------------

func TestPasskeyLoginUnknownCredential(t *testing.T) {
	h := newPkHarness(t)
	h.lgSeededAlice()
	stranger := newSoftAuthenticator(t)
	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	h.wantRefused(h.lgLogin(map[string]any{"credential": lgAssert(t, stranger, ch, 1, h.lgHandle(lgAliceID)), "remember": true}), "unknown")
}

func TestPasskeyLoginInactiveAccount(t *testing.T) {
	h := newPkHarness(t)
	a, _ := h.lgSeededAlice()
	if _, err := h.pool.Exec(h.ctx, `UPDATE user_account SET active = 0 WHERE id = $1`, lgAliceID); err != nil {
		t.Fatal(err)
	}
	rec := h.lgSignIn(a, 1, h.lgHandle(lgAliceID), nil)
	h.wantRefused(rec, "inactive")
}

// A credential belongs to one account: a handle of another account is refused,
// and a login without a handle is only ever the credential owner's session.
func TestPasskeyLoginCredentialOwner(t *testing.T) {
	h := newPkHarness(t)
	a, _ := h.lgSeededAlice()
	bobHandle := h.lgSetHandle(lgBobID)

	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	h.wantRefused(h.lgLogin(map[string]any{"credential": lgAssert(t, a, ch, 1, bobHandle), "remember": true}), "handle")

	rec = h.lgSignIn(a, 1, nil, map[string]any{"next": "/"})
	if rec.Code != http.StatusOK {
		t.Fatalf("login without userHandle: %d %s", rec.Code, rec.Body.String())
	}
	c := lgCookie(rec, lgSessionCookie)
	if c == nil {
		t.Fatal("no session cookie")
	}
	payload, ok := session.Verify(pkTestSecret, c.Value, time.Now())
	if !ok || fmt.Sprint(payload["uid"]) != "1" {
		t.Errorf("session uid %v, want alice (1)", payload["uid"])
	}
}

// --- (7) purpose confusion ----------------------------------------------------

func TestPasskeyLoginChallengeCannotRegister(t *testing.T) {
	h := newPkHarness(t)
	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	a := newSoftAuthenticator(t)
	reg := h.register(h.aliceS, a.Register(t, ceremonyInput{Challenge: ch, Origin: pkOrigin, RPID: pkRPID}, 1), "Stolen", pkUA)
	if reg.Code != http.StatusBadRequest {
		t.Fatalf("registration with a login challenge: %d %s", reg.Code, reg.Body.String())
	}
	if got := decodeError(t, reg); got != pkText("passkeys.error.failed") {
		t.Errorf("error %q", got)
	}
	if _, ok := h.findAudit("passkey_add_failed", "reason=challenge"); !ok {
		t.Errorf("no passkey_add_failed reason=challenge row: %+v", h.audits())
	}
	if n := h.passkeyCount(lgAliceID); n != 0 {
		t.Errorf("passkeys %d after refused registration, want 0", n)
	}
}

func TestPasskeyRegisterChallengeCannotLogin(t *testing.T) {
	h := newPkHarness(t)
	rec, o := h.options(h.aliceS)
	if rec.Code != http.StatusOK {
		t.Fatalf("registration options: %d", rec.Code)
	}
	a := newSoftAuthenticator(t)
	h.lgSetHandle(lgAliceID)
	h.lgSeed(lgAliceID, a, 0)
	h.wantRefused(h.lgLogin(map[string]any{
		"credential": lgAssert(t, a, o.Challenge, 1, h.lgHandle(lgAliceID)),
		"remember":   true,
	}), "challenge")
}

// --- (8) expired --------------------------------------------------------------

func TestPasskeyLoginExpiredChallenge(t *testing.T) {
	h := newPkHarness(t)
	a, _ := h.lgSeededAlice()
	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	if _, err := h.pool.Exec(h.ctx, `UPDATE webauthn_challenge SET expires_at = $1 WHERE challenge_hash = $2`, lgExpired, lgHash(t, ch)); err != nil {
		t.Fatal(err)
	}
	h.wantRefused(h.lgLogin(map[string]any{"credential": lgAssert(t, a, ch, 1, h.lgHandle(lgAliceID)), "remember": true}), "challenge")
}

// --- (9) rate limits ----------------------------------------------------------

func TestPasskeyLoginOptionsRateLimit(t *testing.T) {
	h := newPkHarness(t)
	for i := 0; i < passkeyOptionsMax; i++ {
		if rec, _ := h.lgLoginOptions(); rec.Code != http.StatusOK {
			t.Fatalf("options %d: %d", i+1, rec.Code)
		}
	}
	rec, _ := h.lgLoginOptions()
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("31st options: %d, want 429", rec.Code)
	}
	h.assertNoCache(rec)
	if got := decodeError(t, rec); got != pkText("passkeys.error.rate_limited") {
		t.Errorf("error %q", got)
	}
}

func TestPasskeyLoginFailureRateLimit(t *testing.T) {
	h := newPkHarness(t)
	a, _ := h.lgSeededAlice()
	// A valid answer for a challenge issued before the budget is spent.
	rec, ch := h.lgLoginOptions()
	if rec.Code != http.StatusOK {
		t.Fatalf("options: %d", rec.Code)
	}
	valid := map[string]any{"credential": lgAssert(t, a, ch, 1, h.lgHandle(lgAliceID)), "remember": true}
	for i := 1; i <= passkeyFailMax; i++ {
		rec := h.lgLogin(map[string]any{})
		if rec.Code != http.StatusBadRequest {
			t.Fatalf("failure %d: %d %s", i, rec.Code, rec.Body.String())
		}
	}
	if n := h.rateCount(passkeyFailScope); n != passkeyFailMax {
		t.Fatalf("passkey_fail events %d, want %d", n, passkeyFailMax)
	}
	blocked := h.lgLogin(valid)
	if blocked.Code != http.StatusTooManyRequests {
		t.Fatalf("login after %d failures: %d, want 429 with a valid body", passkeyFailMax, blocked.Code)
	}
	if lgCookie(blocked, lgSessionCookie) != nil {
		t.Error("blocked login set a session cookie")
	}
}

// --- (10) malformed bodies ----------------------------------------------------

func TestPasskeyLoginMalformedBodies(t *testing.T) {
	cases := map[string]string{
		"over 64 KiB": `{"credential": {"id": "` + strings.Repeat("a", passkeyBodyMax) + `"}}`,
		"non-object":  `{"credential": "x"}`,
		"missing":     `{"name": "x"}`,
	}
	for name, body := range cases {
		t.Run(name, func(t *testing.T) {
			h := newPkHarness(t)
			before := h.rateCount(passkeyFailScope)
			rec := h.post(pkRequest{path: "/login/passkey", body: body})
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status %d, want 400: %s", rec.Code, rec.Body.String())
			}
			if got := decodeError(t, rec); got != pkText("passkeys.error.login_failed") {
				t.Errorf("error %q", got)
			}
			if n := h.rateCount(passkeyFailScope); n != before+1 {
				t.Errorf("passkey_fail events %d, want %d", n, before+1)
			}
		})
	}
}

// --- (11) base URL gate -------------------------------------------------------

func TestPasskeyLoginBaseURLGate(t *testing.T) {
	for _, base := range []string{
		"http://ubyhost.example.test",
		"http://127.0.0.1:8080",
		"https://127.0.0.1",
		"http://[::1]:8080",
	} {
		t.Run(base, func(t *testing.T) {
			h := lgHarness(t, base)
			rec, _ := h.lgLoginOptions()
			if rec.Code != http.StatusConflict {
				t.Fatalf("status %d, want 409", rec.Code)
			}
			if got := decodeError(t, rec); got != pkText("passkeys.error.unavailable") {
				t.Errorf("error %q", got)
			}
		})
	}
	t.Run("http://localhost:8080", func(t *testing.T) {
		h := lgHarness(t, "http://localhost:8080")
		rec, _ := h.lgLoginOptions()
		if rec.Code != http.StatusOK {
			t.Fatalf("status %d, want 200: %s", rec.Code, rec.Body.String())
		}
		if got := decodeRPID(t, rec); got != "localhost" {
			t.Errorf("rpId %q, want localhost", got)
		}
	})
}

func decodeRPID(t *testing.T, rec *httptest.ResponseRecorder) string {
	t.Helper()
	var o struct {
		RPID string `json:"rpId"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &o); err != nil {
		t.Fatalf("body is not JSON: %v", err)
	}
	return o.RPID
}

// --- (12) Python fixture -------------------------------------------------------

type lgPyCeremony struct {
	Challenge  string          `json:"challenge"`
	Credential json.RawMessage `json:"credential"`
}

type lgPyFixture struct {
	RPID         string       `json:"rp_id"`
	Origin       string       `json:"origin"`
	UserHandle   string       `json:"user_handle"`
	CredentialID string       `json:"credential_id"`
	PublicKey    string       `json:"public_key"`
	SignCount    int64        `json:"sign_count"`
	Registration lgPyCeremony `json:"registration"`
	Login        lgPyCeremony `json:"login"`
}

func TestPasskeyPythonFixtureInterop(t *testing.T) {
	raw, err := os.ReadFile(lgPythonFixture)
	if err != nil {
		t.Fatal(err)
	}
	var fx lgPyFixture
	if err := json.Unmarshal(raw, &fx); err != nil {
		t.Fatalf("fixture: %v", err)
	}
	h := lgHarness(t, fx.Origin)
	if fx.RPID != pkRPID || fx.Origin != pkOrigin {
		t.Fatalf("fixture rp %q origin %q do not match the test site", fx.RPID, fx.Origin)
	}

	// Registration made by Python, for the account that owns the handle.
	if _, err := h.pool.Exec(h.ctx, `UPDATE user_account SET webauthn_user_handle = $1 WHERE id = $2`, fx.UserHandle, lgAliceID); err != nil {
		t.Fatal(err)
	}
	uid := lgAliceID
	if err := storeChallenge(h.ctx, h.pool, b64Decode(t, fx.Registration.Challenge), passkeyRegister, &uid, time.Now()); err != nil {
		t.Fatal(err)
	}
	rec := h.post(pkRequest{path: "/account/passkeys", session: h.aliceS,
		body: mustJSON(t, map[string]any{"credential": fx.Registration.Credential, "name": "Python key"})})
	if rec.Code != http.StatusOK {
		t.Fatalf("registration of the Python credential: %d %s", rec.Code, rec.Body.String())
	}
	var credID, pubKey string
	if err := h.pool.QueryRow(h.ctx, `SELECT credential_id, public_key FROM passkey WHERE user_account_id = $1`, lgAliceID).Scan(&credID, &pubKey); err != nil {
		t.Fatal(err)
	}
	if credID != fx.CredentialID {
		t.Errorf("stored credential_id %q, want %q", credID, fx.CredentialID)
	}
	if pubKey != fx.PublicKey {
		t.Errorf("stored public_key %q, want %q", pubKey, fx.PublicKey)
	}

	// Login with the Python assertion (counter 7 > stored 0).
	if err := storeChallenge(h.ctx, h.pool, b64Decode(t, fx.Login.Challenge), passkeyLogin, nil, time.Now()); err != nil {
		t.Fatal(err)
	}
	rec = h.lgLogin(map[string]any{"credential": fx.Login.Credential, "remember": true, "next": "/"})
	if rec.Code != http.StatusOK {
		t.Fatalf("login with the Python assertion: %d %s", rec.Code, rec.Body.String())
	}
	if sc, _ := h.lgPasskeyRow(h.lgPasskeyID(fx.CredentialID)); sc != 7 {
		t.Errorf("sign_count after the Python login %d, want 7", sc)
	}
}

func mustJSON(t *testing.T, v any) string {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}

// --- (13) Go fixture for py_webauthn --------------------------------------------

type lgGoFile struct {
	RPID            string          `json:"rp_id"`
	Origin          string          `json:"origin"`
	CredentialID    string          `json:"credential_id"`
	PublicKey       string          `json:"public_key"`
	SignCountBefore int64           `json:"sign_count_before"`
	Challenge       string          `json:"challenge"`
	Credential      json.RawMessage `json:"credential"`
}

// TestPasskeyGoFixture writes testdata/passkeys_go.json when
// PASSKEYS_WRITE_FIXTURE=1 (a Go registration with counter 2, then a Go login
// with counter 4). In every run it checks that the committed file parses.
func TestPasskeyGoFixture(t *testing.T) {
	if os.Getenv(lgWriteEnv) == "1" {
		writeGoFixture(t)
	}
	raw, err := os.ReadFile(lgGoFixture)
	if err != nil {
		t.Fatalf("committed fixture missing (run with %s=1): %v", lgWriteEnv, err)
	}
	var fx lgGoFile
	if err := json.Unmarshal(raw, &fx); err != nil {
		t.Fatalf("fixture does not parse: %v", err)
	}
	if fx.RPID != pkRPID || fx.Origin != pkOrigin {
		t.Errorf("rp %q origin %q", fx.RPID, fx.Origin)
	}
	if fx.SignCountBefore != 2 {
		t.Errorf("sign_count_before %d, want 2", fx.SignCountBefore)
	}
	b64Decode(t, fx.CredentialID)
	b64Decode(t, fx.PublicKey)
	b64Decode(t, fx.Challenge)
	var cred struct {
		ID       string `json:"id"`
		Response struct {
			Signature string `json:"signature"`
		} `json:"response"`
	}
	if err := json.Unmarshal(fx.Credential, &cred); err != nil || cred.ID != fx.CredentialID || cred.Response.Signature == "" {
		t.Errorf("credential does not match the fixture (%v)", err)
	}
}

func writeGoFixture(t *testing.T) {
	t.Helper()
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	rec, o := h.options(h.aliceS)
	if rec.Code != http.StatusOK {
		t.Fatalf("registration options: %d", rec.Code)
	}
	reg := h.register(h.aliceS, a.Register(t, ceremonyInput{Challenge: o.Challenge, Origin: pkOrigin, RPID: pkRPID}, 2), "Fixture key", pkUA)
	if reg.Code != http.StatusOK {
		t.Fatalf("registration: %d %s", reg.Code, reg.Body.String())
	}
	id := h.lgPasskeyID(a.ID())
	if sc, _ := h.lgPasskeyRow(id); sc != 2 {
		t.Fatalf("sign_count after registration %d, want 2", sc)
	}
	var stored lgGoFile
	if err := h.pool.QueryRow(h.ctx, `SELECT credential_id, public_key FROM passkey WHERE id = $1`, id).Scan(&stored.CredentialID, &stored.PublicKey); err != nil {
		t.Fatal(err)
	}

	lrec, lch := h.lgLoginOptions()
	if lrec.Code != http.StatusOK {
		t.Fatalf("login options: %d", lrec.Code)
	}
	assertion := lgAssert(t, a, lch, 4, h.lgHandle(lgAliceID))
	lrec = h.lgLogin(map[string]any{"credential": assertion, "remember": true, "next": "/"})
	if lrec.Code != http.StatusOK {
		t.Fatalf("login: %d %s", lrec.Code, lrec.Body.String())
	}
	credential, err := json.Marshal(assertion)
	if err != nil {
		t.Fatal(err)
	}
	out, err := json.MarshalIndent(lgGoFile{
		RPID:            pkRPID,
		Origin:          pkOrigin,
		CredentialID:    stored.CredentialID,
		PublicKey:       stored.PublicKey,
		SignCountBefore: 2,
		Challenge:       lch,
		Credential:      credential,
	}, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(lgGoFixture, append(out, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}
