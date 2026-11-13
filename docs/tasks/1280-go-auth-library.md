# 1280: Go auth library: session write side and login primitives

Status: todo
Depends on: none | Base commit: a83df54 | Branch: go-login-accounts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (11 new files, no edits)

## 1. Objective

Port the parts of `App/app/auth.py`, `App/app/login_link.py` and `App/app/rate_limit.py` that login needs into the Go package `go/internal/session` (new files only), plus the admin gate `_require_admin` as `go/internal/session/admingate`. No route is registered and nothing is switched on: this is the library the later Go login, signup and account routes call. Sessions, 2FA and login links stay shared with Python, so Go must read and write exactly what Python does.

## 2. Context

Rules that apply (AGENTS.md, rules.md#secrets, SECURITY.md "Host sessions" / "Login links"):

- Public repo: the test secrets below are fixed test strings, not real keys. Never add a real key.
- No new dependency: `go/go.mod` and `go/go.sum` stay unchanged (TOTP is HMAC-SHA1 from the standard library).
- SQL is Postgres-only through pgx, parameterised; the statements are the ones Python's `db` helpers generate.
- Existing exported functions in `go/internal/session/session.go` (`Sign`, `Verify`, `Load`, `AcceptancePending`) are not changed: `hostweb` and `pushweb` call them.

What the new code reproduces (Python is the truth; every line was checked against the source at the base commit):

| Python | Go |
|---|---|
| `auth.issue_session` (keys uid, sv, iat, rf, rm, as, ast, rv in that order) | `IssueSession(secret, uid, sv, IssueOptions, now)` |
| `auth._session_payload` (30 days sliding, 90 days from iat with rm, 12 h without) | `ReadPayload(secret, token, now)` |
| `session_max_age`, `attach_session`, `clear_session`, `refresh_session_cookie` | `SessionMaxAgeFor`, `SessionCookie`, `ClearSessionCookie`, `RefreshSession` |
| `session_issued_at`, `session_is_fresh`, `end_all_sessions` | `IssuedAt`, `IsFresh`, `EndAllSessions` |
| `issue_two_factor_pending`, `read_two_factor_pending` (salt `ubyhost-2fa-pending`, 10 min) | `IssueTwoFactorPending`, `ReadTwoFactorPending` |
| `new_totp_secret`, `totp_uri`, `recovery_code_hash`, `new_recovery_codes` | `NewTOTPSecret`, `TOTPURI`, `RecoveryCodeHash`, `NewRecoveryCodes` |
| `enable_totp`, `stage_totp`, `reset_totp`, `verify_second_factor` | `EnableTOTP`, `StageTOTP`, `ResetTOTP`, `VerifySecondFactor` |
| `attach_device`, `trusted_device`, `device_cookie_valid` (salt `ubyhost-device`, 30 days) | `NewDeviceID`, `DeviceToken`, `DeviceCookie`, `TrustedDevice`, `DeviceCookieValid` |
| `normalise_username`, `username_is_valid`, `new_username`, `account_by_email`, `account_by_username`, `create_account`, `email_taken`, `set_account_email`, `db.utcnow` | `NormaliseUsername`, `UsernameIsValid`, `NewUsername`, `AccountByEmail`, `AccountByUsername`, `AccountByID`, `CreateAccount`, `EmailTaken`, `SetAccountEmail`, `UTCNow` |
| `login_link.issue`, `peek`, `consume`, `account_for`, `request_blocked`, `record_request`, `consume_blocked`, `record_consume_failure` | `IssueLoginLink`, `PeekLoginLink`, `ConsumeLoginLink`, `AccountForLink`, `LinkRequestBlocked`, `LinkRecordRequest`, `LinkConsumeBlocked`, `LinkRecordConsumeFailure` |
| `rate_limit.blocked`, `record`, `account_2fa_blocked`, `record_account_2fa_failure` | `RateBlocked`, `RateRecord`, `Account2FABlocked`, `RecordAccount2FAFailure` |
| `routes/admin_accounts._require_admin` (require_login, then `Response(flash("auth.error.admins_only"), 403)`) | `admingate.Require(w, r, pool, getenv, at) (*session.Host, error)` |

Format facts the code depends on (all proven by the golden file):

- itsdangerous `_CompactJSON` writes `ensure_ascii=False`: non-ASCII stays UTF-8, only `"`, `\` and controls below U+0020 are escaped (`pyString`).
- `json.dumps(list)` for `recovery_codes_hash` uses `", "` between items (`pyDumpsList`); the compare-and-set on spending a recovery code matches the old text exactly.
- CPython's zlib and Go's compress differently, so a token may differ in bytes (or one side compresses and the other not). The tests compare the decompressed JSON, the timestamp, and that both tokens verify. The signature is then the same function.
- Starlette `Response(text, status_code=403)` sends the UTF-8 text with only `content-length`: no Content-Type. Go sets `Content-Type` to nil so `net/http` does not sniff one.
- `re.sub(r"\s+", "")` and `str.strip()` count U+001C to U+001F as whitespace; Go's `unicode.IsSpace` does not (`pySpace`).
- `pyotp.TOTP.at(step*30)` equals HOTP-SHA1 of the step (the secret padded to a multiple of 8, base32 decoded case-insensitively), 6 digits.

Skipped, with reason: `staging_*`, `ensure_bootstrap_admin` (staging and first-run only, Python keeps them); `accounts_exist` (bootstrap only); permalink and PIN helpers (guest pages, not login); `require_login` and impersonation (already in `hostweb.Login`); `login_link.purge` (retention job); rate-limit scopes other than login-link and 2FA (`login_fail`, PIN).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/session/pyjson.go` | create | Python-compatible JSON, `quote`, whitespace helpers |
| `go/internal/session/issue.go` | create | session issue/read/refresh, cookies, 2FA pending, device cookie |
| `go/internal/session/totp.go` | create | TOTP, recovery codes, enable/stage/reset, `VerifySecondFactor` |
| `go/internal/session/accounts.go` | create | `LoginAccount`, username helpers, account lookups, create, e-mail |
| `go/internal/session/loginlink.go` | create | login_token rows and the login-link / 2FA rate limits |
| `go/internal/session/admingate/admingate.go` | create | `Require`: the admin gate |
| `App/scripts/auth_golden.py` | create | writes `testdata/auth.json` from the Python code |
| `go/internal/session/testdata/auth.json` | create (generated) | output of the golden script, never hand-written |
| `go/internal/session/auth_test.go` | create | golden parity tests (no database) |
| `go/internal/session/auth_db_test.go` | create | Postgres tests; skip without `UBYHOST_TEST_DATABASE_URL` |
| `go/internal/session/admingate/admingate_test.go` | create | i18n texts vs Python, no-cookie redirect |
| `docs/tasks/1280-files-2.md` | exists | part 2 of the file contents (committed with this brief) |
| `docs/tasks/1280-report.md` | create | the report |

No other file may change. Final sha256 of every file:

| Path | sha256 |
|---|---|
| `go/internal/session/pyjson.go` | `fca897b8231ee9b0380e25bc13c0890c71768567d5c628048911b2a882d6b0b4` |
| `go/internal/session/issue.go` | `29ee2e0a7953c6b1c04f0a236feda6abef2bfb052e60c02388df7a022554c413` |
| `go/internal/session/totp.go` | `51e714bc4fbc7f1c542b7d872b597a0ed4e118c4d3415e3f77ffd49614384d53` |
| `go/internal/session/accounts.go` | `e85fbd09826662d94f059630ab0456d81eb6ef997c610ec0b7978d0f04f4eaba` |
| `go/internal/session/loginlink.go` | `9b1d023eee5f1e90c29a0ec44d7984c55457a79fe995d921b329923e85a6293e` |
| `go/internal/session/admingate/admingate.go` | `b4e930b1d1411fae010e4808c0d02b8643288a7d9fa01bf31c26a3f9ae595db2` |
| `App/scripts/auth_golden.py` | `4f7db9b82ebe54f43e71468855cf768e26a09a2abc315282fc701e7b36c99b38` |
| `go/internal/session/auth_test.go` | `360fb74956ea3d6bfa2afe5e81f8a49f1bd0c67c06f30050abf5ea136a5aef50` |
| `go/internal/session/auth_db_test.go` | `00b84397904a0c2f09a7107f4c9a9806a163110b4db3cdfd9268f98f5ebaf568` |
| `go/internal/session/admingate/admingate_test.go` | `325b77689d16af45f9a4820409163894af852d30651ba0f414a66b19d00c1f83` |
| `go/internal/session/testdata/auth.json` | `35e54895f16ba0a1084d6c704899b897e6a617b58506689ae11706b6be68defc` |

## 4. Steps

1. Create the six code files (`pyjson.go`, `issue.go`, `totp.go`, `accounts.go` from the Appendix below; `loginlink.go`, `admingate/admingate.go` from [1280-files-2.md](1280-files-2.md)) with the exact contents given. Then run from `go/`: `export PATH=$PATH:/usr/local/go/bin && gofmt -l internal/session/ && go vet ./internal/session/... 2>&1 | tail -30`. Expected: no output. Commit `1280 step 1`.
2. Create `App/scripts/auth_golden.py` from 1280-files-2.md. From `App/` run `.venv/bin/python scripts/auth_golden.py 2>&1 | tail -5`. Expected: `wrote go/internal/session/testdata/auth.json`. (No `.venv`: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3` first.) Then `sha256sum ../go/internal/session/testdata/auth.json` must print the hash in §3; run the script a second time, the hash must not change. Commit `1280 step 2` (both files).
3. Create the three test files from 1280-files-2.md. Run the §6 commands. Commit `1280 step 3`.
4. Run `sha256sum` over every §3 file except the report and compare with the table. Write the report. Commit `1280 report`.

## 5. Do not touch

`go/internal/session/session.go`, `session_test.go`, `testdata/tokens.json`, `go/internal/hostweb/`, `go/internal/jobs/`, `go/cmd/`, `go/go.mod`, `go/go.sum`, every file under `App/app/`, `App/tests/`, `docs/context/`, `docs/ENVIRONMENT.md`. No route, no `UBYHOST_GO_PATHS` change. Hard rules 3 (no secrets) and 4 (no dependency) apply.

## 6. Commands

From `go/` (with `export PATH=$PATH:/usr/local/go/bin`):

```bash
gofmt -l internal/session/ 2>&1 | tail -30
go vet ./internal/session/... 2>&1 | tail -30
go test ./internal/session/... -count=1 2>&1 | tail -30
```

Expected: no output from gofmt and vet; `ok` for `internal/session` and `internal/session/admingate`.

Database tests (run them when a Postgres is reachable; CI sets the variable): `UBYHOST_TEST_DATABASE_URL='postgres://USER@HOST:PORT/postgres?sslmode=disable' go test ./internal/session/... -count=1 -run Database -v 2>&1 | grep -E '^(---|ok|FAIL)' | tail -30`. Expected: PASS for `TestAccountsDatabase`, `TestLoginLinkDatabase`, `TestSecondFactorDatabase`, `TestDeviceDatabase`, `TestLoadDatabase`. Without the variable they print SKIP; say so in the report.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] `git diff --stat a83df54` lists only the §3 files (plus this brief).
- [ ] Every sha256 matches §3.
- [ ] gofmt and vet print nothing; `go test ./internal/session/...` is `ok` for both packages.
- [ ] Golden tests pass: `TestAuthGoldenSessions`, `Reads`, `Cookies`, `Refresh`, `TwoFactorPending`, `TOTP`, `UsernamesAndText`.
- [ ] The report says whether the database tests ran or skipped.
- [ ] `go/go.mod` and `go/go.sum` unchanged.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- a sha256 differs and you cannot see why after one comparison;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1280-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/session/totp.go` (`VerifySecondFactor`: step window, replay guard, recovery-code compare-and-set, decrypt error paths).
- `go/internal/session/issue.go` (`ReadPayload` limits, `RefreshSession`, cookie attributes).
- `go/internal/session/loginlink.go` (single-use consume, retiring older links, expiry strings).
- `go/internal/session/accounts.go` (`SetAccountEmail` session bump and link retirement).
- `go/internal/session/admingate/admingate.go` (403 body and headers; checks the real account, so an impersonating admin passes, as in Python).

Known differences from Python, accepted (none reachable in normal use):

- The existing `session.Verify` (used by `session.Load`, so by every Go host route today) still accepts a remember-me cookie up to 400 days and has no 90-day cap. Python stopped at 30 days sliding and 90 days absolute in 0911. `ReadPayload` is correct. Switching `Load` to it is a follow-up brief, because `hostweb` and `pushweb` depend on it.
- `App/scripts/session_golden.py` (0672) no longer matches `issue_session`, which now adds `rf`. Its committed `tokens.json` still passes; rerunning the script would fail its assert.
- Where Python raises (HTTP 500), Go answers false or an error: a non-integer uid/sv in a device cookie, a non-integer `rf`/`iat` on refresh, a TOTP secret that is not base32.
- `pyotp.at()` goes through local time (`fromtimestamp` then `mktime`); on a non-UTC server, during the DST change hour, Python can compute a different step. Go uses the step directly. Production runs in UTC.
- `ClearSessionCookie` writes `Expires=1970` and an empty value, where Starlette writes `expires=<now>` and `""`. Browsers treat both as a delete (Max-Age=0 on both).

## Owner steps

None for this brief: it adds a library, and nothing is switched on. Merge as usual when CI is green.


## Appendix: file contents

Each block is the whole file. Copy it exactly (tabs in Go files are real tabs; `gofmt -l` must print nothing). The fence is `~~~~` and is not part of the file. Each file ends with one newline after its last line.

Part 1 (this file): `go/internal/session/pyjson.go`, `go/internal/session/issue.go`, `go/internal/session/totp.go`, `go/internal/session/accounts.go`. Part 2 is [1280-files-2.md](1280-files-2.md): `go/internal/session/loginlink.go`, `go/internal/session/admingate/admingate.go`, `App/scripts/auth_golden.py`, `go/internal/session/auth_test.go`, `go/internal/session/auth_db_test.go`, `go/internal/session/admingate/admingate_test.go`.

### go/internal/session/pyjson.go

sha256 `fca897b8231ee9b0380e25bc13c0890c71768567d5c628048911b2a882d6b0b4`

~~~~
package session

import (
	"fmt"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// pyField is one key of a payload written in a fixed (Python dict) order.
type pyField struct {
	key   string
	value any
}

// pyCompact is json.dumps(fields, separators=(",", ":")), the itsdangerous
// _CompactJSON encoding, for the value types auth payloads hold.
func pyCompact(fields []pyField) string {
	var b strings.Builder
	b.WriteByte('{')
	for i, f := range fields {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(pyString(f.key))
		b.WriteByte(':')
		b.WriteString(pyValue(f.value, ","))
	}
	b.WriteByte('}')
	return b.String()
}

// pyValue encodes one value; sep is the list separator ("," compact, ", " default).
func pyValue(v any, sep string) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case bool:
		if x {
			return "true"
		}
		return "false"
	case int64:
		return strconv.FormatInt(x, 10)
	case string:
		return pyString(x)
	case []int64:
		parts := make([]string, len(x))
		for i, n := range x {
			parts[i] = strconv.FormatInt(n, 10)
		}
		return "[" + strings.Join(parts, sep) + "]"
	case []string:
		parts := make([]string, len(x))
		for i, s := range x {
			parts[i] = pyString(s)
		}
		return "[" + strings.Join(parts, sep) + "]"
	}
	panic(fmt.Sprintf("pyValue: unsupported %T", v))
}

// pyDumpsList is json.dumps(list_of_str) with the default ", " separator.
func pyDumpsList(items []string) string {
	return pyValue(items, ", ")
}

// pyString is json.dumps(s, ensure_ascii=False), as itsdangerous's
// _CompactJSON writes it: only '"', '\\' and control characters below U+0020
// are escaped (\uXXXX in lower-case hex); everything else stays UTF-8.
func pyString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(&b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

// pyQuote is urllib.parse.quote(s, safe=safe): UTF-8 bytes, letters, digits
// and "_.-~" plus safe stay, everything else is %XX in upper-case hex.
func pyQuote(s, safe string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < utf8.RuneSelf && (c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' ||
			strings.IndexByte("_.-~", c) >= 0 || strings.IndexByte(safe, c) >= 0) {
			b.WriteByte(c)
			continue
		}
		fmt.Fprintf(&b, "%%%02X", c)
	}
	return b.String()
}

// pySpace is str.isspace(): Go's unicode.IsSpace plus the ASCII separators
// U+001C to U+001F, which Python also counts as whitespace.
func pySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// pyStrip is str.strip() with no argument.
func pyStrip(s string) string {
	return strings.TrimFunc(s, pySpace)
}

// pyRemoveSpace is re.sub(r"\s+", "", s) on a str.
func pyRemoveSpace(s string) string {
	return strings.Map(func(r rune) rune {
		if pySpace(r) {
			return -1
		}
		return r
	}, s)
}

// isASCII is str.isascii().
func isASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= utf8.RuneSelf {
			return false
		}
	}
	return true
}
~~~~

