# 1281: Go signup library and session lifetime cap

Status: todo
Depends on: 1280 | Base commit: 68ea789 | Branch: go-login-accounts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (12 new files, 3 edits by one diff)

## 1. Objective

Port `App/app/signup.py` (with the mails it queues and the helpers it reaches) into the new Go package `go/internal/signup`, so the later Go sign-up routes and the customer-admin page can call it; no route is registered. Also make `session.Verify`/`session.Load` (used by every live Go host route) enforce Python's 30-day sliding and 90-day absolute session limits, so Go and Python accept exactly the same cookies.

## 2. Context

Rules that apply (AGENTS.md, rules.md#secrets, rules.md#mail): public repo, the test secrets below are fixed test strings; no new dependency (`go/go.mod`, `go/go.sum` unchanged; `time/tzdata` is the standard library); SQL is Postgres through pgx, parameterised, no pool use at construction.

What the new code reproduces (Python is the truth; checked against the source at the base commit):

| Python | Go (`go/internal/signup` unless noted) |
|---|---|
| `enabled`, `clean_click_id`, `clean_gclid`, `clean_utm`, `click_ids`, `clean_user_agent`, `signup_selection.clean` | `Enabled`, `CleanClickID`, `CleanGclid`, `CleanUTM`, `ClickIDs`, `CleanUserAgent`, `CleanSelection` |
| `issue_click`, `read_click` (URLSafeSerializer, salt `ubyhost-signup-click`) | `IssueClick`, `ReadClick` |
| `platform_active`, `click_platforms`, `attribution` | `PlatformActive`, `ClickPlatforms`, `Attribution` |
| `issue_token`, `pending_account` (salt `ubyhost-signup-verify`, 24 h) | `IssueToken`, `PendingAccount` |
| `rate_limited`, `record_attempt` | `RateLimited`, `RecordAttempt` (via `session.RateBlocked`/`RateRecord`) |
| `consent_text`, `consent_text_id`, `has_click`, `consents_for`, `signup_source` | `ConsentText`, `ConsentTextID`, `HasClick`, `ConsentsFor`, `SignupSource` |
| `register` (+ `_store_clicks`, `acceptance.record`, `db.audit`) | `Register(ctx, pool, getenv, RegisterInput, now)` |
| `resend_operator` | `ResendOperator(ctx, pool, userID, actor, getenv, now) (bool, error)` |
| `activate` (+ `billing_trial.activation_dates`, `meta_capi.enqueue`) | `Activate`, `TrialDates` |
| `withdraw_consent` | `WithdrawConsent` |
| `conversion_time`, `export_rows`, `conversions_csv`, `export_conversions` | `ConversionTime`, `ExportRows`, `ConversionsCSV`, `ExportConversions` |
| `db.set_current_actor` (contextvar read by `db.audit`) | `WithAuditActor(ctx, userID, username, impersonating)` |
| `mail_notify.build_signup_verify` / `_exists` / `_admin`, `_signup_footer` | `mail.BuildSignupVerify`, `BuildSignupExists`, `BuildSignupAdmin` (new file `go/internal/mail/auth_signup.go`) |
| `mail_notify.signup_verify` / `signup_exists` / `signup_admin` + `mail.enqueue` | unexported `queueVerify`, `enqueue` in `store.go`: the same `email_outbox` row (kind, idempotency key, owner, subject cut to 200, `payload` = `json.dumps` of text, html, lang and `claim_secret_enc`), nothing while `UBYHOST_MAIL_BACKEND` is not console/ses |

Facts the code depends on (proven by the golden file or the DB tests):

- The mails are rendered in Python (`_shell`, blocks, `host_i18n`), so Go renders them too; the existing private `shell`, `blockHeading`, `blockParagraph`, `blockButton`, `blockLink`, `blockFact`, `esc` of package `mail` are reused; `authShell` only swaps `<html lang="en">` for the mail's language. Strings en/cs/vi are copied from `host_i18n.STRINGS`; the golden compares every byte of subject, text and HTML for 22 mails.
- The outbox `payload` is `json.dumps` with defaults: `", "`/`": "` separators and `ensure_ascii=True` (`pyDumps`). The verify token sits only encrypted in `claim_secret_enc`; the body carries `{{claim_secret}}`.
- Starlette `QueryParams.get` returns the **last** value of a repeated key; `last()` does the same.
- `str.strip()` also strips U+001C..U+001F (`pyStrip`).
- CPython's and Go's zlib differ, so a compressed click value may differ in bytes; the tests compare the decompressed JSON and that both verify.
- Python's `db.audit` fills `actor_user_id`/`impersonator_user_id` from the request's signed-in account. In Go that comes from `ctx` (`WithAuditActor`), so `ResendOperator` keeps the requested signature; the admin route must wrap `ctx` with the admin before calling it.
- Session cap: `auth._session_payload` loads with max_age 30 days, refuses `rm` sessions more than 90 days after `iat` (a missing `iat` counts as 0), and plain sessions after 12 h. 1280's `ReadPayload` does exactly that; `Verify` now returns `ReadPayload`, so `Load` follows. `pythonKeyOrder` gains `rf` (issue_session's order). `App/scripts/session_golden.py` is not touched: its committed `tokens.json` still passes, and the new parity test reuses the `reads` cases of 1280's `auth.json`.

