# 1502: Go login pages (dormant): GET/POST /login, GET/POST /login/link, and the signed-out page renderer

Status: todo
Depends on: 1501 (on go-wave3: `clientip`, `turnstile`, `web/auth/finish.go`, `mail/auth_queue.go`); 1280 and 1282 are merged (`session/loginlink.go`, `web/auth/auth.go` `Routes`). Not 1514. | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 14 calls)

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR. Commit after each step that changes files with the message `1502 step k`, and the report as `1502 report`. The orchestrator opens the PR.

## 1. Objective

Port the four login routes of `App/app/routes/admin_accounts.py` (lines 60-267) to Go with their pages (`login.html`, `login_sent.html`, `login_link.html`, and `two_factor_login.html` for an account with an authenticator), plus a new package `authpage` that renders any page extending `auth_base.html`, which the later auth briefs reuse. Nothing switches: Caddy sends `/login` and `/login/link` to Go only after the owner adds them to `UBYHOST_GO_PATHS` (Owner steps); the compose file only passes four more keys to the Go container.

## 2. Context

Rules (AGENTS.md): 1 filing untouched; 2 no new personal-data field, no new cookie (the same session, device, language and CSRF cookies Python sets), the Turnstile siteverify request already declared by 1501 (PR text below); 3 test data is made up (`@example.test`, test-only secrets); 4 no new dependency (`go.mod` unchanged); 5 plain PostgreSQL, no schema change; 6 forms work without JavaScript (same markup as Python); 7 and 10 do not apply yet: no page is served until the path switch, and the UX gate is an owner step at the switch (as brief 1427); 11 go-first: `App/scripts/auth_login_golden.py` and `App/tests/test_go_auth_pages.py` are port plumbing (go-first.md allowance 1: golden scripts, parity tests). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1502-files/` mirrors the repo paths with `.txt` appended. You only copy them, check their sha256 and run three small edit scripts from `docs/tasks/1502-files/edits/`. Never type or edit code.

**What the files do** (Python source in brackets, checked at 859d114d5):

- `go/internal/web/auth/authpage/` (new package): `Render(w, r, env, host, name, data, status)` is `templating.render` (`templating.py` 695-797) for a page extending `auth_base.html`, with `_seo_head.html` (canonical and hreflang for `/login`, `seo.head_links` 125-136) and `_env_banner.html`, plus what the middleware adds (`main.py` 321-345): the `ubyhost_lang` cookie for a new `?lang=` (`host_i18n.remember_language` 11042), the `ubyhost_csrf` nonce cookie (a copy of `hostweb/layout` `csrfToken`, layout.go 457-482, which is not exported) and the remember-me refresh (`auth.refresh_session_cookie` 580-599, through `session.RefreshSession`), in Python's cookie order. Language: last `?lang=`, then the cookie, else English when signed in and Czech for a visitor (`templating.py` 702-709). `hostweb/layout.Render` cannot be used: it always renders the host shell (`layout.base`, base.html), never `auth_base.html`. Templates: `base.html` (auth_base), `login.html`, `login_sent.html`, `login_link.html`, `two_factor_login.html`. Catalog `i18n.json` from `i18n_keys.txt` (written by `go_host_i18n.py`, so `App/tests/test_go_host_i18n.py` already guards it).
- `go/internal/web/auth/login.go`: `loginForm` [`login_form` 60-64, `_login_page_context` 76-83], `loginSubmit` [`login_submit` 116-182 with `_try_staging_password_login` 86-113 and `_dev_link_visible` 67-73], `loginLinkForm` [`login_link_form` 193-208, `_link_page` 185-190], `loginLinkSubmit` [`login_link_submit` 228-267], the GET redirect from the public host to the app host [`site_urls.login_redirect_url` 60-72, called in `main.py` 326-332], and the staging helpers [`auth.py` 792-862]. It reuses, unchanged: `hostweb.CSRF`, `d.current`, `formStr`, `normaliseEmail` (account.go 204), 1501's `finishLogin`, `safeLocalPath`, `loginLanguage`, `clientip.Key`, `turnstile.Verifier`, `mail.QueueLinkMail`, `mail.SendNow`, and `session.LinkRequestBlocked`/`LinkRecordRequest` (3 per 15 min per address, 10 per day per address, 10 per 15 min per IP), `LinkConsumeBlocked`/`LinkRecordConsumeFailure` (20 bad links per 15 min per IP), `TrustedDevice`, `DeviceCookieValid`, `IssueLoginLink`, `PeekLoginLink`, `ConsumeLoginLink`, `AccountForLink`, `IssueTwoFactorPending`. A valid device cookie for the typed address skips Turnstile (and hides the widget on GET); the link page sends `Cache-Control: no-store` and `Referrer-Policy: no-referrer`; the 2FA page `Cache-Control: no-store`. Audit rows: `login_link_sent` (actor `anonymous`, owner the account) and, through `finishLogin`, `login` with `method=link` or `method=staging_password`.
- `go/internal/web/auth/login_test.go` + `testdata/login.json`: 79 cases recorded from the real FastAPI app by `App/scripts/auth_login_golden.py` (SQLite, Turnstile's `requests.post` replaced by a fake), replayed on PostgreSQL through `Routes` with the real Turnstile verifier pointed at an equivalent fake server. Compared per case: status, `Location`, `Content-Type`, `Cache-Control`, `Referrer-Policy`, the whole page HTML (whitespace runs and form tokens normalised), every cookie with its attributes and session/device payload, the 2FA pending payload, the bootstrap login file, and the rows of `audit`, `rate_limit_event`, `login_token`, `user_account`, `email_outbox` and `alert`.
- `App/tests/test_go_auth_pages.py`: fails when a `?v=` asset URL in the five Python templates is not the same in the Go copies.

**Differences from Python, on purpose:**
1. The Go container mounts the data volume read-only, so after an admin's first invite link the `initial_admin_login` file cannot be deleted there; Python ignores the same `OSError`. The link in that file is spent by then.
2. `mail.send_now` runs in a goroutine after the page is written (Python: a BackgroundTask). The Go container has no SES credentials (`docker-compose.yml`: "no SES/AWS"), so in production that send fails with a log line and the queued row goes out with Python's next mail job (every 5 minutes). See Owner step 3.
3. A 500 answers plain `Internal Server Error` (the existing `serverError`), not Python's `error.html` page.
4. html/template writes `+` as `&#43;` in text and attributes; the test maps it back before comparing. Browsers read both the same.
5. Python's GET redirect also covers `/login/`; Go does not register that path, and Caddy's `path /login` matches only `/login`, so `/login/` stays on Python.

