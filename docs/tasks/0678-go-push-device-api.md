# 0678: Go push device API (turn on, refresh, turn off, remove a device)
Status: todo
Depends on: 0676 (hostweb) | Base commit: task/0676-go-hostweb | Branch: task/0678-go-push-api
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Port four of the five routes in `App/app/routes/push.py` to a new Go package `go/internal/pushweb`, as-is, and register them in `go/cmd/ubyhost-web/main.go`: `POST /account/push/subscribe`, `/account/push/refresh`, `/account/push/unsubscribe`, `/account/push/devices/{id}/delete`. `POST /account/push/test` stays in Python (it sends a push now, and the Go push sender does not exist yet). Production unchanged: Go container off.
## 2. Context
Python source of truth (read only these): `App/app/routes/push.py` (all, 139 lines); `App/app/push.py` 1-60 (constants), 57-60 `enabled`, 107-252 (`_hash`, `clean_subscription`, `count_for`, `save_subscription`, `_drop`, `remove`, `refresh`, `remove_endpoint`); `App/app/routes/passkeys.py` 79-93 `device_label` (port only what `_device` needs: the `en` label, and the `passkeys.default_name` comparison); `App/app/db.py` `audit` (grep `^def audit`); `App/app/security.py` `protect_host_post` (grep it; the push router sits under `admin.router`, so it runs before every route here). `App/app/auth.py` `current_user`/`workspace_user` only to confirm what `own_account` means with the Go `session.Host` (account vs workspace while an admin previews).
Go to build on: `go/internal/hostweb` (CSRF, Back, Flash, Lang, Catalog, Cookie), `go/internal/session` (`Load`, `Host`), `go/internal/ubyport` (exported `Audit`, `UTCNow`; grep `^func [A-Z]` in notify.go/store.go), `go/internal/payments/connect.go` for handler shape.

Rules: `own_account` is "signed in and not previewing" (no login redirect, no acceptance/paused redirect; those are `require_login`, which these routes do not call). JSON answers: same bodies, status codes and `Cache-Control: no-store` as `_answer`/`_error`; error texts from the host catalog in `hostweb.Lang` (add the `push.*`, `flash.push.*` and `passkeys.default_name` keys used to `go/internal/pushweb/i18n_keys.txt`, run `App/scripts/go_host_i18n.py`, embed). `_body`: over 8 KiB or bad JSON or non-object -> `{}`. Python `str(data.get(x) or "")` semantics for each field. `push.enabled()` reads env: copy the exact env rule (grep `def enabled` and `vapid_key`); if it needs the VAPID key to load, check only that the key env/file is present the way `enabled` does, and say how in the report. Endpoint hashing, length caps, device cap (`too many devices`), timestamps, SQL and audit details exactly as `push.py`. Device delete: form POST, `hostweb.Back` to `/settings#settings-group-phone` with the flash rules.
## 3. Files
Create: `go/internal/pushweb/pushweb.go` (split if over ~400 lines), `pushweb_test.go`, `i18n_keys.txt`, `i18n.json`. Edit: `go/cmd/ubyhost-web/main.go` (four routes, `m.wrap` pattern). Write `docs/tasks/0678-report.md`.
## 4. Steps
1. Package + routes (`{id}` not an integer -> 404).
2. DB tests (skip without `UBYHOST_TEST_DATABASE_URL`, setup copied from `payments/connect_test.go`): each route signed out -> 401 JSON (delete: flash redirect); admin previewing another workspace -> 401; bad CSRF refused; subscribe with push off -> 409; subscribe valid -> row with hashed endpoint, lang, device from a real iPhone UA, audit `push_device_added devices=1`; subscribe same endpoint twice -> one row (as Python); invalid subscription shapes (missing keys, http endpoint, too long) -> 400 failed; device cap reached -> 400 too_many; refresh known/unknown endpoint -> `{"known": true/false}` and lang updated; unsubscribe known -> row gone + audit `source=device`, unknown -> ok, no audit; device delete own -> gone + flash, other account's device -> untouched, plain redirect. Body over 8 KiB treated as `{}`.
3. Commit: `0678: Go push device API`.
## 5. Do not touch
`App/` (read only, except running the script), other Go packages except `main.go` (if `hostweb` or `ubyport` lacks a helper, write a small private one in `pushweb` and say so), `go.mod`/`go.sum`, CI, compose, Caddy, templates, JS, CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/pushweb/ ./cmd/... -count=1 2>&1 | tail -30`.
- From `App/` (create `.venv` if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`): `.venv/bin/python scripts/go_host_i18n.py --check | tail -5`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
pushweb tests pass with the database URL set, 0 skipped; vet/gofmt/build clean; i18n check passes.
## 8. Stop and ask
Stop if the Python ranges no longer match, or a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0678-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