Skipped, with reason: `purge` (retention job), `signup_href`, `public_context`, `consent_label` as a dict (page rendering: route brief), Turnstile (route brief), the `log.exception` text of a failed enqueue.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/signup/signup.go` | create | constants, env readers, cleaners, attribution, selection, source |
| `go/internal/signup/tokens.go` | create | signed click value and verify token |
| `go/internal/signup/texts.go` | create | consent box wording en/cs/vi |
| `go/internal/signup/store.go` | create | insert/update/audit helpers, `WithAuditActor`, outbox `enqueue` |
| `go/internal/signup/register.go` | create | `PendingAccount`, limits, consents, `Register`, `ResendOperator`, `Activate`, `WithdrawConsent` |
| `go/internal/signup/export.go` | create | Google Ads export |
| `go/internal/signup/signup_test.go` | create | golden parity tests (no database) |
| `go/internal/signup/signup_db_test.go` | create | Postgres tests; skip without `UBYHOST_TEST_DATABASE_URL` |
| `go/internal/signup/testdata/signup.json` | create (generated) | output of the golden script, never hand-written |
| `go/internal/mail/auth_signup.go` | create | the three sign-up mails |
| `App/scripts/signup_golden.py` | create | writes `testdata/signup.json` from the Python code |
| `go/internal/session/cap_test.go` | create | `Verify` vs Python reads; `Load` cap on Postgres |
| `go/internal/session/session.go` | edit (diff) | `Verify` = `ReadPayload`; `rf` in key order; old constants gone |
| `go/internal/session/issue.go` | edit (diff) | one comment line |
| `go/internal/session/session_test.go` | edit (diff) | `TestSessionAge` asserted the old 400-day rule |
| `docs/tasks/1281-files-2.md`, `1281-files-3.md` | exist | parts 2 and 3 of the file contents |
| `docs/tasks/1281-report.md` | create | the report |

No other file may change. Final sha256 of every file:

| Path | sha256 |
|---|---|
| `go/internal/signup/export.go` | `f66d44a2852fd349356292af3b3a9a48cbd9bf273923de74ea6fa123f38a0faa` |
| `go/internal/signup/register.go` | `0ba0fdb6f4608e7c6d9f28dd8e85833682cca5ea16a38f92ffd0f5160643bc2d` |
| `go/internal/signup/signup.go` | `73f402aae1791a404ed1ba165a8e6434c65b1a37418552196c59b341d287e9e9` |
| `go/internal/signup/signup_db_test.go` | `008387733649df19b3ce3855a2d57859263c0990727cca9a381ef18c6b76f521` |
| `go/internal/signup/signup_test.go` | `9c1daa6e92c6c52543ddc1e7457cb276183be840ad713aa3f71dc595b14c04a9` |
| `go/internal/signup/store.go` | `09016505a5b214a63a95c73dcc60acd27606409d41d0ad985a4c8bceae3f176b` |
| `go/internal/signup/texts.go` | `94535e4d77dcb863723f00ee8cd9831d98e54f1b1c3516886106d6e329f56f46` |
| `go/internal/signup/tokens.go` | `29f87333a8d8dfb9e614820f932cc50b285e375a265b1f1713a255dc223d288e` |
| `go/internal/signup/testdata/signup.json` | `4cf2a0df1a0b6dd3d9ddf7260aeecc51b7190f56bc18d26a75d6ed7421e39d08` |
| `go/internal/mail/auth_signup.go` | `586757be910e872803ce15bcda7bb1de161e6625002bcd24188594b8fc8e5af8` |
| `go/internal/session/cap_test.go` | `330d4f5a078f5821a657adddd4311299826756dcc005d69412cf7ff455db5f33` |
| `go/internal/session/session.go` | `856471775a637e79c993588606fec7139361e80856fc9a5e63e7b0824828e568` |
| `go/internal/session/issue.go` | `69f8052f050133f7dacf8fb1258aef22856ebe40daa6d8ea1933901f883ae0dd` |
| `go/internal/session/session_test.go` | `9703e60766f5f850a7843fe1436ba94cbe6e52771c9ab13a7deaa846a7c7f8ca` |
| `App/scripts/signup_golden.py` | `c259199648515df410cb5bf53e46377edfbfb49ce41f90fe770b9a6e05ff4411` |

## 4. Steps

1. Create `signup.go`, `tokens.go`, `texts.go` from the Appendix below, `store.go`, `register.go`, `export.go` from [1281-files-2.md](1281-files-2.md), and `go/internal/mail/auth_signup.go` from [1281-files-3.md](1281-files-3.md), with the exact contents given. From `go/`: `export PATH=$PATH:/usr/local/go/bin && gofmt -l internal/signup internal/mail && go vet ./internal/signup/ ./internal/mail/ 2>&1 | tail -30`. Expected: no output. Commit `1281 step 1`.
2. Save the diff in the Appendix ("session diff") as `/tmp/1281-session.diff` and from the repo root run `git apply --check /tmp/1281-session.diff && git apply /tmp/1281-session.diff && git diff --stat 2>&1 | tail -5`. Expected: 3 files changed in `go/internal/session/`. Create `go/internal/session/cap_test.go` from the Appendix. Run `go vet ./internal/session/... 2>&1 | tail -30` from `go/`. Commit `1281 step 2`.
3. Create `App/scripts/signup_golden.py` from 1281-files-2.md. From `App/` run `.venv/bin/python scripts/signup_golden.py 2>&1 | tail -5` (expected `wrote go/internal/signup/testdata/signup.json`; no `.venv`: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3` first). `sha256sum ../go/internal/signup/testdata/signup.json` must print the §3 hash; a second run must not change it. Commit `1281 step 3`.
4. Create `signup_test.go` and `signup_db_test.go` from [1281-files-3.md](1281-files-3.md). Run the §6 commands. Commit `1281 step 4`.
5. `sha256sum` every §3 file except the report and compare with the table. Write the report. Commit `1281 report`.

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/jobs/`, `go/cmd/`, existing files in `go/internal/mail/`, `go/internal/session/` files other than the three in the diff, `testdata/tokens.json`, `testdata/auth.json`, `App/scripts/session_golden.py`, `go/go.mod`, `go/go.sum`, everything under `App/app/`, `App/tests/`, `docs/context/`, `docs/ENVIRONMENT.md`. No route, no `UBYHOST_GO_PATHS` change. Hard rules 2 (privacy: no new field, no outbound request), 3 and 4 apply.

## 6. Commands

From `go/` (with `export PATH=$PATH:/usr/local/go/bin`):

```bash
gofmt -l internal/session internal/signup internal/mail 2>&1 | tail -30
go vet ./internal/session/... ./internal/signup/ ./internal/mail/ 2>&1 | tail -30
go test ./internal/session/... ./internal/signup/ ./internal/mail/ ./internal/hostweb/ ./internal/pushweb/ -count=1 2>&1 | tail -30
```

Expected: no output from gofmt and vet; `ok` for every package.

Database tests (when a Postgres is reachable; CI sets the variable): `UBYHOST_TEST_DATABASE_URL='postgres://USER@HOST:PORT/postgres?sslmode=disable' go test ./internal/signup/ ./internal/session/ -count=1 -run Database -v 2>&1 | grep -E '^(---|ok|FAIL)' | tail -30`. Expected PASS: `TestSignupFlowDatabase`, `TestResendAndLimitsDatabase`, `TestLoadSessionCapDatabase` and the five 1280 database tests. Without the variable they SKIP; say so in the report.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] `git diff --stat 68ea789` lists only the §3 files (plus the three brief files).
- [ ] Every sha256 matches §3.
- [ ] gofmt and vet print nothing; the §6 `go test` line is `ok` for every package.
- [ ] Golden tests pass: `TestGoldenCleaners`, `Clicks`, `Tokens`, `ConsentAndExport`, `Mails` (signup) and `TestVerifyMatchesPythonReads`, `TestSessionAge` (session).
- [ ] The report says whether the database tests ran or skipped.
- [ ] `go/go.mod` and `go/go.sum` unchanged.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found, or `git apply --check` fails;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- a sha256 differs and you cannot see why after one comparison;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1281-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/session/session.go` (`Verify` now refuses remember-me cookies older than 30 days or 90 days past `iat`: hosts with such a cookie must log in again on Go routes, as they already must on Python routes).
- `go/internal/signup/register.go` (`Register` outcomes, `Activate` transaction and race, `WithdrawConsent` compare-and-set, `ResendOperator`).
- `go/internal/signup/store.go` (`enqueue`: payload JSON, claim-secret encryption, swallowed insert error as in Python; `audit` actor from ctx).
- `go/internal/signup/tokens.go` (unsigned itsdangerous serializer, click time window).

