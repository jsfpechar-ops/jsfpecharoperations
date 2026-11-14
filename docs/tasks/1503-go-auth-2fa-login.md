# 1503: Go auth, second login step (`POST /login/2fa`, dormant)

Status: review
Depends on: 1501, 1502 | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR, no `mcp__` tools. Commit after each step that changes a file with the message `1503 step k` (k = the step number), and the report as `1503 report`. The orchestrator opens the one PR. Sibling briefs 1502, 1504 to 1510 may have run before this one; every step here applies on top of them.

**Depends on, checked against go-wave3 at 859d114d5:** 1501 (built on this branch) gives `deps.finishLogin`, `MethodLinkTOTP`, `ActionTwoFactorLogin` (`go/internal/web/auth/finish.go` 30-35, 84) and `clientip.Key` (`go/internal/clientip/clientip.go` 108). 1502 gives the page (below). Already there from 1280/1282: `session.ReadTwoFactorPending` (`go/internal/session/issue.go` 254), `AccountByID` (`accounts.go` 69), `RateBlocked`, `RateRecord`, `Account2FABlocked`, `RecordAccount2FAFailure` (`loginlink.go` 176-246), `VerifySecondFactor` (`totp.go` 151), and in package `auth` `formStr`, `redirect`, `remembers`, `deps.audit` (`auth.go`) and `twoFactorLoginGet` (`admin.go` 56). Not 1504: no code of it is used. 1514 only empties `knownGaps` in `routes_test.go`; the helpers this test reuses stay.

## 1. Objective

Port `POST /login/2fa`, the authenticator or recovery code step after a login link, to `go/internal/web/auth`: the pending token, the login and per-account code limits (429), a wrong code (401, failure rows and the `two_factor_failed` audit), and the finished login (method `link+totp`, action `two_factor_login`). Go already answers `GET /login/2fa` (brief 1282) while Python answers the `POST`, so `/login/2fa` cannot be switched today; after this brief the whole path can. Tier A: it signs people in.

## 2. Context