### go/internal/session/issue.go

sha256 `29ee2e0a7953c6b1c04f0a236feda6abef2bfb052e60c02388df7a022554c413`

~~~~
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
// Verify keeps its older limits for the existing callers.
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
~~~~

### go/internal/session/totp.go

sha256 `51e714bc4fbc7f1c542b7d872b597a0ed4e118c4d3415e3f77ffd49614384d53`

~~~~
package session

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha1"
	"encoding/base32"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Authenticator-app second factor, ported from App/app/auth.py (pyotp 2.10
// defaults: SHA-1, 6 digits, 30-second steps).
const (
	totpInterval = 30
	totpIssuer   = "UbyHost"
	base32Chars  = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
)

var errBadPayload = errors.New("session: payload value is not an integer")

// NewTOTPSecret is pyotp.random_base32(): 32 characters from the base32 alphabet.
func NewTOTPSecret() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	for i := range b {
		b[i] = base32Chars[b[i]&31]
	}
	return string(b)
}

// TOTPURI is pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="UbyHost").
func TOTPURI(secret, username string) string {
	return "otpauth://totp/" + pyQuote(totpIssuer, "/") + ":" + pyQuote(username, "/") +
		"?secret=" + pyQuote(secret, "") + "&issuer=" + pyQuote(totpIssuer, "")
}

