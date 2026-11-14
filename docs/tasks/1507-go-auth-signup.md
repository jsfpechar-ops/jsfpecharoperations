# 1507: Go sign-up pages (dormant): GET/POST `/signup`, GET/POST `/signup/verify`

Status: review
Depends on: 1501 (Turnstile check, client address, `loginLanguage`, `keepLoginLanguage`; built on go-wave3) | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 14 calls)

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR, no `mcp__` tools. Commit after each step that changes a file with the message `1507 step k` (k = the step number), and the report as `1507 report`. Sibling briefs 1502 to 1506 may have run before this one; every step here is written to apply on top of them.

## 1. Objective

Serve the self sign-up form, its "check your e-mail" page and the confirmation link (`App/app/routes/signup.py` 24-174, templates `signup.html`, `signup_sent.html`, `signup_verify.html` on `auth_base.html`) from `go/internal/web/auth`, with Python's status codes (403, 429, 400, 422, 410, 303), budgets, audit row, cookies and page bytes. Tier A (accounts and a session cookie): the code is dormant until the owner lists `/signup` and `/signup/verify` in `UBYHOST_GO_PATHS`, and every page is proven equal to the Python page by goldens from the real Python routes.

## 2. Context

Rules (AGENTS.md): 2 privacy (no new cookie, field or outbound request: the Turnstile POST is 1501's, already in its PR text; the page loads only the Turnstile script Python loads, and only when Turnstile is configured); 3 nothing real in the repo (test secrets and example addresses only); 4 no new dependency (`go/go.mod` unchanged); 5 SQL with Postgres placeholders, no schema change; 6 the forms work without JavaScript; 11 go-first: `App/scripts/signup_pages_golden.py` and `App/tests/test_go_signup_pages.py` are port plumbing (go-first exception 1, golden script and parity test). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1507-files/` mirrors the repo paths with `.txt` added; `docs/tasks/1507-files/SHA256SUMS` lists the 46 copied files. You only copy them, check the hashes and run two small step scripts (`docs/tasks/1507-files/steps/`). Never type or edit the code.

**What Python does** (checked at 859d114d5):

- `signup.py` 66-72 `GET /signup`: 404 (`HTTPException`) while `UBYHOST_SIGNUP_ENABLED` is off; a signed-in visitor gets 303 to `/`; else the form with `signup.attribution(query, mint=True)` (raw `gclid`/`gbraid`/`wbraid`/`fbclid` are signed into a `click` value) and `_form_context` (39-63: hidden `click` and `utm_*` fields, the plan choices of `signup_selection.clean` in the order plan, interval, ttlock, apartments, one unticked consent box per ad platform of a valid click, Meta only when the Conversions API is configured, and `lang_next = signup.signup_href(lang, {**attr, **selection})` for the language switch; the form language is `resolve_language(request, default="cs")`).
- 75-136 `POST /signup`: the host CSRF check first (the router is included from `admin.router`), then 404 when off; Turnstile action `host_signup` (403, `signup.error.turnstile`); `rate_limit.client_key` and `signup.rate_limited` (10 per IP and 3 per address per hour: 429, `signup.error.rate_limited`), then the attempt is recorded before any field check; empty or invalid address 400 (`signup.error.email`, field `email`); no workspace name: `_workspace_from_email` (24-31); over 120 characters 400 (`signup.error.workspace`); `accept` not `1` 422 (`signup.error.accept`). The form comes back with what was typed (`form_str(email)[:254]`, the boxes ticked as posted). Then `signup.register(...)` and the same `signup_sent.html` whatever it found (no account enumeration).
- 139-146 `GET /signup/verify`: `signup.pending_account(t)`: none (forged, older than 24 h, superseded by a newer link, used) is `signup_verify.html` with `expired` and **410**; else the form with the token.
- 149-174 `POST /signup/verify`: CSRF, 404 when off; `login_link.consume_blocked(ip)` (20 bad links per 15 minutes) 429 with `signup.verify.locked`; no pending account or `signup.activate` lost the race: one bad link recorded and 410; else `attach_session(issue_session(id, sv))` (not remembered, no device cookie), `_keep_login_language`, `db.audit("login", "method=signup_link", actor=username, owner_user_id=id)`, 303 to `/`.
- `templating.render` 695-799 for these pages: `lang` is the last `?lang=`, then the `ubyhost_lang` cookie, else Czech (English for a signed-in visitor); none of the paths is in `seo.INDEXABLE_PATHS`, so `vi` stays `vi`; a `?lang=` that differs from the cookie sets `ubyhost_lang` (180 days, Lax, not HttpOnly, Secure on an https public base); the CSRF cookie (middleware, `main.py` 337) comes after it. `auth_base.html` 1-97 is the shell (language form, env banner while `UBYHOST_UBYPORT_ENV` is `mock`, `?notice=` line, "not you" form for a signed-in visitor, footer, hero).

**What the Go code reuses** (each verified at 859d114d5): `hostweb.CSRF` (`go/internal/hostweb/gate.go` 138); `deps.current` 134, `deps.audit` 264, `deps.attach` 308, `httpError`, `redirect`, `formStr`, `formLast`, `pySpace`, `pyStrip` (`go/internal/web/auth/auth.go`); `normaliseEmail` (`account.go` 204); 1501's `loginLanguage` 99, `supportedLanguage` 114, `keepLoginLanguage` 131, `langCookieName`, `langCookieMaxAge` (`finish.go`), `clientip.Key` 108, `clientip.Host` 94, `turnstile.Verifier.Verify` 142, `turnstile.PageSiteKey` 113, `turnstile.FromEnv`; brief 1281's `signup.Enabled`, `Attribution` 225, `CleanSelection` 265, `ClickPlatforms` 203, `ReadClick` 146, `RateLimited` 99, `RecordAttempt` 108, `Register` 315, `PendingAccount` 83, `Activate` 484 and `mail/auth_signup.go` (through `Register`, `Activate`); `session.LinkConsumeBlocked` 228, `LinkRecordConsumeFailure` 233, `IssueOptions`.

**What each new file does:**

- `go/internal/web/auth/signup_pages.go`: the four handlers in Python's order, `signupFormView` (`_form_context`), `signupHref` (`signup_href`), `signupWorkspaceFromEmail`, `signupInput` and its `check` (the field checks), `signupVerifyView`. Every helper name starts with `signup` so no sibling brief's name can clash.
- `go/internal/web/auth/signup_render.go`: `renderSignup`, the auth shell with markupsafe escaping (`text/template`, every value through `E` or `T`), the page language, the CSRF token (a copy of `go/internal/hostweb/layout`'s unexported `csrfToken`, which this package cannot call), the cookie order. Strings come from the embedded `signup_catalog.json`.
- `go/internal/web/auth/templates/signup/*.tmpl`: `auth_base.html` and the three page templates, line for line.
- `signup_catalog.json`, `testdata/signup/cases.json` and 35 `testdata/signup/<case>.html`: written by `App/scripts/signup_pages_golden.py`, which runs the real routes with the FastAPI TestClient on a throwaway SQLite database (it reuses `App/scripts/public_legal_golden.py`) and records the page, the status, the cookies, the context the route gave `render()` and the arguments it gave `register()`. Only the Turnstile answer, the budget answers, `register`, `pending_account`, `activate` and the click clock are replaced. 39 cases.
- `go/internal/web/auth/signup_pages_test.go`: `TestSignupPagesMatchPython` (no database: Go's context against Python's, the `RegisterInput` against `register()`'s arguments, the page byte for byte after the script's normalisation, the cookies; the "off" 404s run the real handlers), `TestSignupWorkspaceFromEmail`, and `TestSignupDatabase` (PostgreSQL, end to end: pending account, both budget rows, three acceptance rows with the client address, the `signup_verify` mail and its decrypted link token, the verify form, 410, activation with the session and language cookies and the `login`/`method=signup_link` audit row with no actor id, the second use 410 plus one bad link, 429 at 20 bad links, the signed-in redirect, 429 at 10 attempts, Turnstile 403 in production before any budget row).
- `App/tests/test_go_signup_pages.py`: fails when the Python pages or copy change and the goldens were not rewritten (`--check`), as `test_go_public_pages.py` does.

**Shared live files** (edited by the step scripts, which work after any sibling brief):

- `go/internal/web/auth/auth.go` `Routes`: four rows appended after the last row of the slice (`steps/routes.py`: anchor `\t}\n}\n\ntype deps struct {`, stops if a `GET /signup` row exists already).
- `go/internal/web/auth/auth_test.go` `TestRoutesBuildWithoutPool`: the route count read from the file and raised by 4 (18 at 859d114d5; more if a sibling added routes).
- `deploy/lightsail/docker-compose.yml`, service `ubyhost-go`: the bare keys `UBYHOST_SIGNUP_ENABLED`, `UBYHOST_SIGNUP_NOTIFY_EMAIL` and, unless brief 1502 added them already, `UBYHOST_TRUSTED_PROXY_CIDRS`, `TURNSTILE_HOSTNAMES`, `TURNSTILE_SECRET`, `TURNSTILE_SITE_KEY`; the comment "(no SES/AWS, Turnstile, Grafana or backup secrets)" loses "Turnstile, " (`steps/compose_env.py`, adds only missing keys). Without them the Go sign-up would answer 404 (`UBYHOST_SIGNUP_ENABLED` unset), skip Turnstile in production and count every visitor under Caddy's address. A bare key passes nothing while `.env` lacks it, so nothing changes on deploy.

**Differences from Python, on purpose** (put them in the PR text):

1. 404 while sign-up is off is the JSON `{"detail":"Not Found"}` for every client; Python shows its `error.html` page to a browser (`main.py` 261-275). Every Go port so far does the same (`web/customers`, `web/billing`); the switch happens only while sign-up is on.
2. A click value with ids of two platforms is long enough for itsdangerous to zlib-compress it; Go's zlib bytes differ from Python's (`signup.IssueClick`, brief 1281). Both sign the same ids and time and each side reads the other's (the golden case `submit-no-accept-en` posts a Python value to Go); the test compares such values by content.
3. The address goes through the package's `normaliseEmail` (a bare address or `Name <addr>`), not `email.utils.parseaddr`; exotic forms Python would accept give "invalid address" (400).
4. On a good confirmation the audit row is written before the cookies, so a failed write sets no cookie (Python discards its response on the same error: the browser sees the same 500).

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints the number shown):

| File | Anchor | Count |
|---|---|---|
| `go/internal/web/auth/finish.go` | `func keepLoginLanguage(w http.ResponseWriter, r *http.Request, getenv func(string) string) {` | 1 |
| `go/internal/web/auth/finish.go` | `func loginLanguage(r *http.Request) string {` | 1 |
| `go/internal/web/auth/auth.go` | `func (d deps) attach(w http.ResponseWriter, userID, sv int64, opt session.IssueOptions, at time.Time) error {` | 1 |
| `go/internal/web/auth/account.go` | `func normaliseEmail(raw string) string {` | 1 |
| `go/internal/turnstile/turnstile.go` | `func PageSiteKey(getenv func(string) string) string {` | 1 |
| `go/internal/clientip/clientip.go` | `func Key(r *http.Request, getenv func(string) string, suffix string) string {` | 1 |
| `go/internal/signup/register.go` | `func Activate(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, a *Account, now time.Time) (bool, error) {` | 1 |
| `go/internal/session/loginlink.go` | `func LinkConsumeBlocked(ctx context.Context, db *pgxpool.Pool, ipKey string, now time.Time) (bool, error) {` | 1 |
| `App/app/routes/signup.py` | `db.audit("login", "method=signup_link", actor=refreshed["username"], owner_user_id=refreshed["id"])` | 1 |
| `App/scripts/public_legal_golden.py` | `def config_values(env: dict) -> dict:` | 1 |
| `deploy/lightsail/docker-compose.yml` | `  ubyhost-go:` | 1 |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/signup_pages.go` | create (copy) | the four handlers and the form logic |
| `go/internal/web/auth/signup_render.go` | create (copy) | the auth shell renderer |
| `go/internal/web/auth/signup_pages_test.go` | create (copy) | golden, unit and PostgreSQL tests |
| `go/internal/web/auth/signup_catalog.json` | create (copy, regenerated) | strings and the check icon |
| `go/internal/web/auth/templates/signup/auth_base.tmpl`, `signup.tmpl`, `signup_sent.tmpl`, `signup_verify.tmpl` | create (copy) | the templates |
| `go/internal/web/auth/testdata/signup/cases.json` and the 35 `*.html` | create (copy, regenerated) | goldens |
| `App/scripts/signup_pages_golden.py` | create (copy) | writes the catalog and goldens from the real Python |
| `App/tests/test_go_signup_pages.py` | create (copy) | the goldens are current |
| `go/internal/web/auth/auth.go` | edit (step script) | four rows at the end of `Routes` |
| `go/internal/web/auth/auth_test.go` | edit (step script) | route count + 4 |
| `deploy/lightsail/docker-compose.yml` | edit (step script) | bare env keys of `ubyhost-go`, one comment |
| `docs/tasks/1507-go-auth-signup.md` | edit | `Status:` line only |
| `docs/tasks/1507-report.md` | create | the report |

`docs/tasks/1507-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (repo root, one call):

```bash
git status --short | grep -v '^?? docs/tasks/' | tail -5; ls go/internal/web/auth/signup_pages.go go/internal/web/auth/templates/signup App/scripts/signup_pages_golden.py 2>&1 | grep -c 'No such file'; grep -c '"GET /signup"' go/internal/web/auth/auth.go
cd docs/tasks/1507-files && sed 's/$/.txt/' SHA256SUMS | sha256sum -c --quiet 2>&1 | tail -5; echo "sidecar check done"
```

   Expected: no `git status` line (another brief's uncommitted code: STOP and ask), `3`, `0`, then only `sidecar check done` (a `FAILED` line: STOP). Then check the eleven anchors of section 2 with `grep -cF '<anchor>' <file>` (one call, joined with `;`): eleven `1`. Anything else: STOP (section 8). No commit for step 0.

1. Copy the files and check them (repo root):

```bash
cd docs/tasks/1507-files && for f in $(awk '{print $2}' SHA256SUMS); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done && cd ../../.. && sha256sum -c --quiet docs/tasks/1507-files/SHA256SUMS 2>&1 | tail -5; echo "copied $(wc -l < docs/tasks/1507-files/SHA256SUMS)"
```

   Expected: only `copied 46`. Note `sha256sum -c` runs from the repo root, where the paths in `SHA256SUMS` resolve. Commit `1507 step 1`.

2. Wire the routes (repo root):

```bash
python3 docs/tasks/1507-files/steps/routes.py.txt 2>&1 | tail -3; cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go build ./... 2>&1 | tail -5; go vet ./internal/web/auth/ 2>&1 | tail -5
```

   Expected: `routes: 4 rows appended; count N -> N+4` (N is 18 if no sibling added routes), then nothing. A line starting `STOP:`: STOP (section 8). Commit `1507 step 2`.

3. Pass the variables to the Go service (repo root):

```bash
python3 docs/tasks/1507-files/steps/compose_env.py.txt 2>&1 | tail -3; git diff --stat deploy/ | tail -2
```

   Expected: `added: ...` naming `UBYHOST_SIGNUP_ENABLED UBYHOST_SIGNUP_NOTIFY_EMAIL` and the keys brief 1502 had not added, then one changed file. Commit `1507 step 3`.

4. Start a PostgreSQL 16 for the database tests (any directory):

```bash
mkdir -p /var/tmp/pg1507 && chown postgres /var/tmp/pg1507 && su postgres -c 'cd /tmp && /usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1507/data -A trust -U postgres >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1507/data -o "-p 55507 -k /var/tmp/pg1507" -l /var/tmp/pg1507/log start' 2>&1 | tail -3
```

   Expected: `server started`. A server already on port 55507 (an earlier try of this brief): use it. No PostgreSQL 16 binaries at that path: STOP (the database tests must run, 0 skipped). No commit.

5. Run section 6. If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt 2>&1 | tail -5; cd ..`. Write the report (section 9), set `Status: review`, commit `1507 report`. Stop the database: `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1507/data stop' 2>&1 | tail -1`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/` (including `layout/`), `go/internal/jobs/`, `go/internal/signup/`, `go/internal/session/`, `go/internal/turnstile/`, `go/internal/clientip/`, `go/internal/mail/`, every existing file of `go/internal/web/auth/` except the two lines the step script changes in `auth.go` and `auth_test.go` (`routes_test.go`, `finish.go`, `i18n.json`, `i18n_keys.txt`, `testdata/routes.json` stay), `go/cmd/ubyhost-web/` (the routes register through the existing `register_web_auth.go`), `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/conftest.py` and every other existing test, `App/scripts/public_legal_golden.py`, `docs/context/*`, `docs/ENVIRONMENT.md`, `docs/tasks/1507-files/`. No `UBYHOST_GO_PATHS` change. Never print a secret, a token, a link or an e-mail address from a database. Rules 2, 3, 4, 5, 6 and 11 as in section 2.

## 6. Commands

From the repo root (each ends with `2>&1 | tail -30`):

- `cd go && gofmt -l internal/web/auth 2>&1 | tail -30` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` and `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` print nothing.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55507/postgres go test -count=1 -v ./internal/web/auth/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`: every line `--- PASS` or `ok`, among them `TestSignupPagesMatchPython`, `TestSignupWorkspaceFromEmail`, `TestSignupDatabase` and `TestRoutesBuildWithoutPool`; no `--- SKIP` and no `FAIL`. Report the SKIP count (must be 0).
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55507/postgres go test -count=1 ./internal/signup/... ./internal/turnstile/... ./internal/clientip/... ./internal/session/... ./cmd/ubyhost-web/... 2>&1 | tail -30` prints only `ok` lines.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `cd App && .venv/bin/python scripts/signup_pages_golden.py --check > /tmp/1507-golden.log 2>&1; echo rc=$?; tail -5 /tmp/1507-golden.log` prints only `rc=0` (a `stale:` line: STOP, Python differs from what the Go code was proven against).
- `cd App && .venv/bin/python -m pytest tests/test_go_signup_pages.py tests/test_go_auth_routes.py tests/test_go_public_pages.py -q --tb=short -x 2>&1 | tail -30` passes (test-map: these are the parity tests of the touched Go package and of the golden script it reuses).
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1507.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1507 step'` lists steps 1, 2 and 3 (and `--grep='^1507 report'` the report).
- [ ] `for c in $(git log --format=%h --grep='^1507 '); do git show --name-only --format= $c; done | sort -u` lists exactly the 46 files of `SHA256SUMS`, `go/internal/web/auth/auth.go`, `go/internal/web/auth/auth_test.go`, `deploy/lightsail/docker-compose.yml`, `docs/tasks/1507-go-auth-signup.md` and `docs/tasks/1507-report.md`.
- [ ] `sha256sum -c --quiet docs/tasks/1507-files/SHA256SUMS` prints nothing (run from the repo root).
- [ ] `git show --format= $(git log --format=%h --grep='^1507 step 2') -- go/internal/web/auth/auth.go | grep -c '^+'` prints `5` (the file header line plus four rows) and `| grep -c '^-[^-]'` prints `0`.
- [ ] Section 6 output exactly as stated, 0 skipped.
- [ ] `for c in $(git log --format=%h --grep='^1507 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|hostweb/|cmd/ubyhost-web/|internal/signup/|internal/session/'` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, a step script prints `STOP:`, or `--check` prints `stale:`;
- a test fails twice (never change the code: it is fixed by hash);
- a database test skips (`UBYHOST_TEST_DATABASE_URL` not reaching the server);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1507-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/signup_pages.go`: the gate order (CSRF, 404, Turnstile, budget, record, fields, register); the attempt recorded before the field checks; the same `signup_sent` page whatever `Register` found; `signupVerifySubmit`: blocked check first, one bad link per failed confirmation, audit before cookies, no device cookie, not remembered, 303 to `/` only.
- `go/internal/web/auth/signup_render.go`: every value escaped (`E`, `T`, `TP`; nothing raw except the check icon from the catalog), the language for signed-in and signed-out visitors, the cookie order and attributes, the Turnstile script only with a site key.
- `go/internal/web/auth/templates/signup/signup.tmpl`: no field from the request outside `E`.
- `App/scripts/signup_pages_golden.py`: runs the real routes; only Turnstile, the budget answers, `register`, `pending_account`, `activate` and the click clock are replaced; the CSRF mask covers only the two token attributes.
- The step scripts' result in `auth.go`, `auth_test.go` and `docker-compose.yml`.

Verified by the brief writer in a throwaway worktree of 859d114d5 (`/var/tmp/wt-1507`, removed afterwards) with exactly these files and step scripts, PostgreSQL 16 on port 55507: `gofmt -l` empty, `go build ./...`, `go vet ./internal/... ./cmd/...` clean, `go mod tidy -diff` empty; `go test -count=1 -v ./internal/web/auth/` all PASS with the database (0 skipped), and `./internal/signup/... ./internal/turnstile/... ./internal/clientip/... ./cmd/ubyhost-web/...` ok; the golden script run twice gives the same files (`--check` rc 0); `test_go_signup_pages.py` and `test_go_public_pages.py` pass; both step scripts run twice (the second run of `routes.py` stops, of `compose_env.py` adds nothing); the compose file still parses as YAML. Mutations caught: 422 turned into 400 for the missing tick, audit detail `method:`, no bad link recorded, signed-in fallback language Czech, `+tag` kept in the workspace name, form language fixed to English, opt-out flag inverted, the 254-character cut of the typed address dropped, the language cookie not kept on confirmation.

## Owner steps

1. Nothing for this brief alone: it is merged with the go-wave3 PR and changes nothing in production (no path is sent to Go; the new compose keys pass values only from `.env`).
2. To switch the sign-up pages to Go later, only while sign-up is on (`UBYHOST_SIGNUP_ENABLED=1` in `.env`) and after brief 1502's login is on Go (the pages link to `/login`): check that `.env` has `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, `TURNSTILE_HOSTNAMES` and `UBYHOST_TRUSTED_PROXY_CIDRS` (brief 1502's owner steps), then add `/signup /signup/verify` to `UBYHOST_GO_PATHS` in `.env` on the server (double-quoted, space-separated), run `docker compose up -d`, open `https://<your domain>/signup` in a private window and check the form shows the Turnstile box. The orchestrator writes the exact value with the switch brief.