Known differences from Python, accepted (none reachable in normal use):

- `normaliseEmail` handles bare addresses only; Python's `parseaddr` also unwraps `Name <a@b>`. Stored account addresses are already bare.
- A signed click whose `t` is not a JSON integer or whose id is not a string is refused; Python would coerce it with `int()`/`str()`. Only the server can sign one.
- Env vars are read at call time through `getenv`, and an empty value counts as unset (Python reads once at import; an empty `UBYHOST_TERMS_VERSION` would store an empty version there).
- Python raises (HTTP 500) where Go returns an error: unknown platform, unparseable stored time, missing data key.
- Found, not fixed (outside this brief): `session.AcceptancePending` defaults all three document versions to 1.7, but Python's defaults are terms 1.7, privacy 1.8, dpa 1.8. Production sets the variables; a follow-up should align the defaults.
- Python's `signup_admin` mail has no owner; Go writes NULL too. `activate` is not atomic with its audit/mail/Meta steps, in both.

## Owner steps

None for this brief: it adds a library and tightens the Go session check to Python's rule. Merge as usual when CI is green.

## Appendix: file contents

Each block is the whole file, fence not included, one newline at the end.

### session diff (save as /tmp/1281-session.diff)

```diff
diff --git a/go/internal/session/issue.go b/go/internal/session/issue.go
index 532eac1..47ac890 100644
--- a/go/internal/session/issue.go
+++ b/go/internal/session/issue.go
@@ -102,7 +102,7 @@ func SessionMaxAgeFor(payload map[string]any) int {
 
 // ReadPayload is auth._session_payload: 30 days at most, a remember-me
 // session ends 90 days after iat, any other one 12 hours after signing.
-// Verify keeps its older limits for the existing callers.
+// Verify, and so Load, use the same rule.
 func ReadPayload(secret, token string, now time.Time) (map[string]any, bool) {
 	if token == "" {
 		return nil, false
diff --git a/go/internal/session/session.go b/go/internal/session/session.go
index 46dbccf..0e1091f 100644
--- a/go/internal/session/session.go
+++ b/go/internal/session/session.go
@@ -24,17 +24,13 @@ const (
 	CookieName = "ubyhost_session"
 	// salt is the itsdangerous salt of _serializer (auth.py lines 55-56).
 	salt = "ubyhost-session"
-	// rememberMaxAge is SESSION_REMEMBER_MAX_AGE (auth.py line 33).
-	rememberMaxAge = 400 * 24 * time.Hour
-	// shortMaxAge is SESSION_MAX_AGE (auth.py line 32), enforced unless "rm" is set.
-	shortMaxAge = 12 * time.Hour
 	// defaultVersion is the default of UBYHOST_*_VERSION (brief 0672, section 2).
 	defaultVersion = "1.7"
 )
 
 // pythonKeyOrder is the insertion order of issue_session (auth.py lines 225-260).
 // Python keeps dict order in its JSON, so Sign writes these keys first.
-var pythonKeyOrder = []string{"uid", "sv", "iat", "rm", "as", "ast", "rv"}
+var pythonKeyOrder = []string{"uid", "sv", "iat", "rf", "rm", "as", "ast", "rv"}
 
 // Account is the user_account row a host session needs.
 type Account struct {
@@ -109,24 +105,11 @@ func Sign(secret string, payload map[string]any, now time.Time) string {
 	return token
 }
 
-// Verify checks token at now as auth._session_payload does (auth.py lines 335-354):
-// 400 days at most, and 12 hours unless the payload has a truthy "rm".
+// Verify checks token at now exactly as auth._session_payload does: it is
+// ReadPayload (30 days sliding; with "rm" 90 days from iat, else 12 hours),
+// so Go routes accept the same cookies as Python (brief 1281).
 func Verify(secret, token string, now time.Time) (map[string]any, bool) {
-	s := secure.NewTimedSerializer(secret, salt)
-	var raw json.RawMessage
-	if err := s.Loads(token, rememberMaxAge, now, &raw); err != nil {
-		return nil, false
-	}
-	payload, ok := decodePayload(raw)
-	if !ok {
-		return nil, false
-	}
-	if !truthy(payload["rm"]) {
-		if err := s.Loads(token, shortMaxAge, now, &raw); err != nil {
-			return nil, false
-		}
-	}
-	return payload, true
+	return ReadPayload(secret, token, now)
 }
 
 // decodePayload decodes a JSON object, with whole numbers as int64 (Python int).
diff --git a/go/internal/session/session_test.go b/go/internal/session/session_test.go
index 3c4f489..c0fb53c 100644
--- a/go/internal/session/session_test.go
+++ b/go/internal/session/session_test.go
@@ -122,12 +122,24 @@ func TestSessionAge(t *testing.T) {
 	if _, ok := Verify(g.Secret, plain, base.Add(12*time.Hour+time.Minute)); ok {
 		t.Error("plain token accepted at 12h01m")
 	}
-	remember := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3), "rm": int64(1)}, base)
-	if _, ok := Verify(g.Secret, remember, base.Add(399*24*time.Hour)); !ok {
-		t.Error("remember token rejected at 399 days")
+	// Brief 1281: 30 days sliding, 90 days from iat, as auth._session_payload.
+	remember := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3), "iat": g.Timestamp, "rm": int64(1)}, base)
+	if _, ok := Verify(g.Secret, remember, base.Add(29*24*time.Hour)); !ok {
+		t.Error("remember token rejected at 29 days")
 	}
-	if _, ok := Verify(g.Secret, remember, base.Add(401*24*time.Hour)); ok {
-		t.Error("remember token accepted at 401 days")
+	if _, ok := Verify(g.Secret, remember, base.Add(31*24*time.Hour)); ok {
+		t.Error("remember token accepted at 31 days")
+	}
+	noIat := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3), "rm": int64(1)}, base)
+	if _, ok := Verify(g.Secret, noIat, base); ok {
+		t.Error("remember token without iat accepted")
+	}
+	refreshed := Sign(g.Secret, map[string]any{"uid": int64(7), "sv": int64(3), "iat": g.Timestamp, "rm": int64(1)}, base.Add(89*24*time.Hour))
+	if _, ok := Verify(g.Secret, refreshed, base.Add(90*24*time.Hour)); !ok {
+		t.Error("refreshed remember token rejected at 90 days from iat")
+	}
+	if _, ok := Verify(g.Secret, refreshed, base.Add(90*24*time.Hour+time.Second)); ok {
+		t.Error("remember token accepted past 90 days from iat")
 	}
 }
 
```