// totpAt is pyotp.TOTP(secret).at(step * 30): HOTP-SHA1 of the step counter.
// The secret is padded to a multiple of 8 and decoded case-insensitively.
func totpAt(secret string, step int64) (string, error) {
	if step < 0 {
		return "", errors.New("session: negative TOTP step")
	}
	if pad := len(secret) % 8; pad != 0 {
		secret += strings.Repeat("=", 8-pad)
	}
	key, err := base32.StdEncoding.DecodeString(strings.ToUpper(secret))
	if err != nil {
		return "", err
	}
	var msg [8]byte
	binary.BigEndian.PutUint64(msg[:], uint64(step))
	mac := hmac.New(sha1.New, key)
	mac.Write(msg[:])
	sum := mac.Sum(nil)
	off := sum[len(sum)-1] & 0xf
	code := binary.BigEndian.Uint32(sum[off:off+4]) & 0x7fffffff
	return fmt.Sprintf("%06d", code%1000000), nil
}

// RecoveryCodeHash is auth.recovery_code_hash.
func RecoveryCodeHash(secret, code string) string {
	return secure.RecoveryCodeHash(secret, code)
}

// NewRecoveryCodes is new_recovery_codes(count): "XXXX-XXXX", upper-case hex.
func NewRecoveryCodes(count int) []string {
	codes := make([]string, count)
	for i := range codes {
		b := make([]byte, 4)
		if _, err := rand.Read(b); err != nil {
			panic(err)
		}
		codes[i] = strings.ToUpper(hex.EncodeToString(b[:2]) + "-" + hex.EncodeToString(b[2:]))
	}
	return codes
}