Rules (AGENTS.md): 2 privacy (no new personal-data field, no outbound request); 3 nothing real in the repo (test secret, `@example.test`); 4 no new dependency; 5 SQL with Postgres placeholders, no schema change; 6 the form works without JavaScript (the page is 1502's); 11 go-first: `App/scripts/login_2fa_golden.py` is port plumbing (go-first exception 1, golden scripts). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1503-files/` mirrors the repo paths with `.txt` added. Step 1 copies them and checks their sha256. Never type or edit the code. `docs/tasks/1503-files/edit_routes.py` is run, not copied.

**Python source of truth** (`App/app/routes/admin_accounts.py` 275-316 `two_factor_login`; `App/app/rate_limit.py` 8-11 limits, 66-76 `login_blocked`/`record_login_failure`, 114-121 `client_key`), in this order, as `deps.twoFactorLogin` (`go/internal/web/auth/login_2fa.go`) does it:

1. Host CSRF check (`security.protect_host_post`; `hostweb.CSRF`).
2. `read_two_factor_pending(form pending, stripped)`: none (bad signature, other salt, older than 10 minutes, no `uid`) is a 303 to `/login?notice=2fa_expired`.
3. The account `WHERE id = uid AND active = 1`; none is a 303 to `/login`.
4. `login_blocked(client_key(request, "<username>:2fa"), client_key(request))` (scope `login_fail` 12 per 15 minutes, then `login_fail_ip` 30 per 15 minutes, each check pruning old rows first), then `account_2fa_blocked` (`2fa_fail_account` 10 per 15 minutes): the page with `auth.error.code_locked`, status 429. Nothing is recorded.
5. `verify_second_factor(account, code)` false: `login_fail` and `login_fail_ip` rows, a `2fa_fail_account` row, audit `two_factor_failed` (no detail, actor the username, owner the account, no actor id), the page with `auth.error.code_invalid`, status 401.
6. Else `_finish_login(remember=bool(pending["rm"]), next_path=str(pending.get("next") or "/"), method="link+totp", action="two_factor_login")`: 303 to the safe local path, session, device and (when it differs) language cookies, `last_login_at`, audit row (brief 1501's `finishLogin`).

The page answers carry `Cache-Control: no-store, private` (main.go's default, as Python's middleware), not the `no-store` of `POST /login/link`. The address comes from `clientip.Key` (CF-Connecting-IP only behind a trusted proxy); brief 1502's owner steps add `UBYHOST_TRUSTED_PROXY_CIDRS` to the Go service before any login path is switched.

**Needs from 1502 (the reason for `Depends on`).** The page `two_factor_login.html` on `auth_base.html` is rendered by brief 1502 (its `POST /login/link` shows it after a good link; `docs/tasks/1502-files/go/internal/web/auth/login.go.txt` 518, on `authpage.Render`). This brief calls, from package `auth`:

```go
// renderTwoFactorLogin writes two_factor_login.html with the given pending
// token (already stripped) in both hidden "pending" fields and, when
// errorKey is not "", the auth-alert box with t(errorKey) (plus the
// "log in again" link for auth.error.code_locked), as Python renders it.
// It sets Content-Type text/html; charset=utf-8 and writes status; it does
// not set Cache-Control; it sets no cookie when the request carries the
// CSRF nonce cookie.
func (d deps) renderTwoFactorLogin(w http.ResponseWriter, r *http.Request, pending, errorKey string, status int) error
```

The golden test checks that contract against Python: the text of `<div class="auth-alert" role="alert">...</div>` byte for byte, two `<input type="hidden" name="pending" value="<token>">` fields, the Content-Type, Cache-Control and cookie list; the rest of the page markup is 1502's to prove.

**Differences from Python, on purpose or inherited:**
1. A database error answers a plain 500 (`serverError`), where Python shows its error page.
2. A pending `uid` that is not an integer matches no account (Python would pass it to SQL as is); only the server signs these tokens.
3. Shared with every Go POST, not fixed here (read-only `go/internal/hostweb/gate.go` 242-244, reported for the hostweb owner): when the CSRF check fails and the Referer has a query, Go re-encodes it sorted (`?err=...&t=abc`), Python keeps its order (`?t=abc&err=...`). The golden uses a Referer without a query.

**Verified by the brief writer** in throwaway worktrees of go-wave3 at 859d114d5, PostgreSQL 16 on a disposable port. With brief 1502's Go files and route edits applied first exactly as its steps 1 and 3 copy them (route count 22 to 23): `go build ./...`, `go vet` clean and `go test ./internal/web/auth/... ./cmd/ubyhost-web/` all `ok`, 0 skipped, so its real `renderTwoFactorLogin` meets the contract. Before 1502 existed, with a stand-in renderer: `gofmt -l` empty, `go build ./...`, `go vet ./internal/web/auth/ ./cmd/ubyhost-web/` clean, `TestLogin2FAGoldenDatabase` (24 cases) and `./internal/web/auth/ ./internal/session/ ./cmd/ubyhost-web/` all `ok` on the database, 0 skipped; the golden regenerated from Python passes too. Also verified with brief 1504 applied first (route count 21 to 22) and alone (18 to 19). Mutations caught: login limit 13, address limit 31, client key `-2fa`, audit with a detail, 429 as 401, method `link`, remember dropped, `/login` as `2fa_expired`, pending not stripped, failure rows not written.

Anchors (step 0; each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `App/app/routes/admin_accounts.py` | `async def two_factor_login(request: Request):` |
| `App/app/rate_limit.py` | `_LOGIN_MAX_FAILURES = 12` |
| `App/app/rate_limit.py` | `_LOGIN_IP_MAX_FAILURES = 30` |
| `go/internal/web/auth/finish.go` | `func (d deps) finishLogin(w http.ResponseWriter, r *http.Request, account *session.LoginAccount,` |
| `go/internal/session/issue.go` | `func ReadTwoFactorPending(secret, token string, now time.Time) (map[string]any, bool) {` |
| `go/internal/session/totp.go` | `func VerifySecondFactor(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, account *LoginAccount, code string, now time.Time) (bool, error) {` |
| `go/internal/clientip/clientip.go` | `func Key(r *http.Request, getenv func(string) string, suffix string) string {` |
| `go/internal/web/auth/auth.go` | `func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {` |
| `go/internal/web/auth/auth_test.go` | `func TestRoutesBuildWithoutPool(t *testing.T) {` |
| `go/internal/web/auth/routes_test.go` | `func loadSeed(t *testing.T, ctx context.Context, pool *pgxpool.Pool, seed [][2]any, now time.Time) {` |
| `App/scripts/auth_routes_golden.py` | `def run(case, seed):` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/login_2fa.go` | create (copy) | `twoFactorLogin`, `loginBlocked`, `recordLoginFailure`, `pendingUserID`, `pendingNext` |
| `go/internal/web/auth/login_2fa_test.go` | create (copy) | golden replay on PostgreSQL, route list, pending helpers |
| `go/internal/web/auth/testdata/login_2fa.json` | create (copy) | golden, from Python |
| `go/cmd/ubyhost-web/register_web_auth_login_2fa_test.go` | create (copy) | the mux serves `GET` and `POST /login/2fa` |
| `App/scripts/login_2fa_golden.py` | create (copy) | writes the golden from the real FastAPI route |
| `go/internal/web/auth/auth.go` | edit (script) | one row appended at the end of `Routes` |
| `go/internal/web/auth/auth_test.go` | edit (script) | route count +1 |
| `docs/tasks/1503-go-auth-2fa-login.md` | edit | the Status line |
| `docs/tasks/1503-report.md` | create | the report |

`docs/tasks/1503-files/` is part of this brief; do not edit it. No other file may change. No catalog key is added (`auth.error.code_locked` and `auth.error.code_invalid` are in `i18n_keys.txt` since 1282; the page strings are 1502's).

## 4. Steps

0. Checks (from the repo root, one call):

```bash
git status --short | tail -5; ls go/internal/web/auth/login_2fa.go go/internal/web/auth/login_2fa_test.go go/internal/web/auth/testdata/login_2fa.json go/cmd/ubyhost-web/register_web_auth_login_2fa_test.go App/scripts/login_2fa_golden.py 2>&1 | grep -c 'No such file'; grep -c 'd.twoFactorLogin}' go/internal/web/auth/auth.go
grep -lF 'func (d deps) renderTwoFactorLogin(w http.ResponseWriter, r *http.Request, pending, errorKey string, status int) error {' go/internal/web/auth/*.go | wc -l
cd docs/tasks/1503-files && sha256sum -c <<'EOF' 2>&1 | tail -6
173240ad87c9dd39753447daeca736d0f1f61b8e08f2fe69f928c82efe45977a  App/scripts/login_2fa_golden.py.txt
ddac8290097bb6eed138984e8132fb8263ca93aabb4f3b3d0a94de718eaa38a5  edit_routes.py
aa43a7248866964117928ad7303195b1e0d367efe7d325688171aa64005cb687  go/cmd/ubyhost-web/register_web_auth_login_2fa_test.go.txt
764f18d6eb9b6437e4545ae11dd3b2d917b43ff3814883679724996cac2b8c25  go/internal/web/auth/login_2fa.go.txt
a0330edbea0845f10c6fe124b183656cf0f5d7c251fe338946ae4531cad380b5  go/internal/web/auth/login_2fa_test.go.txt
60710100491d86aa1d9e9da88df4f7c8fcbed479b2f761b80b0c0bace75948f3  go/internal/web/auth/testdata/login_2fa.json.txt
EOF
```

   Expected: `git status` prints nothing (uncommitted files of another brief: STOP and ask), then `5`, `0`, then `1` (brief 1502's renderer exists; `0`: STOP, 1502 has not run), then six `OK` lines. Then check every anchor of section 2 with `grep -cF '<anchor>' <file>` (one call, eleven commands joined with `;`): eleven `1`. Anything else: STOP (section 8). No commit for step 0.

1. Copy the files and build (from the repo root):

```bash
cd docs/tasks/1503-files && for f in $(find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && git status --short | tail -6
cd go && gofmt -l internal/web/auth cmd/ubyhost-web 2>&1 | tail -3; go build ./... 2>&1 | tail -5
```

   Expected: `git status` shows exactly the five `??` lines of the created files in section 3; no gofmt or build output (`go: downloading` lines are fine). Commit `1503 step 1`.

2. Register the route (from the repo root):

```bash
python3 docs/tasks/1503-files/edit_routes.py 2>&1 | tail -3
git diff go/internal/web/auth/auth.go | grep '^[-+]' | grep -v '^[-+][-+]'; git diff --stat | tail -3
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ ./cmd/ubyhost-web/ 2>&1 | tail -5
```

   Expected: `added 1 row` and `route count N -> N+1` (N is 18 if no sibling brief added a route, more otherwise); the `auth.go` diff is exactly the one line `+		{"POST /login/2fa", "/login/2fa", d.twoFactorLogin},` as the last row of `Routes`; the stat lists `auth.go` (1 insertion) and `auth_test.go` (2 lines changed); no gofmt or vet output. The script printing an `AssertionError`: STOP. Commit `1503 step 2`.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55503/data status' | tail -1` says `server is running`:

```bash
mkdir -p /var/tmp/pg55503 && chown postgres /var/tmp/pg55503 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55503/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55503/data -o "-p 55503 -k /var/tmp/pg55503" -l /var/tmp/pg55503/log start' 2>&1 | tail -3
```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report, run section 6 without the database, and set the report `blocked`. Then run the tests (from the repo root):

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres go test ./internal/web/auth/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestLogin2FAGoldenDatabase$|^TestLogin2FARoutes$|^TestPendingHelpers$|^TestRoutesBuildWithoutPool$|^TestAuthLogin2FARoutesRegistered$' 2>&1 | grep -E '^(--- |ok|FAIL)|SKIP' | tail -12
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres go test ./internal/web/auth/ -count=1 -v -run '^TestLogin2FAGoldenDatabase$' 2>&1 | grep -c '^    --- PASS'
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres go test ./internal/web/auth/... ./internal/session/... ./cmd/ubyhost-web/... -count=1 2>&1 | grep -v ' INFO ' | tail -10
```

   Expected: five `--- PASS` lines and two `ok` lines, no `SKIP`; then `24`; then only `ok` lines. A failing `alert`, `pending fields`, `Content-Type`, `Cache-Control` or cookie line in `TestLogin2FAGoldenDatabase` means 1502's renderer breaks the contract of section 2: STOP and report the case names (do not change any file). No commit (nothing changed).

4. Check the golden against Python once more (from the repo root): regenerate it, replay it, then put the committed one back. If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5; cd ..`. The regenerated file differs in bytes (cookie times rounded to the second, a fresh encrypted seed value), so its hash is not checked; the replay is the check.

```bash
cd App && .venv/bin/python scripts/login_2fa_golden.py 2>&1 | grep -v ' INFO ' | tail -3; cd ..
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55503/postgres go test ./internal/web/auth/ -count=1 -run '^TestLogin2FAGoldenDatabase$' 2>&1 | grep -v ' INFO ' | tail -5; cd ..
git checkout -- go/internal/web/auth/testdata/login_2fa.json && git status --short | tail -3
```

   Expected: `wrote go/internal/web/auth/testdata/login_2fa.json`, then `ok`, then `git status` prints nothing. A failure here, when step 3 passed, means Python changed since the brief was written: STOP and report the failing case names. No commit.

5. Run section 6. Write the report (section 9), set `Status: review` in this file and commit both as `1503 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/` (including the CSRF recovery order of section 2), `go/internal/session/`, `go/internal/clientip/`, `go/internal/mail/`, `go/internal/jobs/`, every existing file in `go/internal/web/auth/` except the appended `Routes` row of `auth.go` and the two count lines of `auth_test.go` (in particular `finish.go`, `admin.go` with `twoFactorLoginGet`, `routes_test.go`, `testdata/routes.json`, `i18n_keys.txt`, `i18n.json`, and every file brief 1502 created), `go/cmd/ubyhost-web/` except the new test file, `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/`, `App/scripts/auth_routes_golden.py`, `deploy/` (no `UBYHOST_GO_PATHS` change), `docs/context/`, `docs/tasks/1503-files/`. Never print a secret, token or code from a real system. Rules 2, 3, 4, 5, 6 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/web/auth cmd/ubyhost-web 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/web/auth/... ./cmd/ubyhost-web/... 2>&1 | tail -30` prints nothing.
- The three test commands of step 3, with the outputs stated there (0 skipped; report the `SKIP` count, which must be 0).
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1503.

Test-map: no row covers these Go packages; the commands above are this brief's tests. No catalog changes, so no pytest.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1503 '` lists steps 1, 2 and the report.
- [ ] `for c in $(git log --format=%h --grep='^1503 '); do git show --name-only --format= $c; done | sort -u` lists exactly the files of section 3.
- [ ] The copied files equal the sidecar: `cd docs/tasks/1503-files && for f in $(find . -name '*.txt' | sed 's|\.txt$||'); do cmp $f.txt ../../../$f; done` prints nothing.
- [ ] Step 3 printed five `--- PASS`, `24`, only `ok` lines and no `SKIP`; step 4 printed `ok`.
- [ ] `for c in $(git log --format=%h --grep='^1503 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|App/tests/|hostweb/|session/|clientip/|deploy/|routes_test\.go|routes\.json|i18n'` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, the renderer of 1502 is missing, or `edit_routes.py` raises;
- a test fails twice (never change the code: it is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1503-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/login_2fa.go`: the order of section 2 (CSRF, pending, account, limits, code, finish); the limits 12 / 30 / 10 per 15 minutes and the keys (`<address>:<username>:2fa`, `<address>`, the account id); nothing is recorded on a 429; the three failure rows and the audit row on a 401; `remembers(pending)` and `pendingNext`; no code, token or address is logged.
- `go/internal/web/auth/login_2fa_test.go` and `App/scripts/login_2fa_golden.py`: the pending token is minted on each side with the same payload; the page is compared on the alert text and the echoed token only; the request peer is `testclient` on both sides so the rate-limit keys match.
- `go/internal/web/auth/auth.go`: only the appended row. `auth_test.go`: only the count.
- Verified by the brief writer (see section 2): build, vet, 24 golden cases on PostgreSQL 16 with 0 skipped, against 1502's real renderer and a stand-in; regenerated golden green, ten mutations caught; applied alone, after 1504 and after 1502.

## Owner steps

1. Nothing for this brief alone: it is merged with the one big PR and changes nothing in production (no route is switched, no environment change).
2. To switch it, after the deploy and only together with brief 1502's `/login` and `/login/link` (the 2FA page is reached from `POST /login/link`, and brief 1502's owner steps add `TURNSTILE_*` and `UBYHOST_TRUSTED_PROXY_CIDRS` to the Go service first): on the server, add `/login/2fa` inside the double quotes of `UBYHOST_GO_PATHS` in `.env` (space-separated, see `docs/ENVIRONMENT.md`), from `deploy/lightsail` run `./scripts/caddy-validate.sh`, then `docker compose up -d caddy`. Rollback: remove it again and run the same two commands.
3. Then, with a test account that has an authenticator: log in by link, type a wrong code once and check the page says the code did not work, then type the right code and check you land signed in.