### go/internal/session/cap_test.go

```go
package session

import (
	"context"
	"testing"
	"time"
)

// TestVerifyMatchesPythonReads runs the auth.json read cases (written by
// App/scripts/auth_golden.py from auth._session_payload) through Verify,
// which Load uses (brief 1281).
func TestVerifyMatchesPythonReads(t *testing.T) {
	g := loadAuthGolden(t)
	if len(g.Reads) == 0 {
		t.Fatal("no read cases")
	}
	for _, c := range g.Reads {
		if _, ok := Verify(g.Secret, c.Token, time.Unix(c.At, 0)); ok != c.OK {
			t.Errorf("%s: Verify ok=%v, Python %v", c.Name, ok, c.OK)
		}
	}
}

// TestLoadSessionCapDatabase: Load refuses remember-me cookies past 30 days
// sliding or 90 days absolute, as current_user does.
func TestLoadSessionCapDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version)
		VALUES (2, 'host01', 'x', '2026-01-01T00:00:00+00:00', 'host', 1, 1)`); err != nil {
		t.Fatal(err)
	}
	base := time.Unix(1798761600, 0)
	opt := IssueOptions{Remember: true}
	tok, err := IssueSession(dbSecret, 2, 1, opt, base)
	if err != nil {
		t.Fatal(err)
	}
	for _, c := range []struct {
		at   time.Duration
		want bool
	}{{29 * 24 * time.Hour, true}, {30*24*time.Hour + time.Second, false}, {400 * 24 * time.Hour, false}} {
		h, err := Load(ctx, pool, tok, base.Add(c.at), dbEnv)
		if err != nil || (h != nil) != c.want {
			t.Errorf("remember cookie at %v: host %v err %v", c.at, h != nil, err)
		}
	}
	iat := base.Unix()
	opt.IssuedAt = &iat
	late, err := IssueSession(dbSecret, 2, 1, opt, base.Add(80*24*time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	if h, _ := Load(ctx, pool, late, base.Add(90*24*time.Hour), dbEnv); h == nil {
		t.Error("refreshed cookie refused at 90 days from iat")
	}
	if h, _ := Load(ctx, pool, late, base.Add(90*24*time.Hour+time.Second), dbEnv); h != nil {
		t.Error("cookie accepted past 90 days from iat")
	}
}
```

### go/internal/signup/signup.go

```go
// Package signup is App/app/signup.py in Go (brief 1281): self sign-up, the
// verification link, activation and the ad-click consent records. It is a
// library only: no route is registered here. Turnstile, the pages and the
// retention purge stay with their own briefs.
package signup

import (
	"net/url"
	"regexp"
	"strconv"
	"strings"
)

// Limits and lifetimes, as signup.py names them.
const (
	VerifyMaxAge      = 24 * 60 * 60
	UnverifiedTTLDays = 7
	WorkspaceMax      = 120
	SignupIPMax       = 10
	SignupEmailMax    = 3
	hour              = 60 * 60

	Google = "google"
	Meta   = "meta"

	GooglePrivacyURL = "https://business.safety.google/privacy/"
	MetaPrivacyURL   = "https://www.facebook.com/privacy/policy/"
	GoogleExportDays = 85
	ClickMaxAgeDays  = 90
	UserAgentMax     = 512
	ConsentGranted   = "Granted"
	ConsentDenied    = "Denied"

	clickFutureSlackMS = 5 * 60 * 1000
	clickSalt          = "ubyhost-signup-click"
	verifySalt         = "ubyhost-signup-verify"
)

// Platforms is PLATFORMS, in display order.
var Platforms = []string{Google, Meta}

// UTMKeys is UTM_KEYS.
var UTMKeys = []string{"utm_source", "utm_medium", "utm_campaign"}

// clickParam is one CLICK_PARAMS entry. clickParams keeps the dict order.
type clickParam struct {
	name     string
	platform string
	re       *regexp.Regexp
}

var (
	shortID     = regexp.MustCompile(`^[A-Za-z0-9_-]{1,200}$`)
	clickParams = []clickParam{
		{"gclid", Google, shortID},
		{"gbraid", Google, shortID},
		{"wbraid", Google, shortID},
		{"fbclid", Meta, regexp.MustCompile(`^[A-Za-z0-9_-]{1,500}$`)},
	}
	utmRE = regexp.MustCompile(`^[A-Za-z0-9._+ -]{1,100}$`)
)

// IDColumns is ID_COLUMNS: the ad_click columns blanked together.
var IDColumns = map[string][]string{
	Google: {"gclid", "gbraid", "wbraid"},
	Meta:   {"fbc", "client_user_agent"},
}

// ConsentFields is CONSENT_FIELDS: the checkbox name per platform.
var ConsentFields = map[string]string{Google: "ads_consent", Meta: "meta_consent"}

// ConsentVersions is CONSENT_VERSIONS; the language is appended.
var ConsentVersions = map[string]string{Google: "ads-google-v1", Meta: "ads-meta-v2"}

// IDRetentionDays is ID_RETENTION_DAYS: (after the click, after upload or send).
var IDRetentionDays = map[string][2]int{Google: {90, 30}, Meta: {90, 7}}

// CSVHeader is CSV_HEADER of the Google Ads offline conversion file.
var CSVHeader = []string{"Google Click ID", "Conversion Name", "Conversion Time", "Ad User Data", "Ad Personalization"}

func platformOf(param string) (clickParam, bool) {
	for _, p := range clickParams {
		if p.name == param {
			return p, true
		}
	}
	return clickParam{}, false
}

// envFlag is os.environ.get(name, "0").lower() in ("1", "true", "yes").
func envFlag(getenv func(string) string, name string) bool {
	switch strings.ToLower(getenv(name)) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// envOr is os.environ.get(name, def): an unset or empty variable gives def.
func envOr(getenv func(string) string, name, def string) string {
	if v := getenv(name); v != "" {
		return v
	}
	return def
}

// Enabled is signup.enabled (config.SIGNUP_ENABLED).
func Enabled(getenv func(string) string) bool { return envFlag(getenv, "UBYHOST_SIGNUP_ENABLED") }

// publicBase is config.PUBLIC_BASE_URL.
func publicBase(getenv func(string) string) string {
	return strings.TrimRight(envOr(getenv, "UBYHOST_PUBLIC_BASE_URL", "http://127.0.0.1:8080"), "/")
}

// appBase is config.app_base_url().
func appBase(getenv func(string) string) string {
	if v := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/"); v != "" {
		return v
	}
	return publicBase(getenv)
}

// operatorEmail is config.OPERATOR_EMAIL.
func operatorEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL")); v != "" {
		return v
	}
	return "support@ubyhost.com"
}

