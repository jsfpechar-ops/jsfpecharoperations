# 0677: Go routes to create and send a payment request
Status: review
Depends on: 0676 (hostweb), 0675 (`SendPaymentLink`) | Base commit: task/0676-go-hostweb | Branch: task/0677-go-payment-requests
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 70k tokens
## 1. Objective
Port `POST /payments/requests/new` and `POST /payments/requests/{id}/send` (`App/app/routes/payments.py` 86-196) to Go, as-is, and register both in `go/cmd/ubyhost-web/main.go`. Production unchanged: the Go container is off and Caddy sends no path to Go.
## 2. Context
Python source of truth (read only these): `App/app/routes/payments.py` 1-60 (router has `protect_host_post`, `_off`) and 86-196; `App/app/payment_request.py` 1-130 (`REASONS`, `RAILS`, `STATUSES`, `_TRANSITIONS`, `create`, `_assign_variable_symbol`, `set_status`); `App/app/mail.py` `enqueue` (grep `^def enqueue`, about 231-290), `mail_enabled`, `normalise_email`, `GUEST_KINDS`; `App/app/auth.py` `require_login` (grep it) only to confirm hostweb.Login matches; `App/app/i18n.py` keys `mail_payment_request_subject` / `mail_payment_request_text` (Czech, the route always uses `lang = "cs"`).
Go to build on: `go/internal/hostweb` (Login, CSRF, Back, Flash, Lang, Catalog), `go/internal/payments/paylink.go` (`SendPaymentLink`, `ErrStripeOff`), `connect.go` (handler shape, how it gets the onboarder), `webhook.go` (`audit`), `go/internal/ubyport/notify.go` (`EnqueueMail`, `OutboxMail`, `writePyString`, `mailPayload`).

Handlers in new file `go/internal/payments/requests.go`, both POST only, in this order: `hostweb.CSRF`, `hostweb.Login`, then the Python body line by line. Workspace owner = `h.Workspace.ID` (that is `access.owner_id`). Flash texts come from the host catalog in the request language (`hostweb.Lang`): add every `payments.*` key the two routes use plus `payments.reason.*` to `go/internal/payments/i18n_keys.txt`, run `App/scripts/go_host_i18n.py`, embed `i18n.json`.
- new: form fields `reason`, `amount_czk` (Python `isdigit` and `>= 1`; note `isdigit` accepts only ASCII digits here after `strip`, check and match), `reservation_id` (owner check SQL as Python), `rail` default `card`, `guest_email`/`guest_note` stripped, empty -> NULL. `expires_at` = today (server local date, as `date.today()`; use the same clock rule Go code already uses for `date.today()`, grep `today` in go/internal) + 30 days ISO. Insert as `create` does (`currency` CZK, `status` draft, `created_at`/`updated_at` = `db.utcnow()` format, see `ubyport.UTCNow`); for `qr` set `variable_symbol` = id zero-padded to 10 in the same transaction. Redirect `/payments` with `payments.draft_saved`.
- send: row load, owner check, status check, resend flag, guest email check, card rail calls `SendPaymentLink` (ErrStripeOff -> `payments.err.stripe_off`; empty link -> `payments.err.not_ready`; other error -> 500 like `connectFail`), qr rail link `/payments/qr/<id>`; first send moves `draft -> sent` exactly as `set_status` (conditional UPDATE, `payment_request_status` audit `id=<id> draft->sent`); then the mail row, then `payments.sent`.
- Mail: port `mail.enqueue`'s guards for this call (mail off -> skip; demo stay skip if `payment_request` is in `GUEST_KINDS`; `normalise_email`; empty -> skip). Payload must be byte-identical to Python `json.dumps({"text": ..., "lang": "cs", "reply_to": ..., "apartment": None})` (default separators, `ensure_ascii=True`, key order as written); build it with the existing `writePyString`. Idempotency key `payment_request:<id>:sent:v1` or `v2` on resend. `reply_to` = `_host_reply_to` (two SQL lookups, payments.py 131-146). Smallest change to ubyport: add an optional pre-encoded `Payload string` field to `OutboxMail` (used instead of `mailPayload` when non-empty) and make `ApartmentID` nullable (`*int64`), updating the two existing callers. Subject cut to 200 as today.
## 3. Files
Create: `go/internal/payments/requests.go`, `requests_test.go`, `i18n_keys.txt`, `i18n.json`. Edit: `go/cmd/ubyhost-web/main.go` (two routes, same `m.wrap` pattern), `go/internal/ubyport/notify.go` + the two `OutboxMail` callers (only the two field changes). Write `docs/tasks/0677-report.md`.
## 4. Steps
1. Handlers + embed + main.go routes `POST /payments/requests/new`, `POST /payments/requests/{id}/send` (`{id}` not an integer -> 404, as FastAPI's int path).
2. DB tests (skip without `UBYHOST_TEST_DATABASE_URL`, setup as `connect_test.go`, fake Stripe as `paylink_test.go`): new: signed out -> login redirect; bad CSRF -> refused as Connect; bad reason, amount `0`, `-1`, `1.5`, empty -> err flash, no row; other owner's reservation -> err, no row; card draft saved (all columns), qr draft gets VS `000000000N`; redirect Location equals Python's exact string for Czech text (hardcode the expected quoted string). send: other owner -> invalid; status `paid` -> cannot_send; no email -> no_email; qr first send -> status sent, audit row, one email_outbox row with the exact payload bytes and key `:v1`; resend -> no status change, key `:v2`; card with Stripe off -> stripe_off flash and no mail; card ready -> link in the mail text; mail disabled -> no row but status still sent (as Python). ubyport tests stay green.
3. Commit: `0677: Go routes to create and send a payment request`.
## 5. Do not touch
`App/` (read only, except running the script), `webhook.go`, `onboarder.go`, `paylink.go` (call it only), `hostweb` (if a helper is missing, add it in `payments` and say so in the report), `go.mod`/`go.sum`, CI, compose, Caddy, templates, JS, CSS.
## 6. Commands
- Local Postgres (once): `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go build ./... && UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/payments/ ./internal/ubyport/ ./internal/hostweb/ ./cmd/... -count=1 2>&1 | tail -30`.
- From `App/` (create `.venv` if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`): `.venv/bin/python scripts/go_host_i18n.py --check && .venv/bin/python -m pytest tests/test_go_host_i18n.py -q 2>&1 | tail -5`.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
All listed Go tests pass with the database URL set, 0 skipped in payments; vet/gofmt/build clean; i18n check passes.
## 8. Stop and ask
Stop if the Python ranges no longer match, or a schema change or new dependency seems needed.
## 9. Report
`docs/tasks/0677-report.md`: command tails, `git diff --stat`, anything decided beyond section 2.
