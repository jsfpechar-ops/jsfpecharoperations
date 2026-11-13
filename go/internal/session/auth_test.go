package session

import (
	"bytes"
	"compress/zlib"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// authGolden is testdata/auth.json, written by App/scripts/auth_golden.py.
type authGolden struct {
	Secret   string `json:"secret"`
	Now      int64  `json:"now"`
	Sessions []struct {
		Name string `json:"name"`
		Args struct {
			UserID         int64   `json:"user_id"`
			SessionVersion int64   `json:"session_version"`
			Workspace      int64   `json:"workspace_user_id"`
			Remember       bool    `json:"remember"`
			Started        *int64  `json:"impersonation_started_at"`
			Revealed       []int64 `json:"revealed_guest_ids"`
			IssuedAt       *int64  `json:"issued_at"`
		} `json:"args"`
		Token string `json:"token"`
	} `json:"sessions"`
	Reads []struct {
		Name  string `json:"name"`
		Token string `json:"token"`
		At    int64  `json:"at"`
		OK    bool   `json:"ok"`
	} `json:"reads"`
	Refreshes []struct {
		Name    string          `json:"name"`
		Payload json.RawMessage `json:"payload"`
		Cookie  string          `json:"cookie"`
	} `json:"refreshes"`
	Cookies map[string]string `json:"cookies"`
	Pending []struct {
		UID   int64  `json:"uid"`
		RM    bool   `json:"rm"`
		Next  string `json:"next"`
		Token string `json:"token"`
	} `json:"pending"`
	TOTP []struct {
		Secret string            `json:"secret"`
		Codes  map[string]string `json:"codes"`
	} `json:"totp"`
	URIs []struct {
		Secret   string `json:"secret"`
		Username string `json:"username"`
		URI      string `json:"uri"`
	} `json:"uris"`
	Recovery struct {
		Codes []string `json:"codes"`
		JSON  string   `json:"json"`
	} `json:"recovery"`
	Usernames []struct {
		In    string `json:"in"`
		Norm  string `json:"norm"`
		Valid bool   `json:"valid"`
	} `json:"usernames"`
	NewUsernames []struct {
		Email    string `json:"email"`
		Username string `json:"username"`
	} `json:"new_usernames"`
	Whitespace []rune `json:"whitespace"`
	JSONString struct {
		In  string `json:"in"`
		Out string `json:"out"`
	} `json:"json_string"`
	UTCNow    string `json:"utcnow"`
	Forbidden struct {
		Status  int        `json:"status"`
		Body    string     `json:"body"`
		Headers [][]string `json:"headers"`
	} `json:"forbidden"`
}

func loadAuthGolden(t *testing.T) authGolden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "auth.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g authGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Sessions) == 0 || len(g.TOTP) == 0 {
		t.Fatal("no golden cases")
	}
	return g
}

// tokenJSON is the JSON and the timestamp inside an itsdangerous token,
// decompressed when the payload starts with ".".
func tokenJSON(t *testing.T, token string) ([]byte, string) {
	t.Helper()
	parts := strings.Split(token, ".")
	if len(parts) < 3 {
		t.Fatalf("not a token: %q", token)
	}
	ts := parts[len(parts)-2]
	value := strings.Join(parts[:len(parts)-2], ".")
	compressed := strings.HasPrefix(value, ".")
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		t.Fatal(err)
	}
	if compressed {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			t.Fatal(err)
		}
		if raw, err = io.ReadAll(r); err != nil {
			t.Fatal(err)
		}
	}
	return raw, ts
}

// sameToken checks a Go token against Python's: identical JSON bytes and
// timestamp, and both verify under the same secret and salt. The bytes of the
// token itself may differ only where zlib (CPython vs Go) compresses
// differently, or one side compresses and the other does not.
func sameToken(t *testing.T, name, secret, salt, got, py string, now time.Time) {
	t.Helper()
	gj, gts := tokenJSON(t, got)
	pj, pts := tokenJSON(t, py)
	if !bytes.Equal(gj, pj) || gts != pts {
		t.Errorf("%s: payload differs:\n go     %s (%s)\n python %s (%s)", name, gj, gts, pj, pts)
	}
	s := secure.NewTimedSerializer(secret, salt)
	var a, b json.RawMessage
	if s.Loads(got, secure.NoMaxAge, now, &a) != nil || s.Loads(py, secure.NoMaxAge, now, &b) != nil {
		t.Errorf("%s: a token does not verify", name)
	}
}