// notifyEmail is config.SIGNUP_NOTIFY_EMAIL.
func notifyEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_SIGNUP_NOTIFY_EMAIL")); v != "" {
		return v
	}
	return operatorEmail(getenv)
}

// conversionName is config.ADS_CONVERSION_NAME.
func conversionName(getenv func(string) string) string {
	return strings.TrimSpace(envOr(getenv, "UBYHOST_ADS_CONVERSION_NAME", "UbyHost sign-up"))
}

// metaEnabled is config.meta_capi_enabled().
func metaEnabled(getenv func(string) string) bool {
	return strings.TrimSpace(getenv("UBYHOST_META_DATASET_ID")) != "" &&
		strings.TrimSpace(getenv("UBYHOST_META_ACCESS_TOKEN")) != ""
}

// CleanClickID is clean_click_id: the trimmed value if it fits the parameter's
// pattern, else "".
func CleanClickID(param, value string) string {
	p, ok := platformOf(param)
	text := pyStrip(value)
	if ok && p.re.MatchString(text) {
		return text
	}
	return ""
}

// CleanGclid is clean_gclid.
func CleanGclid(value string) string { return CleanClickID("gclid", value) }

// CleanUTM is clean_utm.
func CleanUTM(value string) string {
	text := pyStrip(value)
	if utmRE.MatchString(text) {
		return text
	}
	return ""
}

