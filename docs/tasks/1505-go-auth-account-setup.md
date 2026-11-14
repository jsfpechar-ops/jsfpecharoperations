# 1505: Go account setup pages (dormant): `/account/accept` and `/account/2fa/setup`, with the `auth_base.html` shell

Status: todo
Depends on: 1501 (built on go-wave3: `safeLocalPath`, `locationQuote`, `langCookieName`, `langCookieMaxAge`, `publicDefaultLanguage` in `go/internal/web/auth/finish.go`; `clientip.Host`) | Base commit: 859d114d5 | Branch: go-wave3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out now (go-wave3). Never create a branch, never push, never open a PR, never use `mcp__` tools. Commit after each step with the message `1505 step k` (k = the step number), and the report as `1505 report`. The orchestrator opens the one PR.

## 1. Objective

Port the four account setup routes of `App/app/routes/admin_accounts.py` to Go: `GET`/`POST /account/accept` (accept the current Terms, Privacy and DPA) and `GET`/`POST /account/2fa/setup` (authenticator QR code, then recovery codes), with the `auth_base.html` page shell they render in. Tier A (sessions, second factor, legal evidence): the code is dormant until the owner lists the paths, and every answer (status, headers, cookies, page, database rows) is proven equal to Python's by 37 golden cases recorded from the real Python app.

## 2. Context

Rules (AGENTS.md): 2 privacy (no new field: `legal_acceptance.ip` and `user_agent` are written exactly as `acceptance.record` writes them; no new outbound request); 3 test secrets and `example.test` addresses only; 4 no new dependency (`github.com/skip2/go-qrcode` and `golang.org/x/text` are already direct requirements in `go/go.mod` lines 11-12); 5 Postgres placeholders, no schema change; 6 the forms work without JavaScript (plain POST forms, as in Python); 7 and 10: the four pages are new Go templates whose HTML is proven equal to Python's (whitespace folded) by the golden test, so they look the same; Go pages cannot be screenshotted yet (orchestrator open item 7, brief 1412 paused), say so in the report instead of a screenshot; 11 go-first: `App/scripts/auth_account_golden.py` and `App/tests/test_go_auth_account.py` are port plumbing (go-first.md exception 1, golden scripts and parity tests). No file under `App/app/` changes.

**The code is in sidecar files.** `docs/tasks/1505-files/` mirrors the repo paths; every file has `.txt` appended. You only copy them (dropping `.txt`) and check their sha256 (step 0). Never type or edit the code. The two existing files (`auth.go`, `auth_test.go`) change by the scripted edits of step 2 only.

**Python source of truth** (`App/app/routes/admin_accounts.py` at the base commit):

- `account_accept_form` 420-434: `auth.require_login` (path is in `_ACCEPTANCE_EXEMPT_PATHS`, `App/app/auth.py` 496-505, so a pending account is not sent to itself), `acceptance.pending` (`App/app/acceptance.py` 46-56), `next` through `security.safe_local_path(..., "/")`; nothing pending: 303 to `next`; else `account_accept.html`.
- `account_accept_submit` 437-460: the same, plus `accept` must be `"1"` (stripped) or 422 with `auth.error.accept_required`; then `acceptance.record(id, docs, "clickwrap", request)` (`acceptance.py` 70-110: one row per document with `request.client.host` and the user agent cut to 300 characters, `ON CONFLICT DO NOTHING`, audit `legal_accepted` detail `terms_v1.7 privacy_v1.8 dpa_v1.8 method=clickwrap`, actor the username, owner the account, actor id and impersonator from `require_login`) and 303 to `next`.
- `two_factor_setup_form` 470-490: `current_user` only (no acceptance redirect); signed out 303 `/login`; authenticator on: back to `/settings` with `flash.accounts.twofa_enabled`; login older than 10 minutes (`auth.FRESH_LOGIN_SECONDS`, `auth.py` 752 and `session_is_fresh` 770-781): back to `/settings/security#settings-security` with `auth.error.recent_login`; the staged secret is decrypted (a value no key opens counts as none) or a new one staged (`auth.stage_totp`); page with the QR code (`qrcode.make`), the `otpauth:` link, the key in groups of four, and `?moved=1` notice.
- `two_factor_setup_submit` 493-538: the same gates; the code with spaces removed must pass `pyotp.TOTP(secret).verify(code, valid_window=1)` (NFKC compare, no replay watermark) or 400 with `auth.error.setup_code_invalid`; then `auth.enable_totp` (eight new recovery codes, `session_version` + 1), `two_factor_recovery.html`, a re-issued session cookie with the same remember choice and the same login time (`issued_at=session_issued_at`), audit `two_factor_enabled` (no actor id: no `require_login` ran).
- Templates: `account_accept.html` (31 lines), `two_factor_setup.html` (41), `two_factor_recovery.html` (23, no language switch), all extending `auth_base.html` (97); `render()` context in `App/app/templating.py` 695-799 (language: `?lang=`, cookie, else English signed in and Czech signed out; the `ubyhost_lang` cookie for a `?lang=` link; no canonical links for these paths).