// recoveryHashesJSON is json.dumps([recovery_code_hash(c) for c in codes]).
func recoveryHashesJSON(secret string, codes []string) string {
	hashes := make([]string, len(codes))
	for i, c := range codes {
		hashes[i] = RecoveryCodeHash(secret, c)
	}
	return pyDumpsList(hashes)
}

// encryptSecret is db.encrypt_secret: "" stays "", else Fernet with the first data key.
func encryptSecret(getenv func(string) string, plain string) (string, error) {
	if plain == "" {
		return "", nil
	}
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return "", err
	}
	return keys.EncryptString(plain)
}

// EnableTOTP is enable_totp.
func EnableTOTP(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, userID int64, totpSecret string, codes []string) error {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return err
	}
	enc, err := encryptSecret(getenv, totpSecret)
	if err != nil {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE user_account SET totp_secret_enc = $1, totp_enabled = 1, `+
		`recovery_codes_hash = $2, totp_last_step = NULL, `+
		`session_version = session_version + 1 WHERE id = $3`,
		enc, recoveryHashesJSON(secret, codes), userID)
	return err
}

// StageTOTP is stage_totp.
func StageTOTP(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, userID int64, totpSecret string) error {
	enc, err := encryptSecret(getenv, totpSecret)
	if err != nil {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE user_account SET totp_secret_enc = $1, totp_enabled = 0, `+
		`totp_last_step = NULL WHERE id = $2`, enc, userID)
	return err
}

