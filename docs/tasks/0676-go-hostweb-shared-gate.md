# 0676: Go shared host web gate and host strings (go/internal/hostweb)
Status: review
Depends on: 0675 (#680) | Base commit: claude/project-thread-iwyawc | Branch: task/0676-go-hostweb
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Move the host login gate, CSRF gate, language and flash-redirect helpers that today live privately in `go/internal/payments/connect.go` into a new exported package `go/internal/hostweb`, so the next Go routes (0677 payment requests, 0678 push, 0679 command palette) share one copy. Add a host string catalog for Go that is generated from Python and checked for drift. Pure refactor for Connect: its behaviour and tests stay identical. Production unchanged (Go container off).
## 2. Context
Read: `go/internal/payments/connect.go` (all), `go/internal/payments/connect_test.go` (setup only), `App/app/routes/admin_helpers.py` 1-120 (`FlashMessage`, `_flash_message`, `back`, `flash`), `App/app/host_i18n.py` 1-30 and 9940-10010 (`supported_language`, `normalise_language`, `resolve_language`, `lang_from_request`, `lookup`, `translate`; grep `^def ` to find them).

Package `hostweb` exports (names may be adjusted, keep them short):
- `Login(w, r, pool, getenv, at) (*session.Host, error)`: today's `connectLogin` incl. `connectEndExpired` and the paused redirect. Add `LoginJSON` variant only if trivial; otherwise later briefs handle 401 themselves.
- `CSRF(w, r, getenv, at) bool`: today's `connectCSRFGate` with `connectCSRFValid`, `connectSameSite`, `connectBrowserSite`, `connectRecovery`.
- `Lang(r) string`: port `resolve_language(request)` exactly (query `lang`, then cookie, through `supported_language`; default `DEFAULT_LANGUAGE`). Check what `supported_language` accepts; if today's `connectLang` (en/cs/vi only) differs, follow Python and note it in the report.
- `Back(w, r, path string, msg, err Flash)`: `admin_helpers.back` exactly (303, `msg=`/`err=` with Python `quote` (safe `/`), `toast_kind`/`toast_sticky` rules, `#fragment` and `?`/`&` handling). `Flash` = text + key; port `_flash_message` with the two key sets copied as Go sets (comment the Python lines).
- `Catalog` + `Load(json []byte) Catalog` + `(c Catalog) T(lang, key string, params map[string]any) string` with Python `lookup` semantics (unknown lang uses default table, missing key falls back to default table then to the key, `%(name)s` formatting; read `lookup` for the guard on bad params and copy it).
- Also move `Cookie`, `QuotePath`, `PublicBase`/`AppBase`, `SecureCookies` and the other small env helpers that more than Connect will need. Keep Connect-only helpers (`connectOff`, `connectConsented`, `connectFail`) in `connect.go`.

Strings for Go: new script `App/scripts/go_host_i18n.py` (stdlib only, imports `app.host_i18n`). For every file `go/internal/*/i18n_keys.txt` (one key per line, `#` comments allowed) it writes `i18n.json` next to it: `{lang: {key: text}}` for every host language in `host_i18n.STRINGS`, only the listed keys, keys missing in a language left out, `sort_keys=True`, `ensure_ascii=False`, indent 1, trailing newline. `--check` mode exits 1 and names the stale file when a file would change. New test `App/tests/test_go_host_i18n.py` runs the check (so CI fails on drift). In this brief, add `go/internal/hostweb/i18n_keys.txt` with no keys except a comment line, plus its generated `i18n.json`, and a Go test that `Load` + `T` reproduces 3 cases that you also assert in the Python test: a plain key, a `%(name)s` key, a missing key. Go packages embed their own `i18n.json` with `//go:embed`.
## 3. Files
Create: `go/internal/hostweb/hostweb.go` (split into 2-3 files if over ~400 lines), `go/internal/hostweb/hostweb_test.go`, `go/internal/hostweb/i18n_keys.txt`, `go/internal/hostweb/i18n.json`, `App/scripts/go_host_i18n.py`, `App/tests/test_go_host_i18n.py`. Edit: `go/internal/payments/connect.go` (use hostweb, delete the moved code), `connect_test.go` only if a moved helper is called directly (move those unit cases to `hostweb_test.go`). Write `docs/tasks/0676-report.md`.
## 4. Steps
1. Create the package by moving code; `connect.go` calls hostweb. No behaviour change.
2. Unit tests in `hostweb_test.go`: Back (msg only, err only, both, success key adds `toast_kind=success`, sticky warning key adds `toast_sticky=1`, path with `?` and with `#frag`, non-ASCII Czech text quoted like Python `quote`), Lang (query beats cookie, unsupported falls to default), Catalog T cases, CSRF cases moved from connect_test if any.
3. Script, JSON, Python test.
4. Commit: `0676: Go shared host web gate and host strings`.
## 5. Do not touch
`App/app/` (read only), `webhook.go`, `onboarder.go`, `paylink.go`, `main.go`, `go.mod`/`go.sum`, CI, compose, Caddy, templates, JS, CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/hostweb/ ./internal/payments/ -count=1 2>&1 | tail -30`.
- From `App/` (create `.venv` first if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`): `.venv/bin/python scripts/go_host_i18n.py --check && .venv/bin/python -m pytest tests/test_go_host_i18n.py -q --tb=short 2>&1 | tail -10`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
hostweb and payments tests pass with the database URL set, 0 skipped; vet, gofmt, build clean; Python check and test pass; Connect tests unchanged and green.
## 8. Stop and ask
Stop if moving the code would change Connect behaviour, or a new dependency seems needed.
## 9. Report
`docs/tasks/0676-report.md`: command tails, `git diff --stat`, the exported API list (one line each), anything decided beyond section 2.