func TestAuthGoldenSessions(t *testing.T) {
	g := loadAuthGolden(t)
	now := time.Unix(g.Now, 0)
	for _, c := range g.Sessions {
		a := c.Args
		got, err := IssueSession(g.Secret, a.UserID, a.SessionVersion, IssueOptions{
			Workspace: a.Workspace, Remember: a.Remember, ImpersonationStartedAt: a.Started,
			RevealedGuestIDs: a.Revealed, IssuedAt: a.IssuedAt}, now)
		if err != nil {
			t.Fatal(err)
		}
		sameToken(t, c.Name, g.Secret, salt, got, c.Token, now)
	}
}

func TestAuthGoldenReads(t *testing.T) {
	g := loadAuthGolden(t)
	for _, c := range g.Reads {
		_, ok := ReadPayload(g.Secret, c.Token, time.Unix(c.At, 0))
		if ok != c.OK {
			t.Errorf("%s: ReadPayload ok=%v, Python %v", c.Name, ok, c.OK)
		}
	}
	if _, ok := ReadPayload(g.Secret, "", time.Unix(g.Now, 0)); ok {
		t.Error("empty token accepted")
	}
}

// cookieOf parses one Set-Cookie value (Python's or Go's).
func cookieOf(t *testing.T, line string) *http.Cookie {
	t.Helper()
	c, err := http.ParseSetCookie(line)
	if err != nil {
		t.Fatalf("parse %q: %v", line, err)
	}
	return c
}

// sameCookie compares what a browser acts on: name, value, path, lifetime, flags.
func sameCookie(t *testing.T, name string, py, got *http.Cookie) {
	t.Helper()
	pyValue := py.Value
	if pyValue == `""` {
		pyValue = ""
	}
	if py.Name != got.Name || pyValue != got.Value || py.Path != got.Path || py.MaxAge != got.MaxAge ||
		py.HttpOnly != got.HttpOnly || py.Secure != got.Secure || py.SameSite != got.SameSite {
		t.Errorf("%s: cookie differs:\n python %+v\n go     %+v", name, py, got)
	}
}

func TestAuthGoldenCookies(t *testing.T) {
	g := loadAuthGolden(t)
	now := time.Unix(g.Now, 0)
	device, err := DeviceToken(g.Secret, 7, 3, "DEVICEID0123456789abcd", now)
	if err != nil {
		t.Fatal(err)
	}
	sameToken(t, "device", g.Secret, deviceSalt, device, cookieOf(t, g.Cookies["device_plain"]).Value, now)
	for _, secure := range []bool{false, true} {
		s := "plain"
		if secure {
			s = "secure"
		}
		checks := map[string]*http.Cookie{
			"session_" + s:          SessionCookie("TOKEN", false, secure),
			"session_remember_" + s: SessionCookie("TOKEN", true, secure),
			"clear_" + s:            ClearSessionCookie(secure),
			"device_" + s:           DeviceCookie(cookieOf(t, g.Cookies["device_plain"]).Value, secure),
		}
		for name, c := range checks {
			sameCookie(t, name, cookieOf(t, g.Cookies[name]), cookieOf(t, c.String()))
		}
	}
}

func TestAuthGoldenRefresh(t *testing.T) {
	g := loadAuthGolden(t)
	now := time.Unix(g.Now, 0)
	for _, c := range g.Refreshes {
		payload, ok := decodePayload(c.Payload)
		if !ok {
			t.Fatal(c.Name)
		}
		got, err := RefreshSession(g.Secret, payload, http.Header{}, true, now)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		if c.Cookie == "" {
			if got != nil {
				t.Errorf("%s: Go refreshed, Python did not", c.Name)
			}
			continue
		}
		if got == nil {
			t.Errorf("%s: Python refreshed, Go did not", c.Name)
			continue
		}
		py := cookieOf(t, c.Cookie)
		sameToken(t, c.Name, g.Secret, salt, got.Value, py.Value, now)
		got.Value = py.Value
		sameCookie(t, c.Name, py, got)
	}
	// A cookie already set in this response wins (login, logout, 2FA).
	payload, _ := decodePayload(g.Refreshes[2].Payload)
	h := http.Header{}
	h.Add("Set-Cookie", "ubyhost_session=x; Path=/")
	if got, _ := RefreshSession(g.Secret, payload, h, true, now); got != nil {
		t.Error("refreshed over a cookie set in the same response")
	}
}

