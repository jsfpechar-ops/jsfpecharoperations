# 0673: Go Stripe Connect start/return routes (guards only, Stripe injected)
Status: review
Depends on: 0672 (#673) | Base commit: origin/main | Branch: claude/project-thread-qv0fs6
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
## 1. Objective
Port the three Connect routes of `App/app/routes/stripe_connect.py` (`GET` and `POST /payments/connect/start`, `GET /payments/connect/return`) to Go with every guard Python applies before Stripe is called. The two Stripe calls stay behind an interface; brief 0674 implements it (HTTP, call budget, account create) and registers the routes. This brief adds no route to `main.go`: nothing changes in production.
## 2. Context
Python source of truth (read only these ranges): `App/app/routes/stripe_connect.py` 33-100; `App/app/auth.py` 225-260 (`issue_session`, `session_max_age`), 320-340 (`workspace_user`), 430-466 (`end_expired_impersonation`), 481-560 (`require_login`, `attach_session`), 647-660 (`session_issued_at`), 880-893 (`secure_cookies`); `App/app/security.py` 16-19, 62-95 (CSRF serializer, nonce binding, `csrf_token_valid`), 114-208 (site match, recovery location, `_require_csrf`); `App/app/billing.py` 49-50 and 140-150 (`enabled`, `entitlements` paused); `App/app/payments_consent.py` (whole, 29 lines); `App/app/db.py` 2122-2163 (`set_current_actor`, `audit`). Go to build on: `go/internal/session` (`Load`, `AcceptancePending`, `Sign`), `go/internal/secure` (`NewTimedSerializer`, `LoadSecret`), `go/internal/payments/webhook.go` (style, `audit`, `text`).

Behaviour, in Python's order:
1. **POST only, before anything else:** CSRF as `_require_csrf(guest=False)`: token from header `x-csrf-token`, else form field `_csrf`; valid when itsdangerous salt `ubyhost-csrf`, max age 400 days, payload `{"nonce": sha256hex(cookie ubyhost_csrf)}` (constant-time compare, empty cookie never matches). Invalid and not same-site (Origin, else Referer, else `Sec-Fetch-Site: cross-site`; www-insensitive host match against the request host or `UBYHOST_PUBLIC_BASE_URL` host; scheme rule of `_browser_site_matches`, Go sees `X-Forwarded-Proto`-less http behind Caddy so treat the request scheme as `http`) gives 403 JSON `{"detail":"Cross-site request rejected."}`. Invalid but same-site gives 303 to `_csrf_recovery_location`.
2. **Login** (`require_login`): no valid session gives 303 `/login?next=<path>`. Expired impersonation: write `impersonation_stopped`/`expired` audit rows for the target and the admin (deduplicated, actor = admin username, `actor_user_id` and `impersonator_user_id` = admin id), set a fresh plain session cookie (`uid`/`sv`/`iat` as `issue_session`, `iat` copied from the old payload or 0; cookie attrs as `attach_session`, Max-Age 12 h) and 303 to `/admin/customers?msg=<url-quoted impersonation.expired text>`. Text in `en`/`cs`/`vi` exactly as in `host_i18n.py` / `host_vi_i18n.py`; language from `?lang=`, then cookie `ubyhost_lang`, else `en`. Acceptance pending (not impersonating) gives 303 `/account/accept?next=<quoted path>`. POST, billing on (`UBYHOST_BILLING_ENABLED` 1/true/yes), not impersonating, and `billing_account.status = 'paused'` gives 303 `/predplatne?paused=1`.
3. **Off:** `UBYHOST_STRIPE_MODE` not `test`/`live` gives an empty 404.
4. **Workspace:** owner = `Host.Workspace.ID`. (Python's None case is the no-accounts dev shortcut; Go has no such case.)
5. **Start only:** no `audit` row with `action = 'payments_terms_accepted'` and `detail = 'version=2026-11-01'` for the owner gives 303 `/payments/consent`. Then `url, err := c.OnboardingLink(ctx, owner, base)` with base = `UBYHOST_APP_BASE_URL` else `UBYHOST_PUBLIC_BASE_URL` (default `http://127.0.0.1:8080`), trailing `/` trimmed; `ErrStripeOff` or `ErrNoEntity` logs a warning and gives 303 `/`; success gives 303 to `url`; any other error 500.
6. **Return only:** `c.HandleReturn(ctx, owner)`; `ErrStripeOff`/`ErrNoAccount` only log; then 303 `/`; any other error 500.

Known differences, write them in the file comment: staging no-login and the no-accounts dev shortcut are not ported (production never uses them); language does not read `request.state.lang`.
## 3. Files
Create: `go/internal/payments/connect.go`, `go/internal/payments/connect_test.go`. Write `docs/tasks/0673-report.md`. Nothing else.
## 4. Steps
1. `connect.go`: `type Onboarder interface { OnboardingLink(ctx context.Context, owner int64, baseURL string) (string, error); HandleReturn(ctx context.Context, owner int64) error }`, sentinels `ErrStripeOff`, `ErrNoEntity`, `ErrNoAccount`, and `ConnectStartHandler(pool, getenv, now, c Onboarder) http.HandlerFunc` (serves GET and POST) and `ConnectReturnHandler(...)`. Secret from `secure.LoadSecret(getenv)`. Audit inserts with `$n` placeholders. Comments name the Python lines. Read the POST body at most 64 KB.
2. Tests with a fake `Onboarder` (records calls). Database tests skip without `UBYHOST_TEST_DATABASE_URL` and set up the schema as `webhook_test.go` does; one test (no DB) checks the three expired texts equal the lines in `../../../App/app/host_i18n.py` and `host_vi_i18n.py`. Cases: no cookie redirects to login; mode off 404; consent missing redirects to `/payments/consent` and the fake is not called; consent present redirects to the fake URL with the right base; `ErrNoEntity` redirects `/`; return calls `HandleReturn` and redirects `/`; POST without token cross-site 403, same-site 303 to recovery; POST with a valid token (minted with `NewTimedSerializer(secret,"ubyhost-csrf")`) proceeds; paused billing POST redirects `/predplatne?paused=1` and GET does not; acceptance pending redirects; expired impersonation writes two audit rows, sets a cookie that `session.Verify` accepts without `as`, and redirects to `/admin/customers?msg=`.
3. Commit: `0673: Go Connect start/return routes behind an Onboarder`.
## 5. Do not touch
`App/` (read only), `main.go`, `go.mod`/`go.sum`, CI, compose, Caddy, any template, JS or CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ ./internal/session/ -count=1 -v 2>&1 | grep -E "^(---|ok|FAIL|PASS)" | tail -40`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All payments and session tests pass with the database URL set, 0 skipped; diff touches only the files in section 3 (plus this brief's Status line).
## 8. Stop and ask
Stop if the Python ranges no longer match section 2, if a test needs a schema change, or if a new dependency seems needed.
## 9. Report
`docs/tasks/0673-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