// ResetTOTP is reset_totp.
func ResetTOTP(ctx context.Context, db *pgxpool.Pool, userID int64) error {
	_, err := db.Exec(ctx, `UPDATE user_account SET totp_secret_enc = NULL, totp_enabled = 0, `+
		`recovery_codes_hash = NULL, totp_last_step = NULL, `+
		`session_version = session_version + 1 WHERE id = $1`, userID)
	return err
}

// VerifySecondFactor is verify_second_factor: a TOTP code for the step before,
// at or after now (each step accepted once, via totp_last_step), else a
// recovery code, spent by compare-and-set on recovery_codes_hash.
func VerifySecondFactor(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, account *LoginAccount, code string, now time.Time) (bool, error) {
	normalized := pyRemoveSpace(code)
	if !isASCII(normalized) {
		return false, nil
	}
	// db.decrypt_secret: a missing data key raises, which Python turns into
	// False; a token no key opens reads as "" and falls through to recovery.
	totpSecret := ""
	if account.TOTPSecretEnc != nil && *account.TOTPSecretEnc != "" {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return false, nil
		}
		if plain, err := keys.Decrypt(*account.TOTPSecretEnc, 0, now); err == nil {
			totpSecret = string(plain)
		}
	}
	if totpSecret != "" && normalized != "" {
		current := now.Unix() / totpInterval
		for _, step := range []int64{current - 1, current, current + 1} {
			want, err := totpAt(totpSecret, step)
			if err != nil {
				return false, err
			}
			if hmac.Equal([]byte(want), []byte(normalized)) {
				tag, err := db.Exec(ctx, `UPDATE user_account SET totp_last_step = $1 WHERE id = $2 `+
					`AND (totp_last_step IS NULL OR totp_last_step < $3)`, step, account.ID, step)
				if err != nil {
					return false, err
				}
				return tag.RowsAffected() == 1, nil
			}
		}
	}
	sessionSecret, err := secure.LoadSecret(getenv)
	if err != nil {
		return false, err
	}
	candidate := RecoveryCodeHash(sessionSecret, normalized)
	raw := ""
	if account.RecoveryCodesHash != nil {
		raw = *account.RecoveryCodesHash
	}
	if raw == "" {
		raw = "[]"
	}
	var stored []any
	if err := json.Unmarshal([]byte(raw), &stored); err != nil {
		stored = nil
	}
	for i, s := range stored {
		h, ok := s.(string)
		if !ok || !hmac.Equal([]byte(candidate), []byte(h)) {
			continue
		}
		rest := make([]string, 0, len(stored)-1)
		for j, o := range stored {
			if j != i {
				str, _ := o.(string)
				rest = append(rest, str)
			}
		}
		tag, err := db.Exec(ctx, `UPDATE user_account SET recovery_codes_hash = $1 WHERE id = $2 `+
			`AND recovery_codes_hash IS NOT DISTINCT FROM $3`, pyDumpsList(rest), account.ID, account.RecoveryCodesHash)
		if err != nil {
			return false, err
		}
		return tag.RowsAffected() == 1, nil
	}
	return false, nil
}
~~~~