**What the new Go files do:**

- `acct_shell.go` + `acct_templates/shell.tmpl`: `auth_base.html` (language form, env banner, `?notice=` line, "Not you? Log out" form when signed in, footer, hero) through `text/template` with explicit markupsafe escaping (`acctView.E`, `T`), so the bytes match Jinja and the `otpauth:` link survives (`html/template` would turn it into `#ZgotmplZ`). `acctRender` issues the CSRF token and nonce cookie as `layout.csrfToken` does (`go/internal/hostweb/layout/layout.go` 457-482; `hostweb/` is read-only so it is copied), sets the language cookie, writes nothing on error. `acctSendNow` and `acctBackground` are the hooks brief 1506 uses for `mail.send_now`.
- `account_setup.go`: the four handlers; `acctLogin` is `require_login` on an exempt path (`hostweb.Login`, `go/internal/hostweb/gate.go` 61-95, redirects every pending account to `/account/accept`, so a signed-in, unexpired session is passed through and only signed-out or expired sessions get `hostweb.Login`'s answer); `acctPending`, `acctRecord` (acceptance); `acctTOTPVerify` (pyotp verify); `acctQRData` (go-qrcode, error correction M, 10 px per module, 4-module border: the same 450x450 image layout as `qrcode.make`; the PNG bytes differ).
- `acct_i18n_keys.txt` / `acct_i18n.json`: the strings of the shell, the four pages of 1505 and 1506 and their flashes, written from `host_i18n.STRINGS` by the golden script (its own file, so the sibling briefs that edit `i18n_keys.txt` / `i18n.json` cannot conflict).
- `account_golden_test.go`: the replay harness (`runAccountGolden`, reused by brief 1506); `account_setup_test.go`: pyotp vectors, NFKC, the QR size, escaping, route rows, catalog keys.
- `App/scripts/auth_account_golden.py`: runs the real FastAPI app on SQLite (as `auth_routes_golden.py`), replaces only `mail.send_now` (records the id) and, while seeding, Fernet's IV and clock (so the file is the same on every run); `App/tests/test_go_auth_account.py`: the catalog is fresh.

**Differences from Python, on purpose:**

1. The staging no-login and the no-accounts bootstrap shortcuts of `current_user` / `require_login` are not ported (as in every route of `go/internal/web/auth`).
2. The QR image bytes differ (other encoder); size and module layout are the same, the goldens mask the image.
3. A re-issued session cookie is dropped if the recovery page then fails to render (Python discards the whole response on the same error).

**Verified by the brief writer** in a throwaway worktree of 859d114d5 with exactly these files and step 2's edits, PostgreSQL 16 on a disposable port: `gofmt -l` empty, `go build ./...`, `go vet ./internal/... ./cmd/...` clean, `go mod tidy -diff` empty; `go test ./internal/web/auth/ -count=1 -v`: every test PASS, 0 SKIP (including `TestAccountSetupGoldenDatabase`, 37 cases, and the existing `TestRoutesGoldenDatabase`); `go test ./cmd/ubyhost-web/ ./internal/session/... ./internal/hostweb/... ./internal/mail/` ok; the golden script run twice gives the same two hashes; `pytest tests/test_go_auth_account.py tests/test_go_auth_routes.py` 4 passed. Mutations caught: audit detail separator, notice-form shown signed out, default language English for visitors, first instead of last `?next=`, re-issued cookie without remember, login time not kept.

Anchors (step 0, each `grep -cF '<anchor>' <file>` prints 1):

| File | Anchor |
|---|---|
| `go/internal/web/auth/auth.go` | `func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {` |
| `go/internal/web/auth/auth.go` | `func (d deps) login(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {` |
| `go/internal/web/auth/finish.go` | `func safeLocalPath(value, def string) string {` |
| `go/internal/web/auth/finish.go` | `publicDefaultLanguage = "cs"` |
| `go/internal/web/auth/auth_test.go` | `t.Errorf("%d routes, want ` |
| `go/internal/clientip/clientip.go` | `func Host(r *http.Request, getenv func(string) string) string {` |
| `go/internal/session/issue.go` | `func IsFresh(payload map[string]any, limit int64, now time.Time) bool {` |
| `go/internal/session/totp.go` | `func StageTOTP(ctx context.Context, db *pgxpool.Pool, getenv func(string) string, userID int64, totpSecret string) error {` |
| `go/internal/hostweb/gate.go` | `http.Redirect(w, r, "/account/accept?next="+QuotePath(r.URL.Path), http.StatusSeeOther)` |
| `App/app/routes/admin_accounts.py` | `acceptance.record(account["id"], docs, "clickwrap", request)` |
| `App/app/routes/admin_accounts.py` | `if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):` |

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/auth/acct_shell.go` | create (copy) | `auth_base.html` shell, `acctRender`, CSRF token, send hooks |
| `go/internal/web/auth/acct_templates/shell.tmpl` | create (copy) | `acct.head`, `acct.foot` |
| `go/internal/web/auth/acct_templates/account_accept.tmpl` | create (copy) | page |
| `go/internal/web/auth/acct_templates/two_factor_setup.tmpl` | create (copy) | page |
| `go/internal/web/auth/acct_templates/two_factor_recovery.tmpl` | create (copy) | page |
| `go/internal/web/auth/acct_i18n_keys.txt` | create (copy) | catalog keys |
| `go/internal/web/auth/acct_i18n.json` | create (copy, regenerated) | catalog |
| `go/internal/web/auth/account_setup.go` | create (copy) | the four handlers |
| `go/internal/web/auth/account_golden_test.go` | create (copy) | golden replay harness |
| `go/internal/web/auth/account_setup_test.go` | create (copy) | unit tests |
| `go/internal/web/auth/testdata/account_setup.json` | create (copy, regenerated) | golden |
| `App/scripts/auth_account_golden.py` | create (copy) | writes the golden and the catalog from Python |
| `App/tests/test_go_auth_account.py` | create (copy) | the catalog is fresh |
| `go/internal/web/auth/auth.go` | edit (step 2 script) | four rows appended to the `Routes` slice |
| `go/internal/web/auth/auth_test.go` | edit (step 2 script) | route count + 4 |
| `docs/tasks/1505-report.md` | create | the report |

`docs/tasks/1505-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call):