// last is Starlette's QueryParams/FormData .get: the last value of a key.
func last(params url.Values, key string) (string, bool) {
	vs, ok := params[key]
	if !ok || len(vs) == 0 {
		return "", false
	}
	return vs[len(vs)-1], true
}

// ClickIDs is click_ids: the valid ad click identifiers in a query string.
func ClickIDs(params url.Values) map[string]string {
	found := map[string]string{}
	for _, p := range clickParams {
		v, _ := last(params, p.name)
		if c := CleanClickID(p.name, v); c != "" {
			found[p.name] = c
		}
	}
	return found
}

// PlatformActive is platform_active: Meta only once the Conversions API is set up.
func PlatformActive(getenv func(string) string, platform string) bool {
	if platform == Meta {
		return metaEnabled(getenv)
	}
	return true
}

// ClickPlatforms is click_platforms: the active platforms a click has ids for.
func ClickPlatforms(getenv func(string) string, click *Click) []string {
	if click == nil {
		return nil
	}
	present := map[string]bool{}
	for param := range click.IDs {
		if p, ok := platformOf(param); ok {
			present[p.platform] = true
		}
	}
	var out []string
	for _, p := range Platforms {
		if present[p] && PlatformActive(getenv, p) {
			out = append(out, p)
		}
	}
	return out
}

// Attribution is attribution(params, mint=mint): the clean utm_* labels and
// the signed click value. With mint, raw identifiers in params are signed
// with seenMS (the page view); a form post only keeps a valid signed value.
func Attribution(secret string, params url.Values, mint bool, nowMS int64) map[string]string {
	found := map[string]string{}
	for _, k := range UTMKeys {
		v, _ := last(params, k)
		if c := CleanUTM(v); c != "" {
			found[k] = c
		}
	}
	token, _ := last(params, "click")
	click := ReadClick(secret, token, nowMS)
	if click == nil {
		token = ""
	}
	if mint {
		raw := ClickIDs(params)
		if len(raw) > 0 && (click == nil || !sameIDs(click.IDs, raw)) {
			if minted, err := IssueClick(secret, raw, nowMS); err == nil {
				token = minted
			}
		}
	}
	if token != "" {
		found["click"] = token
	}
	return found
}

func sameIDs(a, b map[string]string) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if w, ok := b[k]; !ok || w != v {
			return false
		}
	}
	return true
}