### go/internal/session/accounts.go

sha256 `e85fbd09826662d94f059630ab0456d81eb6ef997c610ec0b7978d0f04f4eaba`

~~~~
package session

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Account helpers used by login, ported from App/app/auth.py (brief 1280).

// Errors of create_account; the text is the Python ValueError message.
var (
	ErrEmailInvalid = errors.New("users.email.error.invalid")
	ErrUnknownRole  = errors.New("Unknown account role.")
	ErrUsername     = errors.New("auth.error.username")
)

var usernameRE = regexp.MustCompile(`^[a-z0-9][a-z0-9._-]{2,31}$`)

// usernameEq is db.username_eq() on Postgres: ASCII-only case folding.
const usernameEq = `translate(username, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') ` +
	`= translate($1, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')`

// LoginAccount is the user_account columns login reads (SELECT * in Python).
// Nullable columns are pointers so NULL and "" stay apart.
type LoginAccount struct {
	ID                int64
	Username          string
	DisplayName       *string
	Email             *string
	Role              string
	Active            int64
	SessionVersion    int64
	TOTPEnabled       int64
	TOTPSecretEnc     *string
	RecoveryCodesHash *string
	TOTPLastStep      *int64
	EmailVerifiedAt   *string
	LastLoginAt       *string
	CreatedAt         string
}