```bash
git status --short | tail -5; ls go/internal/web/auth/acct_shell.go go/internal/web/auth/account_setup.go go/internal/web/auth/acct_templates App/scripts/auth_account_golden.py App/tests/test_go_auth_account.py 2>&1 | grep -c 'No such file'
cd docs/tasks/1505-files && sha256sum -c <<'EOF' 2>&1 | tail -20
f64603f72ce4fe1eef2b87ac9238ab36eede57bbacb94a20b1d82919fcecaa2c  App/scripts/auth_account_golden.py.txt
9c41bebf659e2e44a60b1a9e2db984f42aed0db6812ed9f458b32c4c62ec0f20  App/tests/test_go_auth_account.py.txt
61f73fcac8f9f4040ccd89b8e42e64676670a9817ef29964fe287551cecae39b  go/internal/web/auth/account_golden_test.go.txt
8110729ebd668452b81280f3c816f8a27545061e25103bb16fdf58f278be5ae0  go/internal/web/auth/account_setup.go.txt
19abd1a3f2493e2e2534cd1342cf2f6b0ac824f5d7d493d47f8b056a148a2ab2  go/internal/web/auth/account_setup_test.go.txt
26fd3d12e2d06b22155fc857fe487414ef4c8398e7708f4d16c1a3bfaeb1d3ba  go/internal/web/auth/acct_i18n.json.txt
ea6e775a9c4730d8b634cb9828f7effa5c8fa9b0635c5404402081dcec31dad2  go/internal/web/auth/acct_i18n_keys.txt.txt
d6eface478202b08c21fb8e81a4b16d53927d33fca8d59f0e68d0d83865379e0  go/internal/web/auth/acct_shell.go.txt
7116c4533ba03f5959d166286f737a1b3f865981066033ac2799abf10333385d  go/internal/web/auth/acct_templates/account_accept.tmpl.txt
0a7070fb2ff2a8e8cc9db94807cae160cdfffb4fa67af38bef1eb24a73db09b1  go/internal/web/auth/acct_templates/shell.tmpl.txt
57d506608079fed9466eda2758a6e13bc8b6b676c989f3037274f4eab20d5f6c  go/internal/web/auth/acct_templates/two_factor_recovery.tmpl.txt
46cd137caf8f6a75e906e2fd359ec249271f1e60dd687b1cfccea7d1b2de3808  go/internal/web/auth/acct_templates/two_factor_setup.tmpl.txt
d18ef021f4c8a5c9fad685b4cd9824be057dfa60776720e1753165200b91e46d  go/internal/web/auth/testdata/account_setup.json.txt
EOF
```

   Expected: `git status` prints nothing (other uncommitted files: STOP and ask), the `grep -c` prints `5`, then thirteen `OK` lines. Then check each anchor of section 2 with `grep -cF '<anchor>' <file>` (one call, eleven commands joined with `;`): eleven `1`. Also `grep -rn 'func acct\|acctRender\|acctCatalog' go/internal/web/auth/*.go | wc -l` prints `0` (no sibling brief defined these names). Anything else: STOP (section 8). No commit for step 0.