// CleanSelection is signup_selection.clean: only the bounded plan choices.
func CleanSelection(params url.Values) map[string]string {
	result := map[string]string{}
	for _, f := range []struct {
		field   string
		choices []string
	}{{"plan", []string{"standard", "max"}}, {"interval", []string{"month", "year"}}, {"ttlock", []string{"0", "1"}}} {
		if v, ok := last(params, f.field); ok {
			for _, c := range f.choices {
				if v == c {
					result[f.field] = v
				}
			}
		}
	}
	count, ok := last(params, "apartments")
	if !ok {
		count, ok = last(params, "apts")
	}
	if ok && apartmentsRE.MatchString(count) {
		if n, _ := strconv.Atoi(count); n <= 50 {
			result["apartments"] = strconv.Itoa(n)
		}
	}
	return result
}

var apartmentsRE = regexp.MustCompile(`^[1-9][0-9]?$`)

// SignupSource is signup_source: google, meta or none for the admin funnel.
func SignupSource(stored []string, attr map[string]string) string {
	for _, p := range Platforms {
		for _, s := range stored {
			if s == p {
				return p
			}
		}
	}
	label := strings.ToLower(pyStrip(attr["utm_source"]))
	for _, p := range []struct {
		platform string
		names    []string
	}{{Google, []string{"google", "adwords", "googleads", "google_ads"}}, {Meta, []string{"facebook", "fb", "instagram", "ig", "meta"}}} {
		for _, n := range p.names {
			if label == n {
				return p.platform
			}
		}
	}
	return "none"
}

// CleanUserAgent is clean_user_agent: printable ASCII only, trimmed, at most
// 512 characters; "" stands for None.
func CleanUserAgent(value string) string {
	var b strings.Builder
	for _, r := range value {
		if r >= ' ' && r <= '~' {
			b.WriteRune(r)
		}
	}
	text := strings.Trim(b.String(), " ")
	if len(text) > UserAgentMax {
		text = text[:UserAgentMax]
	}
	return text
}
```

### go/internal/signup/tokens.go

```go
package signup

import (
	"bytes"
	"compress/zlib"
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"io"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Click is a verified signed click value: the identifiers and when they
// were first seen (milliseconds since the epoch).
type Click struct {
	IDs    map[string]string
	SeenMS int64
}

// pyStrip is str.strip(): Go's unicode.IsSpace plus U+001C to U+001F.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) })
}

// jsonString writes s as a JSON string the way json.dumps(ensure_ascii=False)
// does for the ASCII values signed here (ids, nonces).
func jsonString(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}

// plainSign is the HMAC-SHA1 signature of itsdangerous Signer (django-concat).
func plainSign(secret, salt, message string) string {
	derived := sha1.Sum([]byte(salt + "signer" + secret))
	mac := hmac.New(sha1.New, derived[:])
	mac.Write([]byte(message))
	return base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

// plainDumps is URLSafeSerializer(secret, salt).dumps for a ready JSON text:
// zlib when that is shorter, URL-safe base64, then "." and the signature.
func plainDumps(secret, salt, payload string) (string, error) {
	data := []byte(payload)
	prefix := ""
	var zb bytes.Buffer
	w, err := zlib.NewWriterLevel(&zb, zlib.DefaultCompression)
	if err != nil {
		return "", err
	}
	if _, err := w.Write(data); err != nil {
		return "", err
	}
	if err := w.Close(); err != nil {
		return "", err
	}
	if zb.Len() < len(data)-1 {
		data = zb.Bytes()
		prefix = "."
	}
	value := prefix + base64.RawURLEncoding.EncodeToString(data)
	return value + "." + plainSign(secret, salt, value), nil
}

// plainLoads is URLSafeSerializer(secret, salt).loads: the JSON object, with
// whole numbers as int64; ok is false wherever Python raises BadSignature.
func plainLoads(secret, salt, token string) (map[string]any, bool) {
	cut := strings.LastIndex(token, ".")
	if cut < 0 {
		return nil, false
	}
	value, sig := token[:cut], token[cut+1:]
	if !hmac.Equal([]byte(plainSign(secret, salt, value)), []byte(sig)) {
		return nil, false
	}
	compressed := strings.HasPrefix(value, ".")
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		return nil, false
	}
	if compressed {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			return nil, false
		}
		if raw, err = io.ReadAll(r); err != nil {
			return nil, false
		}
	}
	return decodeObject(raw)
}

// decodeObject decodes a JSON object with whole numbers as int64.
func decodeObject(raw []byte) (map[string]any, bool) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, false
	}
	m, ok := v.(map[string]any)
	if !ok || m == nil {
		return nil, false
	}
	for k, e := range m {
		m[k] = number(e)
	}
	return m, true
}

func number(v any) any {
	switch x := v.(type) {
	case json.Number:
		if i, err := x.Int64(); err == nil {
			return i
		}
	case map[string]any:
		for k, e := range x {
			x[k] = number(e)
		}
	}
	return v
}

// IssueClick is issue_click: the identifiers (in CLICK_PARAMS order) and the
// moment they were first seen, signed with salt ubyhost-signup-click.
func IssueClick(secret string, ids map[string]string, seenMS int64) (string, error) {
	var parts []string
	for _, p := range clickParams {
		if v, ok := ids[p.name]; ok {
			parts = append(parts, jsonString(p.name)+":"+jsonString(v))
		}
	}
	payload := `{"i":{` + strings.Join(parts, ",") + `},"t":` + strconv.FormatInt(seenMS, 10) + `}`
	return plainDumps(secret, clickSalt, payload)
}