const accountColumns = `id, username, display_name, email, role, active, session_version, totp_enabled, ` +
	`totp_secret_enc, recovery_codes_hash, totp_last_step, email_verified_at, last_login_at, created_at`

// accountWhere loads the first user_account row matching where (trusted SQL).
func accountWhere(ctx context.Context, db *pgxpool.Pool, where string, args ...any) (*LoginAccount, error) {
	var a LoginAccount
	err := db.QueryRow(ctx, `SELECT `+accountColumns+` FROM user_account WHERE `+where, args...).Scan(
		&a.ID, &a.Username, &a.DisplayName, &a.Email, &a.Role, &a.Active, &a.SessionVersion, &a.TOTPEnabled,
		&a.TOTPSecretEnc, &a.RecoveryCodesHash, &a.TOTPLastStep, &a.EmailVerifiedAt, &a.LastLoginAt, &a.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// AccountByID is SELECT * FROM user_account WHERE id = ? AND active = 1.
func AccountByID(ctx context.Context, db *pgxpool.Pool, id int64) (*LoginAccount, error) {
	return accountWhere(ctx, db, `id = $1 AND active = 1`, id)
}

// NormaliseUsername is normalise_username: strip, lower-case.
func NormaliseUsername(value string) string {
	return strings.ToLower(pyStrip(value))
}

// UsernameIsValid is username_is_valid.
func UsernameIsValid(value string) bool {
	return usernameRE.MatchString(NormaliseUsername(value))
}

// AccountByEmail is account_by_email: the active account with this exact
// login e-mail, or nil.
func AccountByEmail(ctx context.Context, db *pgxpool.Pool, email string) (*LoginAccount, error) {
	if email == "" {
		return nil, nil
	}
	return accountWhere(ctx, db, `email = $1 AND active = 1`, email)
}

// AccountByUsername is account_by_username (ASCII case-insensitive).
func AccountByUsername(ctx context.Context, db *pgxpool.Pool, username string) (*LoginAccount, error) {
	name := NormaliseUsername(username)
	if name == "" {
		return nil, nil
	}
	return accountWhere(ctx, db, usernameEq+` AND active = 1`, name)
}

var (
	usernameStrip   = regexp.MustCompile(`[^a-z0-9._-]`)
	usernameLeading = regexp.MustCompile(`^[^a-z0-9]+`)
)

func tokenHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}

// usernameBase is the handle stem new_username derives from the e-mail.
func usernameBase(email string) string {
	local := strings.ToLower(strings.SplitN(email, "@", 2)[0])
	local = usernameStrip.ReplaceAllString(local, "")
	base := usernameLeading.ReplaceAllString(local, "")
	if len(base) > 20 {
		base = base[:20]
	}
	if base == "" {
		base = "host"
	}
	return base
}

// NewUsername is new_username: "<stem>-<4 hex>", unused, else "host-<12 hex>".
func NewUsername(ctx context.Context, db *pgxpool.Pool, email string) (string, error) {
	base := usernameBase(email)
	for range 20 {
		candidate := base + "-" + tokenHex(2)
		if !UsernameIsValid(candidate) {
			continue
		}
		var id int64
		err := db.QueryRow(ctx, `SELECT id FROM user_account WHERE `+usernameEq, candidate).Scan(&id)
		if errors.Is(err, pgx.ErrNoRows) {
			return candidate, nil
		}
		if err != nil {
			return "", err
		}
	}
	return "host-" + tokenHex(6), nil
}

// UTCNow is db.utcnow(): ISO seconds with "+00:00".
func UTCNow(now time.Time) string {
	return now.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// CreateAccount is create_account; email must already be normalised.
func CreateAccount(ctx context.Context, db *pgxpool.Pool, email, displayName, role, username string, now time.Time) (int64, error) {
	email = strings.ToLower(pyStrip(email))
	if email == "" || !strings.Contains(email, "@") {
		return 0, ErrEmailInvalid
	}
	if role != "admin" && role != "host" {
		return 0, ErrUnknownRole
	}
	username = NormaliseUsername(username)
	if username == "" {
		var err error
		if username, err = NewUsername(ctx, db, email); err != nil {
			return 0, err
		}
	}
	if !UsernameIsValid(username) {
		return 0, ErrUsername
	}
	var id int64
	err := db.QueryRow(ctx, `INSERT INTO user_account (username, display_name, email, password_hash, role, `+
		`active, must_change_password, session_version, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) `+
		`RETURNING id`, username, pyStrip(displayName), email, "", role, 1, 0, 1, UTCNow(now)).Scan(&id)
	return id, err
}

// EmailTaken is email_taken: another account (id != exceptUserID) has it.
func EmailTaken(ctx context.Context, db *pgxpool.Pool, email string, exceptUserID int64) (bool, error) {
	var id int64
	err := db.QueryRow(ctx, `SELECT id FROM user_account WHERE email = $1 AND id != $2`, email, exceptUserID).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil, err
}

// SetAccountEmail is set_account_email: new unverified address, a
// session_version bump when an address is replaced, and every unused
// login_token of the account spent.
func SetAccountEmail(ctx context.Context, db *pgxpool.Pool, userID int64, email string, now time.Time) error {
	var current *string
	err := db.QueryRow(ctx, `SELECT email FROM user_account WHERE id = $1`, userID).Scan(&current)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	sql := `UPDATE user_account SET email = $1, email_verified_at = NULL`
	if current != nil && pyStrip(*current) != "" {
		sql += `, session_version = session_version + 1`
	}
	if _, err := db.Exec(ctx, sql+` WHERE id = $2`, email, userID); err != nil {
		return err
	}
	_, err = db.Exec(ctx, `UPDATE login_token SET used_at = $1 WHERE user_account_id = $2 AND used_at IS NULL`,
		UTCNow(now), userID)
	return err
}
~~~~