1. Copy the thirteen files (from the repo root), then build:

```bash
cd docs/tasks/1505-files && for f in $(find . -type f -name '*.txt' | sed 's|^\./||' | sort); do mkdir -p "../../../$(dirname "$f")"; cp "$f" "../../../${f%.txt}"; done; cd ../../..
git status --short --untracked-files=all | wc -l; cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go build ./... 2>&1 | tail -5
```

   Expected: `13`, no gofmt or build output. Commit `1505 step 1`.

2. Register the routes and raise the route count (from the repo root). The rows go at the end of the `Routes` slice, after any rows other briefs added; the count goes up by 4 from whatever it is now:

```bash
python3 - <<'PY'
p = "go/internal/web/auth/auth.go"
s = open(p, encoding="utf-8").read()
start = s.index("\treturn []Route{\n")
end = s.index("\n\t}\n", start) + 1  # the line that closes the slice
rows = (
    '\t\t{"GET /account/accept", "/account/accept", d.accountAcceptForm},\n'
    '\t\t{"POST /account/accept", "/account/accept", d.accountAcceptSubmit},\n'
    '\t\t{"GET /account/2fa/setup", "/account/2fa/setup", d.twoFactorSetupForm},\n'
    '\t\t{"POST /account/2fa/setup", "/account/2fa/setup", d.twoFactorSetupSubmit},\n'
)
open(p, "w", encoding="utf-8").write(s[:end] + rows + s[end:])
PY
f=go/internal/web/auth/auth_test.go; n=$(grep -oE 'if len\(seen\) != [0-9]+ \{' $f | grep -oE '[0-9]+'); m=$((n+4)); sed -i "s/if len(seen) != $n {/if len(seen) != $m {/; s/routes, want $n\", len(seen))/routes, want $m\", len(seen))/" $f
grep -c 'd.accountAcceptForm}\|d.accountAcceptSubmit}\|d.twoFactorSetupForm}\|d.twoFactorSetupSubmit}' go/internal/web/auth/auth.go; grep -n 'len(seen) !=\|routes, want' $f; git diff --stat | tail -3
cd go && gofmt -l internal/web/auth 2>&1 | tail -3; go vet ./internal/web/auth/ 2>&1 | tail -5; go test -count=1 ./internal/web/auth/ 2>&1 | tail -5
```

   Expected: `4`; two lines showing the same number, 4 higher than before (22 if no sibling brief added routes); `git diff --stat` shows `auth.go | 4 ++++` and `auth_test.go | 4 ++--`; no gofmt or vet output; `ok` (the database tests skip here; step 3 runs them). Commit `1505 step 2`.

3. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server you may create databases on, use it and skip the start. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if it already runs (`su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55505/data status' | tail -1` says `server is running`):

```bash
mkdir -p /var/tmp/pg55505 && chown postgres /var/tmp/pg55505 && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg55505/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg55505/data -o "-p 55505 -k /var/tmp/pg55505" -l /var/tmp/pg55505/log start' 2>&1 | tail -3
```

   Expected: `server started`. No PostgreSQL 16 binaries at that path: write "CI only" in the report and STOP before the test below. Then (from the repo root):

```bash
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres go test ./internal/web/auth/ -count=1 -v 2>&1 | grep -cE '^\s*--- SKIP'; UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres go test ./internal/web/auth/ -count=1 -v -run 'TestAccountSetupGoldenDatabase|TestAcct|TestRoutesGoldenDatabase|TestRoutesBuildWithoutPool' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15
```

   Expected: `0` (no skipped test or subtest), then only `--- PASS` lines and `ok`. Commit nothing new if nothing changed (no commit for this step when the tree is clean).

4. The golden script must reproduce the two Python files (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -5; cd ..`.

```bash
cd App && .venv/bin/python scripts/auth_account_golden.py 2>/dev/null | tail -3; cd .. && sha256sum go/internal/web/auth/testdata/account_setup.json go/internal/web/auth/acct_i18n.json | tail -2 && git status --short | tail -5
cd App && .venv/bin/python -m pytest tests/test_go_auth_account.py tests/test_go_auth_routes.py -q --tb=short 2>&1 | tail -3
```

   Expected: two `wrote go/internal/web/auth/...` lines, the hashes `d18ef021f4c8a5c9fad685b4cd9824be057dfa60776720e1753165200b91e46d` and `26fd3d12e2d06b22155fc857fe487414ef4c8398e7708f4d16c1a3bfaeb1d3ba` (as in step 0), `git status` empty, `4 passed`. A different hash: STOP (Python differs from what the Go code was proven against; do not commit the regenerated file). No commit (nothing changed).

5. Run section 6. Write the report (section 9) and commit it as `1505 report`. Do not push or open a PR.

## 5. Do not touch

`go/internal/hostweb/` (read-only; the CSRF token code is copied, not changed), `go/internal/session/`, `go/internal/mail/`, `go/internal/jobs/`, `go/internal/clientip/`, every existing file in `go/internal/web/auth/` except the two step-2 edits (`i18n_keys.txt`, `i18n.json`, `routes_test.go`, `testdata/routes.json`, `finish.go`, `account.go`, `admin.go` stay as they are), `go/cmd/ubyhost-web/` (the routes register through the existing `auth.Routes` loop in `register_web_auth.go`), `go/go.mod`, `go/go.sum`, `App/app/`, `deploy/` (no environment change, `UBYHOST_GO_PATHS` stays as it is), `docs/context/`, `docs/tasks/1505-files/`. Never print a secret, token, link or e-mail address. Rules 2, 3, 4, 5, 6, 7, 10 and 11 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/web/auth 2>&1 | tail -5` prints nothing.
- `cd go && go build ./... 2>&1 | tail -30` prints nothing.
- `cd go && go vet ./internal/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres go test ./internal/web/auth/... ./internal/session/... ./internal/hostweb/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` prints only `ok` lines.
- `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55505/postgres go test ./internal/web/auth/ -count=1 -v 2>&1 | grep -cE '^\s*--- SKIP'` prints `0` (report this SKIP count).
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `cd App && .venv/bin/python -m pytest tests/test_go_auth_account.py tests/test_go_auth_routes.py -q --tb=short 2>&1 | tail -3` prints `4 passed`.
- `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` shows no error naming 1505.

Test-map: no row covers Go packages; the commands above are this brief's tests.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1505 step'` lists steps 1 and 2 (and `git log --oneline --grep='^1505 report'` the report).
- [ ] `for c in $(git log --format=%h --grep='^1505 '); do git show --name-only --format= $c; done | sort -u` lists exactly the 16 files of section 3 (the report included) plus `docs/tasks/1505-go-auth-account-setup.md` (the Status line): 17 lines.
- [ ] The copied files equal the sidecar: `cd docs/tasks/1505-files && for f in $(find . -type f -name '*.txt'); do cmp "$f" "../../../${f%.txt}"; done` prints nothing.
- [ ] `git diff 859d114d5 -- go/internal/web/auth/auth.go | grep '^[-+]' | grep -v '^+++\|^---'` shows only `+` lines (the four rows, plus rows of sibling briefs if they ran first).
- [ ] Section 6 output exactly as stated, SKIP count 0.
- [ ] `for c in $(git log --format=%h --grep='^1505 '); do git show --name-only --format= $c; done | grep -E 'go\.mod|go\.sum|App/app/|hostweb/|cmd/ubyhost-web/|deploy/|docs/context/'` prints nothing.
- [ ] Report: "No screenshot: the Go pages are proven equal to Python's HTML by `TestAccountSetupGoldenDatabase`; Go pages cannot be screenshotted yet (open item 7)."

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

Write `docs/tasks/1505-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (the section 7 file list).
2. Each command, with the last 5 lines of its output, and the SKIP count.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/web/auth/account_setup.go`: `acctLogin` (the acceptance exemption must not open any other path; it is used by the two `/account/accept` handlers only), the freshness gate before any secret is shown or changed, `acctTOTPVerify` (window of one step each side, constant-time compare), `twoFactorSetupSubmit` (the recovery codes are shown once and only stored hashed by `session.EnableTOTP`; the new cookie keeps remember and the login time), `acctRecord` (audit detail carries document ids and versions only).
- `go/internal/web/auth/acct_shell.go` and `acct_templates/*.tmpl`: every value printed goes through `E` or `T` (text/template does not escape by itself); only `Check` is raw markup. The CSRF token is bound to the nonce cookie exactly as `layout.csrfToken`.
- `go/internal/web/auth/auth.go`: four rows appended, nothing else.
- `App/scripts/auth_account_golden.py`: drives the real app; fakes only `mail.send_now` and, while seeding, Fernet's IV and clock.

Verified by the brief writer: see section 2 ("Verified by the brief writer"). Cross-brief note: 1502, 1503 and 1507 render other `auth_base.html` pages (login, 2FA login, sign-up); if one of them ships its own shell first, a later clean-up brief can make them share `acctRender`. The names here all start with `acct` so they cannot collide.

## Owner steps

1. Nothing for this brief alone: it merges with the one big PR and changes nothing in production (no path is switched, no environment change).
2. Switch later, together with brief 1503's `/login/2fa` and 1506's `/account/email*` paths, only after brief 1502's owner steps have given the `ubyhost-go` service `UBYHOST_TRUSTED_PROXY_CIDRS` (otherwise the acceptance row records Caddy's address as the visitor's): add `/account/accept /account/2fa/setup` to `UBYHOST_GO_PATHS` in the server's `.env` (both methods of each path move together), run `deploy.sh`, then open `https://<your domain>/account/2fa/setup` while logged in within the last 10 minutes and check the QR code scans. To go back, remove the two paths and run `deploy.sh` again.
