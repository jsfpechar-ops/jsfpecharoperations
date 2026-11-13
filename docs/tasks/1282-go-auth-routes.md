# 1282: Go auth routes that render no page

Status: todo
Depends on: 1280, 1281 | Base commit: 3208184 | Branch: go-login-accounts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (12 new files, 4 edits by one diff)

## 1. Objective

Port the 18 routes of `App/app/routes/admin_accounts.py`, `signup.py` and `passkeys.py` whose every answer is a redirect, plain text, CSV, JSON or empty into the new Go package `go/internal/web/auth`, registered through `go/cmd/ubyhost-web/register_web_auth.go`. Nothing goes live: Caddy sends a path to Go only once the owner lists it in `UBYHOST_GO_PATHS`. Also: `session.AcceptancePending` uses Python's per-document versions (privacy and DPA 1.8, not 1.7), and `signup.WithdrawConsent` writes its `ad_click` UPDATE as literals so the state-machine pin test sees it.

## 2. Context

Rules (AGENTS.md, rules.md#secrets, go-full-move.md section 7): public repo, the golden secret is a fixed test string; no new dependency (`go/go.mod`, `go/go.sum` unchanged); SQL through pgx, parameterised; route functions do not touch the pool while building; `hostweb/`, `jobs/`, `main.go`, `App/app/`, `App/tests/conftest.py` are read-only.

Ported (Python is the truth; every case is recorded from the real FastAPI app):

| Route | Python | Gate |
|---|---|---|
| POST /logout, /account/logout-all | `logout`, `logout_all` | CSRF, current_user |
| POST /account/onboarding-emails, /account/stay-fee-emails, /account/guest-details-mail | `*_submit` (+ `lifecycle_mail.set_opt_out`/`resubscribe`, `stay_fee_auto.set_emails_enabled`, `guest_mail_pref.set_full_details`) | CSRF, current_user, own host |
| POST /account/2fa/move, /account/2fa/disable | `two_factor_move`, `two_factor_disable` | CSRF, require_login |
| POST /account/security-prompt/seen | `passkeys.security_prompt_seen` (204/401) | CSRF, current_user |
| GET /login/2fa, GET /admin/users | redirects, no gate | none |
| GET /admin/incidents | redirect | _require_admin |
| POST /admin/users/{id}/impersonate, /admin/stop-impersonating | `user_impersonate`, `stop_impersonating` | CSRF, 422, _require_admin |
| POST /admin/incidents, /admin/incidents/{id} | `incident_create`, `incident_update` (+ `incidents.create/update/mark_timestamp`) | CSRF, 422, _require_admin |
| POST /admin/ads-conversions.csv | `ads_conversions_csv` (404 while sign-up off) | CSRF, 404, _require_admin |
| POST /admin/users/{id}/ads-consent/withdraw, /settings/privacy/ad-consent | `ads_consent_withdraw`, `ad_consent_settings` | CSRF, 422, admin / require_login |

Facts the code depends on (all proven by the golden replay):

- Every route of these routers runs `security.protect_host_post` first (`hostweb.CSRF`), then FastAPI validates `{id}`: a non-integer is a 422 with pydantic's `int_parsing` body even when signed out (`pathID`).
- `require_login` skips the paused-plan check on `/account`, `/settings`, `/logout`, ... (`_READ_ONLY_OPEN_PREFIXES`); `hostweb.Login` checks every POST, so `login()` hands it a copy whose method is `POST-READ-ONLY-OPEN` there. `bare` drops the HTML body and Content-Type `http.Redirect` adds to GET redirects (RedirectResponse sends neither).
- `db.audit` takes `actor_user_id`, `impersonator_user_id` and the default owner from `require_login`'s context; routes that only call `current_user` write NULLs (e.g. `stay_fee_emails_on` has owner NULL). `audit(ctx, g, ...)` with `g` nil reproduces that.
- `form.get` is the last value of a repeated key (`formLast`); `form_str` strips with `str.strip` (U+001C..U+001F included); `enabled` on the three switches is compared unstripped.
- `Cache-Control: no-store, private` comes from `main.go`'s `metrics.wrap`; the test wraps the same way.
- Flash texts: `go_host_i18n.py` only covers `go/internal/<pkg>/`, so `auth_routes_golden.py` writes `web/auth/i18n.json` in the same format from `i18n_keys.txt`; `App/tests/test_go_auth_routes.py` fails when it goes stale. vi lacks two keys; both sides fall back to en.
- `config.py`: `UBYHOST_TERMS_VERSION` default 1.7, `UBYHOST_PRIVACY_VERSION` 1.8, `UBYHOST_DPA_VERSION` 1.8, read unstripped (`session.CurrentVersions`).
- Known gap, not fixed here (hostweb is read-only): `hostweb.endExpired` signs the stop cookie without `rf` and with SameSite=Strict, Python adds `rf` and uses Lax (`knownGaps` in routes_test.go, case `stop_expired`).

Excluded, with reason: `POST /admin/users`, `/admin/users/{id}/invite`, `/admin/users/{id}/email` (they send mail through `mail_notify.link_mail` + `mail.send_now` and `email_changed`: brief 1283 with `go/internal/mail/auth_*.go` goldens); `/admin/users/{id}/schedule-deletion` (`mail_notify.workspace_deletion`, shared with the retention job's "deleted" mail: 1283 or the retention thread, coordinator decides); `/admin/users/{id}/export` (`workspace_export.build_workspace_zip`: exports thread, section 7); `GET /admin/funnel`, `GET /admin` (customer admin thread); `GET`/`POST /signup/verify`, `POST /login/link`, `POST /login`, `POST /login/2fa`, `/account/accept`, `/account/2fa/setup`, `/account/email*` (render a template on some branch); passkey JSON routes (WebAuthn library decision pending). No route here was already registered in Go.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/auth.go` | create | `Routes`, gates, form and audit helpers |
| `go/internal/web/auth/account.go` | create | logout, switches, 2FA move/disable, prompt seen |
| `go/internal/web/auth/admin.go` | create | admin redirects, impersonation, incidents, ads export and consent |
| `go/internal/web/auth/i18n_keys.txt` | create | the flash keys |
| `go/internal/web/auth/i18n.json` | create (generated) | by the golden script |
| `go/internal/web/auth/testdata/routes.json` | create (generated) | by the golden script |
| `go/internal/web/auth/auth_test.go` | create | no-DB tests |
| `go/internal/web/auth/routes_test.go` | create | golden replay on Postgres |
| `go/cmd/ubyhost-web/register_web_auth.go` | create | `init()` → `registerRoutes` |
| `App/scripts/auth_routes_golden.py` | create | records Python's answers |
| `App/tests/test_go_auth_routes.py` | create | catalog freshness |
| `go/internal/signup/withdraw_sql_test.go` | create | literal UPDATEs match `IDColumns` |
| `go/internal/session/session.go`, `session_test.go` | edit (diff) | per-document versions |
| `go/internal/signup/register.go` | edit (diff) | literal withdraw UPDATE |
| `App/tests/test_sm_queues.py` | edit (diff) | pin `WithdrawConsent` (2 sites, pending/sending → withdrawn) |
| `docs/tasks/1282-files-2.md` .. `-4.md` | exist | file contents |
| `docs/tasks/1282-report.md` | create | the report |

No other file may change. Final sha256 (`routes.json` is not pinned: the TOTP ciphertext and timing offsets change each run):

| Path | sha256 |
|---|---|
| `go/internal/web/auth/auth.go` | `59dbfd9836da920783c20ca277bee8f0a7d0bb10e37edeb24e49329214444fd6` |
| `go/internal/web/auth/account.go` | `38c7b9057a91e51d5aa795bf2e1d169d094d3479623f7b1fdd213e83f6256c7c` |
| `go/internal/web/auth/admin.go` | `0e054ba441f820003ca28470e52344d7fa2162bb04093865dd067208edfbb017` |
| `go/internal/web/auth/auth_test.go` | `2336f906996fdd6ccabccc8c1fca6ff98d87e6f9c6dcafd356bd02c8415afcf2` |
| `go/internal/web/auth/routes_test.go` | `359219df27f3cb8c2af87dc006385e929668fcfbf2038be9a701efa16e341cd3` |
| `go/internal/web/auth/i18n_keys.txt` | `0a348f395ea8d9d5872f6a44c8bdedc12377a58313be141fd76b0469298d0760` |
| `go/internal/web/auth/i18n.json` | `d3ae4709265d7be190d885e83572172e847c81fff7dc4ea42943fd5ba0ee475c` |
| `go/cmd/ubyhost-web/register_web_auth.go` | `09b96181481278a3e036ca584e8a8725b40a5b0df432c162d95a2b2e78889765` |
| `go/internal/signup/withdraw_sql_test.go` | `8b2d0d4dca19a3e83b9b5e6109f0998b4c3b0fb9d404202631210b1632111655` |
| `App/scripts/auth_routes_golden.py` | `74959243dc9ad694a67dca84c63ed84255e875782b298e54a3b0d9c57e54c1e4` |
| `App/tests/test_go_auth_routes.py` | `e52f59a5bd529fda2d752f0562a9840743c63b00110b12e716a0d92d1d97e33e` |
| `go/internal/session/session.go` | `e8c9195ff735b3d7251938556c9ef58483f60bab4a485ff4cddd3d3b59d0e492` |
| `go/internal/session/session_test.go` | `689b9b550d7f9871762f356dcf0cca2efc07c9fe5129604ca91ba59c823d1697` |
| `go/internal/signup/register.go` | `024bf8533c099da4977d50418142c2a4690858745bf58e255dd21b453b776835` |
| `App/tests/test_sm_queues.py` | `f174f6485d43b0e94f6b32a88e94a41e2e2b9e6d7f712138273d7f086ae07731` |

## 4. Steps

1. Save the diff in the Appendix as `/tmp/1282.diff` and run from the repo root `git apply --check /tmp/1282.diff && git apply /tmp/1282.diff && git diff --stat 2>&1 | tail -6`. Expected: the four §3 edit files. Commit `1282 step 1`.
2. Create `auth.go`, `account.go` ([1282-files-2.md](1282-files-2.md)), `admin.go`, `auth_test.go`, `routes_test.go` ([1282-files-3.md](1282-files-3.md)), `i18n_keys.txt`, `register_web_auth.go`, `withdraw_sql_test.go` ([1282-files-4.md](1282-files-4.md)), each exactly as given. Write `go/internal/web/auth/i18n.json` as `{}` for now. From `go/`: `export PATH=$PATH:/usr/local/go/bin && gofmt -l internal/ cmd/ && go vet ./... 2>&1 | tail -30`. Expected: no output. Commit `1282 step 2`.
3. Create `App/scripts/auth_routes_golden.py` and `App/tests/test_go_auth_routes.py` from 1282-files-4.md. From `App/`: `.venv/bin/python scripts/auth_routes_golden.py 2>&1 | tail -2`. Expected: `wrote go/internal/web/auth/testdata/routes.json` and `wrote go/internal/web/auth/i18n.json`; the i18n.json sha256 matches §3. Commit `1282 step 3`.
4. Run the §6 commands. Compare every sha256 in §3. Write the report. Commit `1282 report`.

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/jobs/`, `go/internal/mail/`, `go/cmd/ubyhost-web/main.go` and the other `register_*.go`, `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/conftest.py`, every other `App/tests/` file, `docs/context/`, `docs/ENVIRONMENT.md`. No `UBYHOST_GO_PATHS` change. Hard rules 3 (no secrets), 4 (no dependency), 5 (SQL) apply.

## 6. Commands

From `go/` (with `export PATH=$PATH:/usr/local/go/bin`):

```bash
gofmt -l internal/ cmd/ 2>&1 | tail -30
go vet ./... 2>&1 | tail -30
go test ./internal/web/... ./internal/session/... ./internal/signup/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
```

Database tests (find a Postgres with `ps aux | grep [p]ostgres`; none: as root `mkdir -p /var/tmp/pg1282 && chown postgres /var/tmp/pg1282 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1282/data -A trust && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1282/data -o "-p 5433 -k /var/tmp/pg1282" -l /var/tmp/pg1282/log start'`):
`UBYHOST_TEST_DATABASE_URL='postgres://postgres@127.0.0.1:5433/postgres?sslmode=disable' go test ./internal/web/... ./internal/session/... ./internal/signup/ -count=1 2>&1 | tail -30`. Expected: `ok` for all four packages (`TestRoutesGoldenDatabase` runs 79 cases, about 15 s).

From `App/`: `.venv/bin/python -m pytest tests/test_go_auth_routes.py tests/test_sm_queues.py tests/test_sm_billing_status.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance

- [ ] `git diff --stat 3208184` lists only §3 files (plus the brief files).
- [ ] Every sha256 in §3 matches.
- [ ] gofmt and vet print nothing; the Go tests are `ok`; `TestRoutesBuildWithoutPool` and `TestRoutesRegisterOnce` pass.
- [ ] The report says whether `TestRoutesGoldenDatabase` ran (not skipped) and passed.
- [ ] The four Python tests pass.
- [ ] `go/go.mod` and `go/go.sum` unchanged.

## 8. Stop and ask

Stop, and write the report, if: an excerpt or anchor is not found or `git apply --check` fails; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, see executor.md); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1282-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `auth.go` `login`/`bare`: the method-copy and body-drop wrappers around `hostweb.Login`; a hostweb change to how it reads `r.Method` breaks the read-only-open skip.
- `account.go` `audit` NULLs for current_user-only routes (Python's contextvar is unset there), and the `onboarding-emails` suppression delete (address normalising mirrors `ubyport.normaliseEmail`, not full `parseaddr`).
- `admin.go` `pathID`: Go accepts what `strconv.ParseInt` accepts after trimming; pydantic also takes forms like `1_000`. `pyIsDigit` is ASCII only (Python's `isdigit` takes other digits).
- `register.go` `WithdrawConsent` literal statements vs `IDColumns` (guarded by `withdraw_sql_test.go`).
- hostweb gaps for its owner: `endExpired` cookie (no `rf`, SameSite Strict); `csrfMaxAge` is 400 days, Python's `CSRF_MAX_AGE` is 30.

## Owner steps

None for this brief. Later, to switch a route on: add its path to `UBYHOST_GO_PATHS` in `.env` (double-quoted, space-separated) and redeploy; a path with `{id}` needs a Caddy pattern, so ask the orchestrator for the exact value first.

## Appendix: diff for step 1

```diff
diff --git a/App/tests/test_sm_queues.py b/App/tests/test_sm_queues.py
index d15e2aa..ac6f4cf 100644
--- a/App/tests/test_sm_queues.py
+++ b/App/tests/test_sm_queues.py
@@ -220,6 +220,7 @@ SEND_SITES = {
     (GOCAPI, "Send"): 5,
     (SIGNUP, "withdraw_consent"): 1,
     (GOSIGNUP, "enqueueMeta"): 1,
+    (GOSIGNUP, "WithdrawConsent"): 2,
 }
 _WITHDRAW = '"send_state": "withdrawn" if row["send_state"] in ("pending", "sending")'
 SEND_MOVES = [
@@ -240,6 +241,7 @@ SEND_MOVES = [
     (GOCAPI, "Send", "state, attempts, truncate(out.detail, 400), iso(now.Add(retryDelay(attempts))), id, stateSending)", ("sending",), "failed"),
     (GOCAPI, "Send", "stateFailed, attempts, truncate(out.detail, 400), id, stateSending)", ("sending",), "failed"),
     (GOSIGNUP, "enqueueMeta", "send_state = 'pending', event_id = $1, next_attempt_at = $2", (None,), "pending"),
+    (GOSIGNUP, "WithdrawConsent", 'w := "withdrawn"', ("pending", "sending"), "withdrawn"),
 ]
 
 
diff --git a/go/internal/session/session.go b/go/internal/session/session.go
index 0e1091f..ced898f 100644
--- a/go/internal/session/session.go
+++ b/go/internal/session/session.go
@@ -24,8 +24,6 @@ const (
 	CookieName = "ubyhost_session"
 	// salt is the itsdangerous salt of _serializer (auth.py lines 55-56).
 	salt = "ubyhost-session"
-	// defaultVersion is the default of UBYHOST_*_VERSION (brief 0672, section 2).
-	defaultVersion = "1.7"
 )
 
 // pythonKeyOrder is the insertion order of issue_session (auth.py lines 225-260).
@@ -265,11 +263,7 @@ func impersonationMaxAge(getenv func(string) string) int64 {
 // legal_acceptance row at its current version for userID (acceptance.pending,
 // App/app/acceptance.py lines 46-56).
 func AcceptancePending(ctx context.Context, db *pgxpool.Pool, userID int64, getenv func(string) string) (bool, error) {
-	versions := map[string]string{
-		"terms":   versionOr(getenv, "UBYHOST_TERMS_VERSION"),
-		"privacy": versionOr(getenv, "UBYHOST_PRIVACY_VERSION"),
-		"dpa":     versionOr(getenv, "UBYHOST_DPA_VERSION"),
-	}
+	versions := CurrentVersions(getenv)
 	rows, err := db.Query(ctx,
 		`SELECT document, version FROM legal_acceptance WHERE user_account_id = $1`, userID)
 	if err != nil {
@@ -295,11 +289,28 @@ func AcceptancePending(ctx context.Context, db *pgxpool.Pool, userID int64, gete
 	return false, nil
 }
 
-func versionOr(getenv func(string) string, key string) string {
-	if v := strings.TrimSpace(getenv(key)); v != "" {
-		return v
+// documentVersions are the env var and default of each document's current
+// version: config.TERMS_VERSION, PRIVACY_VERSION and DPA_VERSION
+// (App/app/config.py).
+var documentVersions = map[string][2]string{
+	"terms":   {"UBYHOST_TERMS_VERSION", "1.7"},
+	"privacy": {"UBYHOST_PRIVACY_VERSION", "1.8"},
+	"dpa":     {"UBYHOST_DPA_VERSION", "1.8"},
+}
+
+// CurrentVersions is acceptance.current_versions: os.environ.get(name,
+// default), used as read (Python does not strip it). An empty value counts as
+// unset, as getenv cannot tell the two apart.
+func CurrentVersions(getenv func(string) string) map[string]string {
+	out := make(map[string]string, len(documentVersions))
+	for doc, nd := range documentVersions {
+		v := getenv(nd[0])
+		if v == "" {
+			v = nd[1]
+		}
+		out[doc] = v
 	}
-	return defaultVersion
+	return out
 }
 
 // queryAccount loads one user_account row; found is false when there is none.
diff --git a/go/internal/session/session_test.go b/go/internal/session/session_test.go
index c0fb53c..dde3302 100644
--- a/go/internal/session/session_test.go
+++ b/go/internal/session/session_test.go
@@ -288,9 +288,19 @@ func TestLoadDatabase(t *testing.T) {
 	if err != nil || !pending {
 		t.Fatalf("before acceptance: pending=%v err=%v", pending, err)
 	}
+	// terms 1.7, privacy 1.8, dpa 1.8: the config.py defaults. privacy at
+	// 1.7 alone must still leave the acceptance pending.
+	if _, err := pool.Exec(ctx, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, $4, $5, $6)`,
+		int64(10), int64(2), "privacy", "1.7", "2026-01-01T00:00:00+00:00", "clickwrap"); err != nil {
+		t.Fatal(err)
+	}
 	for i, doc := range []string{"terms", "privacy", "dpa"} {
+		if pending, err := AcceptancePending(ctx, pool, 2, dbEnv); err != nil || !pending {
+			t.Fatalf("before %s: pending=%v err=%v", doc, pending, err)
+		}
+		version := map[string]string{"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}[doc]
 		if _, err := pool.Exec(ctx, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, $4, $5, $6)`,
-			int64(i+1), int64(2), doc, "1.7", "2026-01-01T00:00:00+00:00", "clickwrap"); err != nil {
+			int64(i+1), int64(2), doc, version, "2026-01-01T00:00:00+00:00", "clickwrap"); err != nil {
 			t.Fatal(err)
 		}
 	}
@@ -299,3 +309,23 @@ func TestLoadDatabase(t *testing.T) {
 		t.Fatalf("after acceptance: pending=%v err=%v", pending, err)
 	}
 }
+
+// TestCurrentVersions pins the per-document defaults and env vars of
+// App/app/config.py (TERMS_VERSION 1.7, PRIVACY_VERSION 1.8, DPA_VERSION 1.8).
+func TestCurrentVersions(t *testing.T) {
+	got := CurrentVersions(func(string) string { return "" })
+	want := map[string]string{"terms": "1.7", "privacy": "1.8", "dpa": "1.8"}
+	for doc, v := range want {
+		if got[doc] != v {
+			t.Errorf("default %s = %q, want %q", doc, got[doc], v)
+		}
+	}
+	env := map[string]string{"UBYHOST_TERMS_VERSION": "2.0", "UBYHOST_PRIVACY_VERSION": " 2.1", "UBYHOST_DPA_VERSION": "2.2"}
+	got = CurrentVersions(func(k string) string { return env[k] })
+	want = map[string]string{"terms": "2.0", "privacy": " 2.1", "dpa": "2.2"}
+	for doc, v := range want {
+		if got[doc] != v {
+			t.Errorf("env %s = %q, want %q", doc, got[doc], v)
+		}
+	}
+}
diff --git a/go/internal/signup/register.go b/go/internal/signup/register.go
index e857038..c13a813 100644
--- a/go/internal/signup/register.go
+++ b/go/internal/signup/register.go
@@ -560,8 +560,16 @@ func enqueueMeta(ctx context.Context, pool *pgxpool.Pool, userID int64, at strin
 // keep the record, never send a Meta event not sent yet. False when there was
 // no active consent.
 func WithdrawConsent(ctx context.Context, pool *pgxpool.Pool, userID int64, platform, actor string, now time.Time) (bool, error) {
-	cols, ok := IDColumns[platform]
-	if !ok {
+	// The update_if of withdraw_consent per platform: the platform's
+	// IDColumns blanked, written out so App/tests/test_sm_queues.py sees the
+	// send_state write (pending or sending to withdrawn, else unchanged).
+	var update string
+	switch platform {
+	case Google:
+		update = `UPDATE ad_click SET gclid = NULL, gbraid = NULL, wbraid = NULL, withdrawn_at = $1, ids_deleted_at = $2, send_state = $3 WHERE id = $4 AND withdrawn_at IS NULL`
+	case Meta:
+		update = `UPDATE ad_click SET fbc = NULL, client_user_agent = NULL, withdrawn_at = $1, ids_deleted_at = $2, send_state = $3 WHERE id = $4 AND withdrawn_at IS NULL`
+	default:
 		return false, nil
 	}
 	var id int64
@@ -582,13 +590,7 @@ func WithdrawConsent(ctx context.Context, pool *pgxpool.Pool, userID int64, plat
 		w := "withdrawn"
 		sendState = &w
 	}
-	sets := make([]string, 0, len(cols)+3)
-	for _, c := range cols {
-		sets = append(sets, c+" = NULL")
-	}
-	sets = append(sets, "withdrawn_at = $1", "ids_deleted_at = $2", "send_state = $3")
-	tag, err := pool.Exec(ctx, "UPDATE ad_click SET "+strings.Join(sets, ", ")+" WHERE id = $4 AND withdrawn_at IS NULL",
-		at, *deleted, sendState, id)
+	tag, err := pool.Exec(ctx, update, at, *deleted, sendState, id)
 	if err != nil {
 		return false, err
 	}
```