**PR text (hard rule 2, the orchestrator pastes it):** "No new personal-data field. The Go login form (dormant until `/login` is in `UBYHOST_GO_PATHS`) makes the Turnstile siteverify request declared in brief 1501 (`challenges.cloudflare.com/turnstile/v0/siteverify`: token, server secret, visitor IP), exactly as `App/app/turnstile.py` does today for the same form. The Go container now receives `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, `TURNSTILE_HOSTNAMES` and `UBYHOST_TRUSTED_PROXY_CIDRS` from `.env`."

**Edits to shared live files** (each is a script in `edits/` that checks its anchor and stops if it is missing; each still applies when a sibling brief 1503-1510 ran first):
- `go/internal/web/auth/auth.go`: `edits/routes.py.txt` appends four rows at the end of the `Routes` slice, after any rows other briefs added (it finds `func Routes(` and the slice's closing `\t}` after it).
- `go/internal/web/auth/auth_test.go`: `edits/count.py.txt` reads `TestRoutesBuildWithoutPool`'s route count N (18 at 859d114d5, more if a sibling brief added routes) and writes N+4 in both places, as the sibling briefs do.
- `deploy/lightsail/docker-compose.yml`: `edits/compose.py.txt` adds the bare keys `UBYHOST_TRUSTED_PROXY_CIDRS` (after `UBYHOST_TERMS_VERSION:`) and `TURNSTILE_HOSTNAMES`, `TURNSTILE_SECRET`, `TURNSTILE_SITE_KEY` (after `POSTHOG_PROJECT_API_KEY:`) to the `ubyhost-go` service only, and drops "Turnstile, " from its "no ... secrets" comment. It adds only the keys that are missing (brief 1507 adds the same four if it ran first). The staging-only keys (`UBYHOST_STAGING_LOGIN_PASSWORD`, `UBYHOST_ADMIN_USERNAME`, `UBYHOST_ADMIN_EMAIL`) are not passed: this compose file runs production only.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/web/auth/auth.go` | `func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {` |
| `go/internal/web/auth/finish.go` | `func (d deps) finishLogin(w http.ResponseWriter, r *http.Request, account *session.LoginAccount,` |
| `go/internal/turnstile/turnstile.go` | `func (v Verifier) Verify(ctx context.Context, r *http.Request, token, expectedAction string) (bool, error) {` |
| `go/internal/clientip/clientip.go` | `func Key(r *http.Request, getenv func(string) string, suffix string) string {` |
| `go/internal/mail/auth_queue.go` | `func QueueLinkMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, kind string,` |
| `go/internal/session/issue.go` | `func RefreshSession(secret string, payload map[string]any, header http.Header, secure bool, now time.Time) (*http.Cookie, error) {` |
| `go/internal/web/auth/account.go` | `func normaliseEmail(raw string) string {` |
| `App/app/routes/admin_accounts.py` | `if not trusted and not turnstile.verify(request, form.get("cf-turnstile-response"), "host_login"):` |
| `deploy/lightsail/docker-compose.yml` | `  ubyhost-go:` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/authpage/authpage.go` | create (copy) | `Render`, `Language`, `LanguageCookie`, `OperatorEmail`, `PasskeysAvailable`, CSRF token |
| `go/internal/web/auth/authpage/pages.go` | create (copy) | `LoginData`, `LoginSentData`, `LoginLinkData`, `TwoFactorLoginData` |
| `go/internal/web/auth/authpage/authpage_test.go` | create (copy) | keys in catalog, titles, language, cookies and head (no database) |
| `go/internal/web/auth/authpage/i18n_keys.txt` | create (copy) | the keys the pages print |
| `go/internal/web/auth/authpage/i18n.json` | create (copy, regenerated in step 3) | catalog |
| `go/internal/web/auth/authpage/templates/base.html` | create (copy) | auth_base.html, _seo_head, _env_banner |
| `go/internal/web/auth/authpage/templates/login.html` | create (copy) | login.html |
| `go/internal/web/auth/authpage/templates/login_sent.html` | create (copy) | login_sent.html |
| `go/internal/web/auth/authpage/templates/login_link.html` | create (copy) | login_link.html |
| `go/internal/web/auth/authpage/templates/two_factor_login.html` | create (copy) | two_factor_login.html |
| `go/internal/web/auth/login.go` | create (copy) | the four handlers, host redirect, staging helpers |
| `go/internal/web/auth/login_test.go` | create (copy) | golden replay (PostgreSQL) |
| `go/internal/web/auth/testdata/login.json` | create (copy, regenerated in step 3) | golden |
| `go/internal/web/auth/auth.go` | edit (script) | four rows appended to `Routes` |
| `go/internal/web/auth/auth_test.go` | edit (script) | route count + 4 |
| `deploy/lightsail/docker-compose.yml` | edit (script) | four bare keys for `ubyhost-go` |
| `App/scripts/auth_login_golden.py` | create (copy) | writes `login.json` and the catalog from the real Python |
| `App/tests/test_go_auth_pages.py` | create (copy) | asset URLs of the Go copies match Python |
| `docs/tasks/1502-report.md` | create | the report |

`docs/tasks/1502-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

From the repo root unless a step says otherwise.

0. Checks (one call, no commit):

```bash
git status --short | tail -5; ls go/internal/web/auth/authpage go/internal/web/auth/login.go go/internal/web/auth/login_test.go go/internal/web/auth/testdata/login.json App/scripts/auth_login_golden.py App/tests/test_go_auth_pages.py 2>&1 | grep -c 'No such file'
cd docs/tasks/1502-files && sha256sum -c <<'EOF' 2>&1 | tail -20
2ebfad45604685119e6517137dcf1eae563cc7fb97971a080361ee50d3f3c1e9  App/scripts/auth_login_golden.py.txt
1087d0604eaa828420504d223bdd05198f83cf632fef562f897792c4f70ee60f  App/tests/test_go_auth_pages.py.txt
f6c7af1c0491c05879e8aecee623f8fb8e3b5c3cb7b7b71bcf917ce080f9a064  edits/compose.py.txt
8282e77d6bb6b31a0a0cda1dad4d3b4bb249c08203da180909a1b45a726d29ef  edits/count.py.txt
0c3066f1807e6dc33f395b073644bc53b41f8bbafe54f8e7f197fa3f0f2a7e98  edits/routes.py.txt
1c64b5015ee2fb9aec04df04a5ffbea8ce3223d312e39bed5fa944a55ca9d248  go/internal/web/auth/authpage/authpage.go.txt
80e14449bdf5de0bfb64a542c9da77a5f4cd911cf592dc5ca956f12af373fcce  go/internal/web/auth/authpage/authpage_test.go.txt
28d5e36c9216e2f95d20eaef2d95c6513465c8216421da335fbee74dbd0fa1f2  go/internal/web/auth/authpage/i18n.json.txt
dd58bc45028cad64402c021644222cf07421a8a70a8165c908e15dd80a25e658  go/internal/web/auth/authpage/i18n_keys.txt.txt
26e94ffc6edf336946fc360f8bfc139f785434d85f8bd7fb7eaf67624a04cc7d  go/internal/web/auth/authpage/pages.go.txt
57469773697239fb6cbb2dc6cb7bda549d7e6a9a5c9e777dc5898ccadd83b255  go/internal/web/auth/authpage/templates/base.html.txt
9de557a88e5b29804fbc18fa05e973f55ac6059240dfa1e6c7fe46687e084b50  go/internal/web/auth/authpage/templates/login.html.txt
8fc20a014da9b0d59117e651aa18ea8071492f0b95475b0e4d5b040acd80684e  go/internal/web/auth/authpage/templates/login_link.html.txt
0492f6f5868548ba774351107849331b65b6d536fc2a4489f89b2df2a7e73682  go/internal/web/auth/authpage/templates/login_sent.html.txt
856d1fc8e4ea82eb8865c0133b62cb6705bf501b1d47fbec2307d858fc27494c  go/internal/web/auth/authpage/templates/two_factor_login.html.txt
f8a62bccdfa5eb165467321cadd42d7dd76d5a7c637efcacd6d501a66778fed0  go/internal/web/auth/login.go.txt
e2881133bc45d2ca5c17df3877f2812a3250a03abe4fd9136359dcf149703101  go/internal/web/auth/login_test.go.txt
f30dc8b920736cee9cbc3a231ba9624a81d87d4f762032336a707799957551bc  go/internal/web/auth/testdata/login.json.txt
EOF
```

   Expected: `git status` prints nothing, or only this brief's own `docs/tasks/1502-*` files (another brief's uncommitted files: STOP and ask), the `grep -c` prints `6`, then eighteen `OK` lines. Then check the nine anchors of section 2 with `grep -cF '<anchor>' <file>` (one call, nine commands joined with `;`): nine `1`. Anything else: STOP (section 8).

1. Copy the page renderer (from the repo root):

```bash
cd docs/tasks/1502-files && for f in $(find go/internal/web/auth/authpage -name '*.txt' | sort); do d="../../../${f%.txt}"; mkdir -p "$(dirname "$d")"; cp "$f" "$d"; done; cd ../../../go && gofmt -l internal/web/auth/authpage 2>&1 | tail -3; go build ./... 2>&1 | tail -5; go vet ./internal/web/auth/authpage/ 2>&1 | tail -5; go test -count=1 ./internal/web/auth/authpage/ 2>&1 | tail -5
```

   Expected: no gofmt, build or vet output (`go: downloading` lines are fine), then `ok`. Commit `1502 step 1`.

2. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`); skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55502/data status' | tail -1` says `server is running`:

```bash
mkdir -p /var/tmp/pg55502 && chown postgres /var/tmp/pg55502 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55502/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55502/data -o "-p 55502 -c listen_addresses=127.0.0.1 -k /var/tmp/pg55502" -l /var/tmp/pg55502/log start' 2>&1 | tail -3
```

   Expected: `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55502/postgres` below. No PostgreSQL 16 binaries at that path: STOP (the golden test must run, not skip). No commit.

3. Copy the handlers and their test, run the two Go edit scripts, test (from the repo root):

```bash
for f in go/internal/web/auth/login.go go/internal/web/auth/login_test.go go/internal/web/auth/testdata/login.json; do cp docs/tasks/1502-files/$f.txt $f; done
python3 docs/tasks/1502-files/edits/routes.py.txt 2>&1 | tail -2; python3 docs/tasks/1502-files/edits/count.py.txt 2>&1 | tail -2
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go build ./... 2>&1 | tail -5; go vet ./internal/web/auth/... 2>&1 | tail -5
UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55502/postgres go test -count=1 -v ./internal/web/auth/... 2>&1 | grep -E '^(ok|FAIL)|--- (FAIL|SKIP)' | tail -30
```

   Expected: `added 4 rows`, then `route count N -> N+4` (`18 -> 22` if no sibling brief ran first), no gofmt, build or vet output, two `ok` lines and no `--- FAIL` or `--- SKIP` line. `rows already there` or a line starting `STOP`: STOP. Commit `1502 step 3` (step 2 has no commit).

4. Copy the golden script and the parity test, and check the script reproduces both generated files (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5; cd ..`.

```bash
cp docs/tasks/1502-files/App/scripts/auth_login_golden.py.txt App/scripts/auth_login_golden.py; cp docs/tasks/1502-files/App/tests/test_go_auth_pages.py.txt App/tests/test_go_auth_pages.py
cd App && .venv/bin/python scripts/auth_login_golden.py 2>&1 | grep -E '^wrote|Error' | tail -5; cd .. && sha256sum go/internal/web/auth/testdata/login.json go/internal/web/auth/authpage/i18n.json | tail -2; git status --short | tail -5
cd App && .venv/bin/python -m pytest tests/test_go_auth_pages.py tests/test_go_host_i18n.py tests/test_go_auth_routes.py -q -rs 2>&1 | tail -5
```

   Expected: two `wrote go/internal/...` lines (a few lines naming `HTTPError: 503` come from the fake Cloudflare outage case and are normal), the two hashes equal to those of `login.json.txt` and `i18n.json.txt` in step 0, `git status` shows only `?? App/scripts/auth_login_golden.py` and `?? App/tests/test_go_auth_pages.py`, then `passed` with no `SKIPPED` line. A different hash: STOP (Python differs from what the Go code was proven against). Commit `1502 step 4`.

5. The compose keys (from the repo root):

```bash
python3 docs/tasks/1502-files/edits/compose.py.txt 2>&1 | tail -2; git diff --stat deploy/ | tail -2; cd App && .venv/bin/python -m pytest tests/test_wp32_container_sizing.py -q 2>&1 | tail -3
```

   Expected: `added 4 keys to ubyhost-go` and `1 file changed, 5 insertions(+), 1 deletion(-)` (if brief 1507 ran first: `added 0 keys` and no diff, then skip the commit), then `passed`. A line starting `STOP`: STOP. Commit `1502 step 5`.

6. Run section 6. Write the report (section 9) and commit it as `1502 report`. Do not push or open a PR. Leave PostgreSQL running (later briefs may use it).

## 5. Do not touch

`go/internal/hostweb/` (including `layout/`), `go/internal/session/`, `go/internal/jobs/`, `go/internal/mail/`, `go/internal/turnstile/`, `go/internal/clientip/`, every existing file in `go/internal/web/auth/` except the two script edits (`finish.go`, `account.go`, `admin.go`, `routes_test.go`, `testdata/routes.json`, `i18n.json`, `i18n_keys.txt` stay as they are), `go/cmd/ubyhost-web/` (the routes register through the existing `register_web_auth.go`), `go/go.mod`, `go/go.sum`, `App/app/`, `App/tests/conftest.py`, `deploy/` except the compose script, Caddy files, `docs/context/*`, `docs/ENVIRONMENT.md`, `docs/tasks/1502-files/`. Never set `UBYHOST_GO_PATHS`. Never print a secret, token, link or e-mail address. Rules 2, 3, 4, 5, 6 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/web/auth 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55502/postgres go test -count=1 -v ./internal/web/auth/... ./internal/hostweb/... ./internal/session/... ./internal/turnstile/... ./internal/clientip/... ./cmd/ubyhost-web/... 2>&1 | grep -E '^(ok|FAIL)|--- (FAIL|SKIP)' | tail -30` prints only `ok` lines (report the number of `--- SKIP` lines: it must be 0).
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `cd App && .venv/bin/python -m pytest tests/test_go_auth_pages.py tests/test_go_host_i18n.py tests/test_go_auth_routes.py tests/test_wp32_container_sizing.py -q -rs 2>&1 | tail -5` ends in `passed`, no `SKIPPED`.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1502.

Test-map: no row covers Go packages; the commands above are this brief's tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1502 '` lists steps 1, 3, 4, 5 (no 5 if brief 1507 already added the compose keys) and the report.
- [ ] `for c in $(git log --format=%h --grep='^1502 '); do git show --name-only --format= $c; done | sort -u` lists exactly the 19 files of section 3 (18 without the compose file in that case) plus `docs/tasks/1502-go-auth-login.md` (Status line).
- [ ] The copied files equal the sidecar: `cd docs/tasks/1502-files && for f in $(find go App -name '*.txt'); do cmp "$f" "../../../${f%.txt}"; done` prints nothing.
- [ ] `git diff 859d114d5 -- go/internal/web/auth/auth.go | grep -c '^+\s*{"\(GET\|POST\) /login\(/link\)\?",'` prints `4`, and `grep -c 'UBYHOST_GO_PATHS' deploy/lightsail/docker-compose.yml` prints the same number as before (`git show 859d114d5:deploy/lightsail/docker-compose.yml | grep -c UBYHOST_GO_PATHS`).
- [ ] Section 6 output exactly as stated, 0 skipped.
- [ ] `for c in $(git log --format=%h --grep='^1502 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|hostweb/|internal/session/|internal/mail/|cmd/ubyhost-web/|Caddyfile'` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, an edit script prints a line starting `STOP` or `rows already there`, or a regenerated file has another hash;
- a test fails twice (never change the code: it is fixed by hash);
- PostgreSQL cannot be started (the golden test must run, not skip);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1502-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/login.go`: the order of checks in `loginSubmit` (staging, trusted device, Turnstile, empty address, rate limit, record, link) is Python's; the same page with or without an account; the token never logged (`DevLink` only on a local run with console mail); `loginLinkSubmit` records a bad-link failure only when no account comes back; the 2FA branch issues the pending token and no session; `loginHostRedirect` (302, `no-referrer`, only for the public host when an app host is set).
- `go/internal/web/auth/authpage/authpage.go`: CSRF nonce cookie (HttpOnly, Strict, Secure per `SecureCookies`), cookie order, the language fallback, nothing written on an error, html/template escaping (no `template.HTML` from request data: only the page body produced by the page template).
- `deploy/lightsail/docker-compose.yml`: bare keys only, `ubyhost-go` service only.

Verified by the brief writer in a throwaway worktree of 859d114d5 with exactly these files and steps, PostgreSQL 16 on a disposable port: `gofmt -l` empty; `go build ./...`; `go vet ./internal/... ./cmd/...` clean; `go mod tidy -diff` empty; `go test -v ./internal/web/auth/... ./internal/hostweb/... ./internal/session/... ./internal/turnstile/... ./internal/clientip/... ./internal/mail/... ./cmd/ubyhost-web/... -count=1` all `ok`, 0 `--- SKIP`, all 79 golden cases pass (every page byte-equal to Python's after normalising); the golden script run twice gives the same two hashes; the pytest files above pass; `docker compose --profile go config -q` accepts the edited file. Mutations caught by the golden test: 429 changed to 400 (3 cases), trusted-device skip removed (1), TOTP branch skipped (2), dev link dropped (6), `no-referrer` dropped (16); `test_go_auth_pages.py` fails when one `?v=` differs. The four pages were opened at 390 px in headless Chrome against `App/app/static` and look like the Python pages (card, language switch, alert, form, footer).

Cross-brief notes for the orchestrator: (a) `authpage` and `two_factor_login.html`/`TwoFactorLoginData` are meant for 1503 (it renders the same page with an error) and for 1505-1507 (signed-out pages): a sibling that wrote its own renderer should be re-pointed at `authpage`. (b) 1503 is `blocked` waiting for `renderTwoFactorLogin` with exactly the signature it names: this brief defines it (login.go), so 1503 can be set to `todo`. (c) Found, not fixed (main.go is out of scope): Python's middleware adds `X-Robots-Tag: noindex` to every response (`main.py` 344); Go's `hardenHeaders` (main.go 49-56) does not, for any Go page.

## Owner steps

1. Nothing changes in production when this merges: no path is switched. After the deploy, the Go container also receives the Turnstile keys and `UBYHOST_TRUSTED_PROXY_CIDRS` from `.env`.
2. Before switching, check the Go container sees them (prints only "set" or "MISSING"): on the server, in the folder with `docker-compose.yml`, run `docker compose --profile go exec ubyhost-go sh -c 'for k in TURNSTILE_SITE_KEY TURNSTILE_SECRET TURNSTILE_HOSTNAMES UBYHOST_TRUSTED_PROXY_CIDRS; do [ -n "$(printenv $k)" ] && echo "$k set" || echo "$k MISSING"; done'`. All four must say `set`; if one is missing, add it to `.env` (Python needs it too) and redeploy.
3. Decide how the login mail leaves when Go serves `/login`: the Go container has no SES keys, so the link mail waits for Python's mail job (up to 5 minutes; the link lives 15). Recommended: ask the orchestrator for a small brief that passes `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID` and `UBYHOST_AWS_SECRET_ACCESS_KEY` to `ubyhost-go`, and switch only after it is deployed.
4. The switch (both paths together; `/login/2fa` may stay on Python, it reads the same signed pending token): in `.env` add `/login /login/link` to `UBYHOST_GO_PATHS` (space-separated, inside the double quotes), then redeploy. Then, in a private window: open `/login`, request a link, open it from the mail, press Log in, and check you land signed in; also check the Czech and English switch. The UX gate (390/768/1280 screenshots, rule 10) is run by the orchestrator at this point.
5. To undo: remove the two paths from `UBYHOST_GO_PATHS` and redeploy; Python serves them again with no data change.

## API for later briefs

All in the repo after this brief. Package `authpage` (`go/internal/web/auth/authpage`):

```go
type Env struct { Getenv func(string) string; Now time.Time }
// templating.render for a page extending auth_base.html; host is current_user (nil for a visitor); status 0 is 200.
// Writes the lang, CSRF and refresh cookies, then the page; nothing on error.
func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, name string, data any, status int) error
func Language(r *http.Request, signedIn bool) string          // the page language render uses
func LanguageCookie(lang string, getenv func(string) string) *http.Cookie // remember_language
func OperatorEmail(getenv func(string) string) string        // operator().email
func PasskeysAvailable(getenv func(string) string) bool      // passkeys.available()
var Strings hostweb.Catalog                                   // the pages' catalog
type LoginData, LoginSentData, LoginLinkData struct{ ... }    // pages.go
type TwoFactorLoginData struct { Pending, Error string }      // two_factor_login.html; Error is a catalog key
```

To add a page: create `templates/<name>.html` with `{{define "<name>"}}` (the `auth_body` block) and `{{define "<name>.title"}}`, optionally `"<name>.meta"` (meta_description) and `"<name>.lang_next"` (the switch's next, e.g. `/login` for a POST answer). The page runs with `authpage.Page` (`.Lang`, `.CSRF`, `.SiteKey`, `.Passkeys`, `.OperatorEmail`, `.SignedIn`, `.Data`); `{{t "key" "name" value ...}}` is `t('key', name=value)`. Append its keys at the end of `i18n_keys.txt` and regenerate `i18n.json` with `App/.venv/bin/python App/scripts/go_host_i18n.py` (run from `App/`). Put the page's Data type in a new file of the package.

In package `auth` (`login.go`), callable from new files:

```go
func (d deps) render(w http.ResponseWriter, r *http.Request, h *session.Host, at time.Time, name string, data any, status int) // Render, 500 on error
// two_factor_login.html for current_user; no Cache-Control, nothing written on error (brief 1503's contract)
func (d deps) renderTwoFactorLogin(w http.ResponseWriter, r *http.Request, pending, errorKey string, status int) error
func (d deps) refreshed(w http.ResponseWriter, h *session.Host, at time.Time) bool // refresh_session_cookie before a redirect; false after a 500
func deployment(getenv func(string) string) string                                  // config.DEPLOYMENT
var loginVerifier func(d deps) turnstile.Verifier                                    // the host_login Turnstile check (tests replace it)
```

```go
// 1503 POST /login/2fa, a wrong code:
if err := d.renderTwoFactorLogin(w, r, pending, "auth.error.code_invalid", http.StatusUnauthorized); err != nil { serverError(w, err) }
```