func TestAuthGoldenTwoFactorPending(t *testing.T) {
	g := loadAuthGolden(t)
	now := time.Unix(g.Now, 0)
	for i, c := range g.Pending {
		got, err := IssueTwoFactorPending(g.Secret, c.UID, c.RM, c.Next, now)
		if err != nil {
			t.Fatal(err)
		}
		sameToken(t, c.Next, g.Secret, twoFactorSalt, got, c.Token, now)
		p, ok := ReadTwoFactorPending(g.Secret, c.Token, now.Add(TwoFactorPendingMaxAge*time.Second))
		if !ok || p["uid"] != c.UID || p["rm"] != c.RM || p["next"] != c.Next {
			t.Errorf("case %d: read back %v %v", i, p, ok)
		}
		if _, ok := ReadTwoFactorPending(g.Secret, c.Token, now.Add((TwoFactorPendingMaxAge+1)*time.Second)); ok {
			t.Errorf("case %d: accepted after 10 minutes", i)
		}
	}
	zero, _ := IssueTwoFactorPending(g.Secret, 0, false, "/", now)
	if _, ok := ReadTwoFactorPending(g.Secret, zero, now); ok {
		t.Error("uid 0 accepted")
	}
}

func TestAuthGoldenTOTP(t *testing.T) {
	g := loadAuthGolden(t)
	for _, c := range g.TOTP {
		for step, want := range c.Codes {
			n, _ := strconv.ParseInt(step, 10, 64)
			got, err := totpAt(c.Secret, n)
			if err != nil || got != want {
				t.Errorf("%s step %s: %q, Python %q (%v)", c.Secret, step, got, want, err)
			}
		}
	}
	for _, c := range g.URIs {
		if got := TOTPURI(c.Secret, c.Username); got != c.URI {
			t.Errorf("uri:\n go     %s\n python %s", got, c.URI)
		}
	}
	if got := recoveryHashesJSON(g.Secret, g.Recovery.Codes); got != g.Recovery.JSON {
		t.Errorf("recovery json:\n go     %s\n python %s", got, g.Recovery.JSON)
	}
	if !regexp.MustCompile(`^[A-Z2-7]{32}$`).MatchString(NewTOTPSecret()) {
		t.Error("TOTP secret format")
	}
	codes := NewRecoveryCodes(8)
	if len(codes) != 8 {
		t.Fatal("recovery code count")
	}
	for _, c := range codes {
		if !regexp.MustCompile(`^[0-9A-F]{4}-[0-9A-F]{4}$`).MatchString(c) {
			t.Errorf("recovery code format %q", c)
		}
	}
	if len(NewDeviceID()) != 22 {
		t.Error("device id is not token_urlsafe(16)")
	}
}

func TestAuthGoldenUsernamesAndText(t *testing.T) {
	g := loadAuthGolden(t)
	for _, c := range g.Usernames {
		if NormaliseUsername(c.In) != c.Norm || UsernameIsValid(c.In) != c.Valid {
			t.Errorf("%q: %q %v, Python %q %v", c.In, NormaliseUsername(c.In), UsernameIsValid(c.In), c.Norm, c.Valid)
		}
	}
	for _, c := range g.NewUsernames {
		// Python ran with token_hex patched to "abcd" and no name taken.
		want := c.Username
		if got := usernameBase(c.Email) + "-abcd"; got != want {
			t.Errorf("%q: %q, Python %q", c.Email, got, want)
		}
	}
	py := map[rune]bool{}
	for _, r := range g.Whitespace {
		py[r] = true
	}
	for r := rune(0); r < 0x110000; r++ {
		if pySpace(r) != py[r] {
			t.Errorf("whitespace U+%04X: go %v python %v", r, pySpace(r), py[r])
		}
	}
	if got := pyString(g.JSONString.In); got != g.JSONString.Out {
		t.Errorf("json string:\n go     %s\n python %s", got, g.JSONString.Out)
	}
	if got := UTCNow(time.Unix(g.Now, 750e6)); got != g.UTCNow {
		t.Errorf("utcnow %q, Python %q", got, g.UTCNow)
	}
}

func TestSessionAgeHelpers(t *testing.T) {
	now := time.Unix(1798761600, 0)
	if SessionMaxAgeFor(nil) != SessionMaxAge || SessionMaxAgeFor(map[string]any{"rm": int64(1)}) != SessionRememberMaxAge {
		t.Error("SessionMaxAgeFor")
	}
	p := map[string]any{"iat": now.Unix() - FreshLoginSeconds}
	if !IsFresh(p, 0, now) || IsFresh(p, 0, now.Add(time.Millisecond)) || IsFresh(p, 599, now) {
		t.Error("IsFresh boundary")
	}
	if IsFresh(map[string]any{"iat": int64(0)}, 0, now) || IsFresh(nil, 0, now) || IssuedAt(map[string]any{"iat": "1"}) != 0 {
		t.Error("IsFresh without iat")
	}
}