// ReadClick is read_click: nil for a bad signature, a click time more than
// five minutes ahead or more than 90 days back, or any identifier that is
// not valid. nowMS is the current time in milliseconds.
func ReadClick(secret, token string, nowMS int64) *Click {
	if token == "" {
		return nil
	}
	payload, ok := plainLoads(secret, clickSalt, token)
	if !ok {
		return nil
	}
	rawIDs, ok := payload["i"].(map[string]any)
	if !ok {
		return nil
	}
	seen, ok := payload["t"].(int64)
	if !ok {
		return nil
	}
	if seen > nowMS+clickFutureSlackMS || seen < nowMS-ClickMaxAgeDays*86400*1000 {
		return nil
	}
	ids := map[string]string{}
	for _, p := range clickParams {
		v, present := rawIDs[p.name]
		if !present {
			continue
		}
		s, isString := v.(string)
		if !isString {
			return nil
		}
		if c := CleanClickID(p.name, s); c != "" {
			ids[p.name] = c
		}
	}
	if len(ids) == 0 || len(ids) != len(rawIDs) {
		return nil
	}
	return &Click{IDs: ids, SeenMS: seen}
}

// IssueToken is issue_token: {"uid", "n"} signed at now with salt
// ubyhost-signup-verify, valid for VerifyMaxAge.
func IssueToken(secret string, userID int64, nonce string, now time.Time) (string, error) {
	payload := `{"uid":` + strconv.FormatInt(userID, 10) + `,"n":` + jsonString(nonce) + `}`
	return secure.NewTimedSerializer(secret, verifySalt).Dumps(json.RawMessage(payload), now)
}

// readToken is the signature half of pending_account: the uid and nonce of
// a verify token at most 24 hours old, ok false otherwise.
func readToken(secret, token string, now time.Time) (int64, string, bool) {
	var raw json.RawMessage
	if err := secure.NewTimedSerializer(secret, verifySalt).Loads(token, VerifyMaxAge*time.Second, now, &raw); err != nil {
		return 0, "", false
	}
	payload, ok := decodeObject(raw)
	if !ok {
		return 0, "", false
	}
	uid, _ := payload["uid"].(int64)
	nonce, _ := payload["n"].(string)
	if uid == 0 || nonce == "" {
		return 0, "", false
	}
	return uid, nonce, true
}
```

### go/internal/signup/texts.go

```go
package signup

import "strings"

// consentStrings are the host_i18n keys of the consent boxes (en, cs, vi),
// copied from App/app/host_i18n.py; the golden test checks every text.
var consentStrings = map[string]map[string]string{
	"en": {
		"signup.ads_consent":       "Optional: I agree that UbyHost may record that I came from a Google ad and share that click identifier with Google (an independent controller) to measure our ad campaigns. No personalised ads. You can withdraw anytime in Settings.",
		"signup.ads_consent_link":  "How Google uses data",
		"signup.meta_consent":      "Optional: I agree that UbyHost may record that I came from Facebook or Instagram and send that click identifier and my browser type string, with the fact and time of my sign-up, to Meta Platforms Ireland Ltd. to measure our campaigns. Meta receives it as a joint controller and then uses it as its own controller. You can withdraw anytime in Settings.",
		"signup.meta_consent_link": "How Meta uses data",
	},
	"cs": {
		"signup.ads_consent":       "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z reklamy Google, a předal tento identifikátor kliknutí společnosti Google (samostatnému správci) k měření úspěšnosti našich reklam. Bez personalizované reklamy. Souhlas můžete kdykoli odvolat v Nastavení.",
		"signup.ads_consent_link":  "Jak Google používá data",
		"signup.meta_consent":      "Nepovinné: Souhlasím, aby UbyHost zaznamenal, že jsem přišel z Facebooku nebo Instagramu, a předal tento identifikátor kliknutí a údaj o typu mého prohlížeče spolu s informací o mé registraci a jejím čase společnosti Meta Platforms Ireland Ltd. k měření úspěšnosti našich kampaní. Meta je při předání společným správcem a dále údaje zpracovává jako samostatný správce. Souhlas můžete kdykoli odvolat v Nastavení.",
		"signup.meta_consent_link": "Jak Meta používá data",
	},
	"vi": {
		"signup.ads_consent":       "Optional: I agree that UbyHost may record that I came from a Google ad and share that click identifier with Google (an independent controller) to measure our ad campaigns. No personalised ads. You can withdraw anytime in Settings.",
		"signup.ads_consent_link":  "Cách Google sử dụng dữ liệu",
		"signup.meta_consent":      "Optional: I agree that UbyHost may record that I came from Facebook or Instagram and send that click identifier and my browser type string, with the fact and time of my sign-up, to Meta Platforms Ireland Ltd. to measure our campaigns. Meta receives it as a joint controller and then uses it as its own controller. You can withdraw anytime in Settings.",
		"signup.meta_consent_link": "Cách Meta sử dụng dữ liệu",
	},
}

// consentLanguage is host_i18n.normalise_language.
func consentLanguage(lang string) string {
	code := []rune(strings.ToLower(lang))
	if len(code) > 2 {
		code = code[:2]
	}
	if _, ok := consentStrings[string(code)]; ok {
		return string(code)
	}
	return "en"
}
```
