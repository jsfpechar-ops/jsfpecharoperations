# 1501: Go auth shared pieces (dormant): Turnstile check, client address, `_finish_login`, login language, account mails

Status: todo
Depends on: none | Base commit: none (one big PR mode, see below) | Branch: the orchestrator's current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now. Never create a branch, never push, never open a PR. Commit after each step with the message `1501 step k` (k = the step number), and the report as `1501 report`. The orchestrator opens the one PR.

## 1. Objective

Add the library pieces every later auth brief (1502 to 1513) needs and Go lacks: the server-side Cloudflare Turnstile check, the visitor address behind the proxy, the end of a successful login (`_finish_login`: session and device cookies, login language, audit row, redirect), and the four account mail builders with their queue functions. Tier A: nothing here is wired to a route or a job, so live traffic does not change, and every value is proven equal to Python by goldens generated from the real Python code.

## 2. Context

Rules (AGENTS.md): 2 privacy (one new outbound request, see "PR text"; no new personal-data field); 3 nothing real in the repo (test secrets and example addresses only); 4 no new dependency (`go/go.mod` unchanged); 5 SQL with Postgres placeholders, no schema change; 11 go-first: `App/scripts/auth_shared_golden.py` is port plumbing (exception 1). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1501-files/` mirrors the repo paths. You only copy them and check their sha256 (step 0). Never type or edit the code.

**What each new file does** (Python source of truth in brackets):

- `go/internal/clientip/clientip.go` [`App/app/client_ip.py`, `rate_limit.client_key` lines 114-121]: `Host(r, getenv)` is `request.client.host` after `apply_visitor_client`: CF-Connecting-IP only when the TCP peer is inside `UBYHOST_TRUSTED_PROXY_CIDRS`, else the peer. `Key(r, getenv, suffix)` is `client_key` (`unknown` without a peer, `host:suffix` with a suffix). The existing Go copies in `web/booking` and `payments` trust the header unconditionally; this one follows Python.
- `go/internal/turnstile/turnstile.go` [`App/app/turnstile.py`, `config.py` 455-467]: `FromEnv`, `Required` (production and site key, secret, hostnames all set), `PageSiteKey` (the `turnstile_site_key` template global), `Verifier.Verify`: the same skip conditions, the POST to `https://challenges.cloudflare.com/turnstile/v0/siteverify` with `secret`, `response`, `remoteip` in that order, 10 s timeout, token empty or over 2048 characters refused without a request, success only when `success` is exactly `true`, `action` equals the expected action and the lower-cased `hostname` is configured. Unreachable (transport error, timeout, 4xx/5xx, body not JSON) fails open: the `turnstile_unavailable` warning alert (dedupe key `turnstile_unavailable:<action>`, through `ubyport.RaiseAlert`), then at most 5 passes per address and action in 15 minutes (`rate_limit_event` scope `turnstile_unreachable`, through `session.RateBlocked`/`RateRecord`).
- `go/internal/web/auth/finish.go` [`admin_accounts.py` 44-57 `_keep_login_language`, 210-225 `_finish_login`; `auth.py` `attach_session` 568, `attach_device` 616, `secure_cookies` 988; `host_i18n.remember_language` 11042; `security.safe_local_path` 42-60]: `startSession` writes `user_account.last_login_at`, the audit row (action, detail `method=<method>`, actor the username, owner the account, no actor id), then sets `ubyhost_session` (`issue_session(id, sv, remember)`), a new `ubyhost_device`, and `ubyhost_lang` when it differs, and returns the Location (`safe_local_path(next, "/")` quoted as Starlette's RedirectResponse does). `finishLogin` adds the 303. The login language is `?lang=` (last value), then the `ubyhost_lang` cookie, else Czech.
- `go/internal/mail/auth_link.go` [`mail_notify.py` 2614-2701 `build_link_mail`, 2704-2738 `build_email_changed`, 2769-2794 `build_passkey_added`, 947-972 `build_workspace_deletion`]: the builders, every language. `go/internal/mail/auth_queue.go` [`link_mail` 2672-2701, `email_changed` 2741-2766, `passkey_added` 2797-2815, `workspace_deletion` 1206-1229, `mail.enqueue` `mail.py` 275-340, `validation.fmt_date` 1205-1221]: the queue functions. They only insert `email_outbox` rows (the existing queue); they never send. A login link's body carries `{{claim_secret}}` and the token travels encrypted in `claim_secret_enc`, as Python does.
- The four `*_test.go` files and four `testdata/*.json` goldens; `App/scripts/auth_shared_golden.py` writes the goldens from the real Python (requests.post replaced, no database, no network).

**Differences from Python, on purpose** (all fail safe or unreachable in practice):
1. An unreadable `UBYHOST_TRUSTED_PROXY_CIDRS` entry: Python raises on every request; Go trusts no peer.
2. Python's 10 s `requests` timeout is per connect and per read; Go's is the whole request. The siteverify answer is read up to 64 KiB.
3. `TURNSTILE_SITE_KEY` set to an empty string: Python disables Turnstile; Go cannot tell empty from unset and uses the default key (stricter).
4. A siteverify answer that is JSON but not an object: Python raises (HTTP 500); Go returns an error so the caller answers 500.
5. Log lines name the action or mail kind only, never an address, token, IP or idempotency key (Python logs the key).
6. `startSession` writes the database before the cookies, so a failed write leaves no cookie; Python discards its response on the same error, so the browser sees the same 500.

**PR text (hard rule 2, the orchestrator pastes it into the PR):** "New outbound request (dormant until brief 1502 routes a page to it): the Go service will POST the visitor's Turnstile token, the server secret and the visitor IP to Cloudflare's siteverify endpoint (`challenges.cloudflare.com/turnstile/v0/siteverify`), exactly as `App/app/turnstile.py` does today for the same forms. Reason: bot protection of the login and guest claim forms (docs/SECURITY.md, Bot protection); Cloudflare is already the Turnstile provider and processor. It is sent only when `UBYHOST_DEPLOYMENT=production` and Turnstile is configured; no other data is sent and nothing is stored from the answer."

**For brief 1502 (not done here):** the Go container does not receive `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, `TURNSTILE_HOSTNAMES` or `UBYHOST_TRUSTED_PROXY_CIDRS` (`deploy/lightsail/docker-compose.yml`, service `ubyhost-go`). Without them `Required` is false (the Go login would skip Turnstile in production) and `Host` is Caddy's address (every visitor shares one rate-limit bucket). Brief 1502 must add the four bare keys to that service before any login route is switched to Go.

**Verified by the brief writer** in a throwaway worktree of the branch head with exactly these files, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go build ./...`, `go vet ./internal/... ./cmd/...` clean, `go mod tidy -diff` empty, `go test ./internal/web/auth/... ./internal/session/... ./internal/mail/... ./internal/hostweb/... ./internal/clientip/... ./internal/turnstile/... ./cmd/ubyhost-web/... -count=1` all `ok` with the database tests run (not skipped); the golden script run twice gives the same four hashes. Mutations caught: hostname not lower-cased, token cap 2049, fail-open budget 6, CF header trusted from any peer, hours from 121 minutes, link key 23 characters, audit detail `method:`, default language English, language cookie not compared.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/session/loginlink.go` | `func RateBlocked(ctx context.Context, db *pgxpool.Pool, scope, key string, max, window int, now time.Time) (bool, error) {` |
| `go/internal/ubyport/effects.go` | `func RaiseAlert(ctx context.Context, pool *pgxpool.Pool, level, kind, message, detail, dedupeKey string,` |
| `go/internal/session/issue.go` | `func DeviceToken(secret string, userID, sessionVersion int64, deviceID string, now time.Time) (string, error) {` |
| `go/internal/web/auth/auth.go` | `func (d deps) audit(ctx context.Context, g *gated, at time.Time, action, detail, actor string, owner *int64) error {` |
| `go/internal/mail/auth_signup.go` | `func authShell(publicBaseURL, lang, title, preheader string, blocks, footer []string) string {` |
| `go/internal/mail/outbox_config.go` | `func obNormaliseEmail(raw string) string {` |
| `App/app/turnstile.py` | `_UNREACHABLE_MAX_ATTEMPTS = 5` |
| `App/app/routes/admin_accounts.py` | `db.audit(action, f"method={method}", actor=account["username"], owner_user_id=account["id"])` |
| `App/app/mail_notify.py` | `key_part = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/clientip/clientip.go` | create (copy) | `Host`, `Key`, `TrustedNetworks` |
| `go/internal/clientip/clientip_test.go` | create (copy) | against the golden |
| `go/internal/clientip/testdata/clientip.json` | create (copy, regenerated) | golden |
| `go/internal/turnstile/turnstile.go` | create (copy) | `FromEnv`, `Required`, `PageSiteKey`, `Verifier.Verify`, `Accepted` |
| `go/internal/turnstile/turnstile_test.go` | create (copy) | config and verify cases, fake siteverify server |
| `go/internal/turnstile/turnstile_db_test.go` | create (copy) | fail-open budget and alert (PostgreSQL) |
| `go/internal/turnstile/testdata/turnstile.json` | create (copy, regenerated) | golden |
| `go/internal/mail/auth_link.go` | create (copy) | `BuildLinkMail`, `BuildEmailChanged`, `BuildPasskeyAdded`, `BuildWorkspaceDeletion` |
| `go/internal/mail/auth_queue.go` | create (copy) | `QueueLinkMail`, `QueueEmailChanged`, `QueuePasskeyAdded`, `QueueWorkspaceDeletion`, `FmtDate` |
| `go/internal/mail/auth_link_test.go` | create (copy) | every mail byte for byte, payloads, dates |
| `go/internal/mail/auth_queue_test.go` | create (copy) | outbox rows (PostgreSQL) |
| `go/internal/mail/testdata/auth_mail.json` | create (copy, regenerated) | golden |
| `go/internal/web/auth/finish.go` | create (copy) | `startSession`, `finishLogin`, `keepLoginLanguage`, `safeLocalPath` |
| `go/internal/web/auth/finish_test.go` | create (copy) | paths, language, cookies; `startSession` (PostgreSQL) |
| `go/internal/web/auth/testdata/finish_login.json` | create (copy, regenerated) | golden |
| `App/scripts/auth_shared_golden.py` | create (copy) | writes the four goldens from the real Python |
| `docs/tasks/1501-report.md` | create | the report |

`docs/tasks/1501-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call):

```bash
git status --short | tail -5; ls go/internal/clientip go/internal/turnstile go/internal/mail/auth_link.go go/internal/mail/auth_queue.go go/internal/web/auth/finish.go App/scripts/auth_shared_golden.py 2>&1 | grep -c 'No such file'
cd docs/tasks/1501-files && sha256sum -c <<'EOF' 2>&1 | tail -20
8e778d3d7339ea88728edac499cb78d9d6b3d057eaff07a8db7c86a2aaf7504d  App/scripts/auth_shared_golden.py
f621b5c8158d2f2927220539b741a2d67254e3ce7d53bae8266f403f2b66b77e  go/internal/clientip/clientip.go
797591333e62afa4c5cfc2f3e677d494e10d76816f7c1d8acf5bb92bc379ccad  go/internal/clientip/clientip_test.go
8f91d9f4d609664b2ecb87b281aad1569171557215635f15bf78c869e902da77  go/internal/clientip/testdata/clientip.json
aebc2c30231007b1057e7aa119b1665e9be7070aa15b4c6af7d828cda4c4f9c5  go/internal/mail/auth_link.go
51dbb1dccbb36a1539c6d278837913a7660097eb0f2cf5544e43775830ed1458  go/internal/mail/auth_link_test.go
3358459f1dbb4244e2a3cdfabaf3ac1e616b8cf8ebc4d2c723546dd135a4ec43  go/internal/mail/auth_queue.go
6d565fe61960928cbe1989ff99340a9301fa5870b3a71549799e932e418eb5ac  go/internal/mail/auth_queue_test.go
a233d3ef4457ab4613394857383bee08f35a4e2ff42eaeb6055dd640088d94e9  go/internal/mail/testdata/auth_mail.json
3bbaf1c8a10c9d8383092ed8ccc37b3cc03977cc89c2ba8d83a192d1fb4e65b2  go/internal/turnstile/testdata/turnstile.json
bacbf8eab3d8f5a2d5a93fdb56d006deec8624e61e6ab3f91b4aae369700004c  go/internal/turnstile/turnstile.go
d16fcd6118ea7643adee60cd86bb980ce4b81e6a4be8c46d73bdaccf7fef2c40  go/internal/turnstile/turnstile_db_test.go
3f8c68ae0db90c359956e8c1f39c2b7619ddd03e97fb697f0f4db39dabf24ee5  go/internal/turnstile/turnstile_test.go
8c12248fcfcdd9419613ef7861c7fa2cbf775fc7b7697a3bdc89ffeed647ee5c  go/internal/web/auth/finish.go
bfc455fc1740f296f4512ce5e2b9c94b830d3fb3039deab67bec478d4f3c71f0  go/internal/web/auth/finish_test.go
eede738380f0dff92f9962a37c4fb75bef07f8960587ac261630ac08806dcdee  go/internal/web/auth/testdata/finish_login.json
EOF
```

   Expected: `git status` prints nothing (other briefs' uncommitted files: STOP and ask), the `grep -c` prints `6`, then sixteen `OK` lines. Then check each anchor of section 2 with `grep -cF '<anchor>' <file>` (one call, nine commands joined with `;`): nine `1`. Anything else: STOP (section 8). No commit for step 0.

1. Copy the client address and Turnstile packages (from the repo root):

```bash
mkdir -p go/internal/clientip/testdata go/internal/turnstile/testdata
for f in clientip/clientip.go clientip/clientip_test.go clientip/testdata/clientip.json turnstile/turnstile.go turnstile/turnstile_test.go turnstile/turnstile_db_test.go turnstile/testdata/turnstile.json; do cp docs/tasks/1501-files/go/internal/$f go/internal/$f; done
cd go && gofmt -l internal/clientip internal/turnstile 2>&1 | tail -3; go build ./... 2>&1 | tail -5; go test -count=1 ./internal/clientip/ ./internal/turnstile/ 2>&1 | tail -5
```

   Expected: no gofmt or build output (`go: downloading` lines are fine), two `ok` lines. Commit `1501 step 1`.

2. Copy the account mails (from the repo root):

```bash
for f in auth_link.go auth_queue.go auth_link_test.go auth_queue_test.go testdata/auth_mail.json; do cp docs/tasks/1501-files/go/internal/mail/$f go/internal/mail/$f; done
cd go && gofmt -l internal/mail 2>&1 | tail -3; go test -count=1 ./internal/mail/ 2>&1 | tail -5
```

   Expected: no gofmt output, `ok`. Commit `1501 step 2`.

3. Copy the login finish (from the repo root):

```bash
for f in finish.go finish_test.go testdata/finish_login.json; do cp docs/tasks/1501-files/go/internal/web/auth/$f go/internal/web/auth/$f; done
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ 2>&1 | tail -5; go test -count=1 ./internal/web/auth/ 2>&1 | tail -5
```

   Expected: no gofmt or vet output, `ok`. Commit `1501 step 3`.

4. Copy the golden script and check it reproduces the four goldens (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -5; cd ..`.

```bash
cp docs/tasks/1501-files/App/scripts/auth_shared_golden.py App/scripts/auth_shared_golden.py
cd App && .venv/bin/python scripts/auth_shared_golden.py 2>&1 | tail -5; cd .. && sha256sum go/internal/clientip/testdata/clientip.json go/internal/turnstile/testdata/turnstile.json go/internal/web/auth/testdata/finish_login.json go/internal/mail/testdata/auth_mail.json | tail -4 && git status --short | tail -5
```

   Expected: four `wrote go/internal/...` lines and nothing else, the four hashes equal to those in step 0, and `git status` shows only `?? App/scripts/auth_shared_golden.py`. A different hash: STOP (Python differs from what the code was proven against). Commit `1501 step 4`.

5. Run section 6. Write the report (section 9) and commit it as `1501 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/internal/ubyport/`, `go/internal/signup/`, every existing file in `go/internal/mail/` and `go/internal/web/auth/` (including `auth.go` `Routes`, `routes_test.go` and the existing `testdata/routes.json`), `go/cmd/ubyhost-web/` (no route is registered), `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/` (including `conftest.py`), `deploy/`, `docs/context/*` (`status.md`, `test-map.md`, `decisions.md` are read-only), `docs/tasks/1501-files/`. Never print a secret, token, link or e-mail address. Rules 2, 3, 4, 5 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/clientip internal/turnstile internal/mail internal/web/auth 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && go test ./internal/web/auth/... ./internal/session/... ./internal/mail/... ./internal/hostweb/... ./internal/clientip/... ./internal/turnstile/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` prints only `ok` lines. Without `UBYHOST_TEST_DATABASE_URL` the database tests (`TestFailOpenBudget`, `TestQueueLinkMail`, `TestQueueNotices`, `TestStartSession` and the existing ones) skip; CI runs them. If it is set, they must pass.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1501.

Test-map: no row covers Go packages; the commands above are this brief's tests. No file under `App/app` or `App/tests` changes, so no pytest.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1501 step'` lists steps 1 to 4 (and `git log --oneline --grep='^1501 report'` the report).
- [ ] `for c in $(git log --format=%h --grep='^1501 '); do git show --name-only --format= $c; done | sort -u` lists exactly the 17 files of section 3 plus `docs/tasks/1501-go-auth-shared.md` (the Status line).
- [ ] The copied files equal the sidecar: `cd docs/tasks/1501-files && for f in $(find . -type f); do cmp $f ../../../$f; done` prints nothing.
- [ ] Section 6 output exactly as stated.
- [ ] `for c in $(git log --format=%h --grep='^1501 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|hostweb/|cmd/ubyhost-web/|deploy/'` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, or a regenerated golden has another hash;
- a test fails twice (never change the code: it is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1501-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/turnstile/turnstile.go`: `Required` is exactly `turnstile.required()` (no stricter, no looser skip); the fail-open path (alert, budget 5 per address and action per 15 minutes); `Accepted`; nothing logs the token, secret or IP.
- `go/internal/clientip/clientip.go`: CF-Connecting-IP believed only from a trusted peer.
- `go/internal/web/auth/finish.go`: cookie attributes (session and device Lax, HttpOnly, Secure per `hostweb.SecureCookies`; language not HttpOnly, Secure on an https base only), the audit row, `safeLocalPath` and `locationQuote` (open redirect).
- `go/internal/mail/auth_queue.go`: the token is only in `claim_secret_enc`, never in the body; idempotency keys as Python; no send.
- `App/scripts/auth_shared_golden.py`: calls the real Python functions; the fakes replace only `requests.post`, `_fail_open` and the clock.

## Owner steps

1. Nothing for this brief alone: it is merged with the one big PR and changes nothing in production (no route, no job, no environment change).
2. Before brief 1502 switches `/login` to Go, its owner steps add `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, `TURNSTILE_HOSTNAMES` and `UBYHOST_TRUSTED_PROXY_CIDRS` to the `ubyhost-go` service (see section 2).

## API for the later briefs

All in the repo after this brief; briefs 1502 to 1510 may be written against these signatures in parallel. `deps` is the existing `go/internal/web/auth` handler struct (`d.pool`, `d.getenv`, `d.now`); the unexported names are callable from new files in package `auth`.

**Client address** (`go/internal/clientip`)

```go
func Host(r *http.Request, getenv func(string) string) string            // request.client.host ("" without a peer)
func Key(r *http.Request, getenv func(string) string, suffix string) string // rate_limit.client_key(request, suffix)
```

```go
ipKey := clientip.Key(r, d.getenv, "")                                   // ip_key = rate_limit.client_key(request)
blocked, err := session.LinkRequestBlocked(ctx, d.pool, ipKey, email, at)
```

**Turnstile** (`go/internal/turnstile`)

```go
func Required(getenv func(string) string) bool        // turnstile.required()
func PageSiteKey(getenv func(string) string) string   // template global turnstile_site_key
type Verifier struct { Pool *pgxpool.Pool; Getenv func(string) string; Client *http.Client; URL string; Now func() time.Time }
func (v Verifier) Verify(ctx context.Context, r *http.Request, token, expectedAction string) (bool, error)
```

```go
token, _ := formLast(r, "cf-turnstile-response")
ok, err := turnstile.Verifier{Pool: d.pool, Getenv: d.getenv, Now: d.now}.Verify(r.Context(), r, token, "host_login")
if err != nil { serverError(w, err); return }
if !ok { /* render login.html with auth.error.turnstile, 403 */ }
```

**Login finish** (`go/internal/web/auth/finish.go`, package `auth`)

```go
const MethodLink, MethodLinkTOTP, MethodStagingPassword = "link", "link+totp", "staging_password"
const ActionLogin, ActionTwoFactorLogin = "login", "two_factor_login"
func MethodPasskey(passkeyID int64) string // "passkey:<id>"
func (d deps) finishLogin(w http.ResponseWriter, r *http.Request, account *session.LoginAccount,
	remember bool, nextPath, method, action string, at time.Time) error // _finish_login: cookies + 303
func (d deps) startSession(w http.ResponseWriter, r *http.Request, account *session.LoginAccount,
	remember bool, nextPath, method, action string, at time.Time) (location string, err error) // the same without the 303
func keepLoginLanguage(w http.ResponseWriter, r *http.Request, getenv func(string) string) // _keep_login_language
func safeLocalPath(value, def string) string // security.safe_local_path
func locationQuote(s string) string          // RedirectResponse's quoting of a Location
```

```go
// 1502 POST /login/link, account without TOTP:
if err := d.finishLogin(w, r, account, row.Remember != 0, next, MethodLink, ActionLogin, at); err != nil { serverError(w, err) }
// 1503 POST /login/2fa after a good code:
err := d.finishLogin(w, r, account, remembers(pending), next, MethodLinkTOTP, ActionTwoFactorLogin, at)
// 1511-1513 passkey finish (JSON answer, cookies kept on w):
loc, err := d.startSession(w, r, account, remember, next, MethodPasskey(passkeyID), ActionLogin, at)
writeJSON(w, http.StatusOK, map[string]string{"redirect": loc}) // plus Cache-Control: no-store
// 1507 POST /signup/verify (no device cookie, not remember):
_ = d.attach(w, id, sv, session.IssueOptions{}, at); keepLoginLanguage(w, r, d.getenv)
```

**Account mails** (`go/internal/mail`; each returns 0 when mail is off or the address is invalid; none sends)

```go
const KindLoginLink, KindAccountInvite, KindEmailConfirm = "login_link", "account_invite", "email_confirm"
const DeletionScheduled, DeletionWeekBefore = "scheduled", "week_before"
var ErrUnknownMail error
func QueueLinkMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, kind string,
	userID int64, toEmail, token string, minutes int, lang string, now time.Time) (int64, error)
func QueueEmailChanged(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64,
	oldEmail, newEmail, stamp, by string, notifyNew bool, now time.Time) (int, error)
func QueuePasskeyAdded(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64,
	toEmail string, passkeyID int64, name string, now time.Time) (int64, error)
func QueueWorkspaceDeletion(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	ownerUserID int64, dueAt, stage string, now time.Time) (int, error)
func BuildLinkMail(publicBaseURL, operatorEmail, kind, link string, minutes int, lang string) (Content, error)
func BuildEmailChanged(publicBaseURL, operatorEmail, side, newMasked, lang, by string) (Content, error)
func BuildPasskeyAdded(publicBaseURL, operatorEmail, name, lang string) Content
func BuildWorkspaceDeletion(publicBaseURL, operatorEmail, stage, date, lang string) (Content, error)
func FmtDate(value string) string // validation.fmt_date
```

```go
// 1502 POST /login (link_mail, then mail.send_now in the background):
id, err := mail.QueueLinkMail(ctx, d.pool, d.getenv, mail.KindLoginLink, account.ID, email, token,
	session.LinkTTL[session.PurposeLogin]/60, lang, at)
go func() { _ = mail.SendNow(context.Background(), d.pool, d.getenv, id) }()
// 1504 invite: mail.KindAccountInvite, session.LinkTTL[session.PurposeInvite]/60, lang "" (English)
// 1506 address change: mail.KindEmailConfirm to the new address, then on confirm
n, err := mail.QueueEmailChanged(ctx, d.pool, d.getenv, userID, oldEmail, newEmail, session.UTCNow(at), "self", false, at)
// 1509 deletion scheduled:
n, err := mail.QueueWorkspaceDeletion(ctx, d.pool, d.getenv, ownerID, dueAt, mail.DeletionScheduled, at)
// 1511-1513 passkey registered:
_, err := mail.QueuePasskeyAdded(ctx, d.pool, d.getenv, account.ID, email, passkeyID, name, at)
```
