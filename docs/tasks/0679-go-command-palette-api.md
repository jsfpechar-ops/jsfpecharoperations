# 0679: Go command-palette JSON API
Status: review
Depends on: 0676 (hostweb) | Base commit: task/0676-go-hostweb | Branch: task/0679-go-command-palette
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Port `GET /api/command-palette` (`App/app/routes/api.py`, 120 lines) to a new Go package `go/internal/palette`, as-is, and register it in `go/cmd/ubyhost-web/main.go`. Production unchanged: Go container off.
## 2. Context
Python source of truth (read only these, grep `^def ` and read one function at a time): `App/app/routes/api.py` (all); `App/app/auth.py` `require_login`, `current_user`; `App/app/access.py` `owner_id`, `apartments`, `invoice_details_url`; `App/app/ttlock.py` `enabled`, `account_for`; `App/app/ai.py` `enabled_for`; `App/app/havel.py` `FEATURE`; `App/app/guest_slug.py` `link_key`; `App/app/config.py` `PUBLIC_BASE_URL`.
Go to build on: `go/internal/hostweb` (Login, Lang, Catalog, AppBase/PublicBase), `go/internal/session` (`Host`: account, workspace, role, impersonation), `go/internal/payments/connect.go` for handler shape.

Rules: `require_login` failing gives `{"items": []}` with 401 (no redirect), but acceptance-pending and other redirects from `require_login` also become that 401 (Python returns JSON for any guard); check `require_login` and match. Items in exactly Python's order with exactly Python's keys per item (absent keys absent, not null); `tone` an int. Keys in each JSON object in Python insertion order (write a small ordered encoder or per-item structs with field order matching Python; FastAPI `JSONResponse` uses `json.dumps(..., ensure_ascii=False, separators=(",", ":"))`, so match that: compact, UTF-8, no HTML escaping, use `json.Encoder` with `SetEscapeHTML(false)` and trim the newline). `owner_id` may be NULL for some roles: mirror the `? IS NULL OR` SQL. Strings from the host catalog: add every key used (`nav.*`, `command.*`, `dashboard.sync_calendars`, `stays.add_stay`, `host.*`, `settings.*`, `properties.shared.lock`, `users.incidents_link`, `reports.detail.title`, `havel.*`) to `go/internal/palette/i18n_keys.txt`, run `App/scripts/go_host_i18n.py`, embed. AI and TTLock checks read the same env and tables as Python; port only the branch logic these two calls need.
## 3. Files
Create: `go/internal/palette/palette.go` (split if over ~400 lines), `palette_test.go`, `i18n_keys.txt`, `i18n.json`. Edit: `go/cmd/ubyhost-web/main.go` (one route). Write `docs/tasks/0679-report.md`.
## 4. Steps
1. Package + route.
2. Golden parity test: a Python script `App/scripts/palette_golden.py` (stdlib + app imports, uses the test DB the same way existing golden scripts do; grep `golden` in `App/scripts/` and copy the closest pattern; if no pattern fits, skip the script and hardcode expected JSON in Go tests instead, say so) is optional. Required Go DB tests (skip without `UBYHOST_TEST_DATABASE_URL`): signed out -> 401 `{"items":[]}`; one property -> hub URLs use `/apartments/<id>?view=settings&section=...#...`; two properties -> `/apartments#property-summaries`; property with permalink token -> copy item with the public link; admin role adds the two admin items; TTLock off -> no lock item, on with account -> item; stays limited to 80 newest, archived left out, other owner's stays left out; submissions limited to 40; Czech language labels; exact byte output for one small fixture (hardcode the expected JSON string).
3. Commit: `0679: Go command-palette JSON API`.
## 5. Do not touch
`App/` (read only, except running the script), other Go packages except `main.go` (if `hostweb` lacks a helper, write a small private one in `palette` and say so), `go.mod`/`go.sum`, CI, compose, Caddy, templates, JS, CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/palette/ ./cmd/... -count=1 2>&1 | tail -30`.
- From `App/` (create `.venv` if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`): `.venv/bin/python scripts/go_host_i18n.py --check | tail -5`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
palette tests pass with the database URL set, 0 skipped; vet/gofmt/build clean; i18n check passes.
## 8. Stop and ask
Stop if the Python ranges no longer match, or a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0679-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
