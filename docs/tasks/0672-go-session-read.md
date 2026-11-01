# 0672: Go reads the Python host session cookie
Status: todo
Depends on: 0671 (#669) | Base commit: origin/main | Branch: claude/project-thread-m85z82
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
Every Go host route (first: Stripe Connect start/return, brief 0673) needs to know who is signed in, exactly as Python does. Add a Go package `go/internal/session` that verifies and issues the `ubyhost_session` cookie byte-compatible with Python, and loads the account and workspace from the database. Library only: no route, no `main.go` change, nothing in production changes.
## 2. Context
Python source of truth (read only these ranges): `App/app/auth.py` lines 29-57 (constants, `_impersonation_max_age`, `_serializer`), 225-339 (`issue_session`, `_session_payload`, `current_user`, `workspace_user`), 367-380 (`impersonation_expired`), 500-525 (`require_login`, only the login and acceptance parts); `App/app/acceptance.py` `DOCUMENTS`, `current_versions`, `pending` (lines 1-56). The serializer is itsdangerous `URLSafeTimedSerializer(secret, salt="ubyhost-session")`; read its source in `App/.venv/lib/python3*/site-packages/itsdangerous/` (`signer.py`, `timed.py`, `url_safe.py`, `_json.py`) for the exact key derivation (django-concat, SHA-1 HMAC), separator, base64 and zlib rules. The secret is the one `go/internal/secure` already loads (`loadSecret` in `datakeys.go`: export a `LoadSecret(getenv)` wrapper, nothing more).

What the package must do:
1. `Sign(secret string, payload map[string]any, now time.Time) string` and `Verify(secret, token string, now time.Time) (map[string]any, bool)`: same bytes as itsdangerous for the same payload and timestamp; Verify accepts compressed (leading `.`) payloads; max age 400 days, and 12 hours unless `rm` is truthy (`_session_payload`). JSON numbers decode as int64 where whole.
2. `Load(ctx, db *pgxpool.Pool, token string, now time.Time, getenv) (*Host, error)`: `Host{Account, Workspace Account; Impersonating, ImpersonationExpired bool; Payload map[string]any}` with `Account{ID int64; Username, Role string; SessionVersion int64}`. nil Host when no valid token, no active account (`active = 1`), or `session_version` differs from `sv`. `as` is honoured only for `role = 'admin'` and an active target; expired impersonation (`UBYHOST_IMPERSONATION_MAX_HOURS`, default 24, 0 = never; missing or non-int `ast` = expired) sets `ImpersonationExpired` and keeps Workspace = Account, as `workspace_user` does.
3. `AcceptancePending(ctx, db, userID, getenv) (bool, error)`: true when any of terms/privacy/dpa at the version from `UBYHOST_TERMS_VERSION` / `UBYHOST_PRIVACY_VERSION` / `UBYHOST_DPA_VERSION` (default `1.7` each) has no `legal_acceptance` row for that user.
Out of scope (0673 handles them in the route): staging no-login, the bootstrap/no-accounts shortcut, writing the expiry audit, the read-only check, CSRF.
## 3. Files
Create: `go/internal/session/session.go`, `go/internal/session/session_test.go`, `go/internal/session/testdata/tokens.json`, `App/scripts/session_golden.py`. Edit: `go/internal/secure/datakeys.go` (export only). Write `docs/tasks/0672-report.md`. Nothing else.
## 4. Steps
1. `App/scripts/session_golden.py`: with a fixed 40-character test secret, set `UBYHOST_SECRET_KEY` before importing `app`, freeze itsdangerous's timestamp (patch `get_timestamp` on the serializer's signer class) to 1798761600, call `auth.issue_session` for: plain; remember; admin impersonating with `ast`; with `rv` list; a payload long enough that itsdangerous compresses it. Write `{secret, timestamp, cases:[{name, payload, token}]}` to `go/internal/session/testdata/tokens.json`. Run it once from `App/` with `.venv/bin/python scripts/session_golden.py`.
2. `session.go`: Sign/Verify/Load/AcceptancePending as in section 2. SQL with `$n` placeholders, read-only queries. Comments name the Python lines.
3. Tests: every golden token verifies to its payload, and `Sign` reproduces each token exactly; a flipped byte, the wrong secret and a different salt fail; non-remember token valid at 11h59m, invalid at 12h01m; remember valid at 399 days, invalid at 401. Database tests (skip without `UBYHOST_TEST_DATABASE_URL`, apply the schema the way `go/internal/payments/webhook_test.go` does): wrong `sv` gives nil, inactive gives nil, admin `as` gives the target workspace, non-admin `as` is ignored, expired `ast` sets the flag, `AcceptancePending` true then false after inserting the three rows.
4. Commit: `0672: Go reads the Python host session cookie`.
## 5. Do not touch
Everything in `App/` except the new script; `go.mod`/`go.sum` (stdlib + pgx only); `main.go`, CI, compose, Caddy.
## 6. Commands
- Python venv (fresh container): from `App/`: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -3`.
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/session/ ./internal/secure/ -count=1 -v 2>&1 | grep -E "^(---|ok|FAIL|PASS)" | tail -30`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All session and secure tests pass with the database URL set, 0 skipped; golden tokens reproduce byte for byte; diff touches only the files in section 3.
## 8. Stop and ask
Stop if the Python ranges no longer match section 2, if itsdangerous output cannot be reproduced without a new dependency, or if a test needs a schema change.
## 9. Report
`docs/tasks/0672-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
