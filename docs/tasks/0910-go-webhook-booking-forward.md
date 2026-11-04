# 0910: Go Stripe webhook forwards booking events to Python

Status: todo. Owner OK: 2026-11-04 (Josef asked to speed up the Stripe step; the fix was announced in the thread). Executor: Haiku 5.5, one run. CRITICAL: payments (a missed booking event loses a paid reservation).

## 1. Objective
Stripe will send ALL events to `/webhooks/stripe`. Python handles booking-site events (`App/app/booking_webhook.py`: confirm reservation, automatic refund when nights sold, mails, expire holds). Go's webhook (`go/internal/payments/webhook.go`) does not, and would record such an event as seen and do nothing. Make Go forward booking events untouched to Python and answer with Python's answer. Everything else stays in Go as it is.

## 2. Context
- Booking event = `event.type` is one of `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.expired`, `checkout.session.async_payment_failed` AND `data.object.metadata.site_booking_id` is truthy in the Python sense. Use the existing Go helper `truthy` (webhook.go, near line 430) on that value, so it is the same test as `booking_webhook.is_booking_event` (lines 23-25). Missing `data.object` or `metadata` (nil map) = not a booking event.
- Python `stripe_connect.process_event` (App/app/stripe_connect.py lines 400-421) checks `account.updated` first, then `is_booking_event`, then the payment-link `PAID_EVENTS`. So an event with `site_booking_id` goes ONLY to the booking handler, even when its object also has a `payment_link` or payment-request metadata. Go must do the same: forward it and do NOT run `processEvent`/`onPaid` for it. Without `site_booking_id` the event goes to `processEvent` as today.
- Order in the Go handler: rate limit, body read, off/secret checks, `verifyEvent`. The new check goes right AFTER a successful `verifyEvent` and BEFORE `processEvent`. Mode off still answers `ignored` without forwarding (Python reads the same `.env` and would ignore it too). A forged event never reaches Python from Go; Python checks the signature again from the same header and raw body (300 s tolerance; do not change the body or the header).
- Forward: read `UBYHOST_PY_WEBHOOK_URL` once in `WebhookHandler` (trimmed, like mode and secret); empty = `http://ubyhost:8080/webhooks/stripe` (service `ubyhost`, `expose: 8080`, network `web`, same network as `ubyhost-go` in `deploy/lightsail/docker-compose.yml`). Never the public URL: that goes through Caddy back to Go once `/webhooks/stripe` is in `UBYHOST_GO_PATHS` (loop).
- Request: `http.NewRequestWithContext(r.Context(), POST, url, bytes.NewReader(raw))` with the exact raw bytes. Copy only `Stripe-Signature`, `Content-Type`, and `CF-Connecting-IP` if present. Do not copy Host, Content-Length, Accept-Encoding, Connection or other hop headers (net/http sets them). One `http.Client` built once: `Timeout: 20 * time.Second`, `CheckRedirect` returns `http.ErrUseLastResponse`. One attempt, no retry in Go (Stripe retries). `net/http` only, no new dependency.
- Rate limit and client IP: Python keys on the peer, replaced by `CF-Connecting-IP` only when the peer is in `UBYHOST_TRUSTED_PROXY_CIDRS` (`App/app/client_ip.py`; production sets `172.16.0.0/12`, which includes the Go container). Caddy always overwrites `CF-Connecting-IP`, so copying it is safe and Python keys on Stripe's IP. Python's key is `<ip>:stripe_webhook`, Go's is `<ip>`: a forwarded event counts once in each bucket. Do not change either key.
- Reply: Python's status code and body (read at most 64 KiB with `io.LimitReader`) go back to Stripe through the existing `text` helper. Log a line when Python's answer is not 200 `ok` (a 200 `ignored` means Python's Stripe mode is off and the event is lost). Network error, timeout or body read error: log it and answer 502 `forward failed`, so Stripe retries. Python's 4xx/5xx/429 are passed through as they are (Stripe retries every non-2xx).
- Do NOT write `stripe_webhook_event` in Go for a forwarded event: Python records it only after its handler returned. A second delivery (Stripe retry, or Go forwarding a retry while the first is still running) is safe: Python skips a recorded id, and `_confirm` locks and re-reads the booking.
- Python's POST `/webhooks/stripe` has no CSRF dependency and no Host check, so a direct call from the Go container is accepted.

## 3. Files
- `go/internal/payments/webhook.go`: the check and the forward (small helpers `isBookingEvent(ev stripeEvent) bool` and `forwardToPython`; reuse `stripeEvent` and `truthy`).
- `go/internal/payments/webhook_forward_test.go` (new): tests below.
- `docs/ENVIRONMENT.md`: one row for `UBYHOST_PY_WEBHOOK_URL` next to the `UBYHOST_GO_PATHS` row (line 184); in that row change the sentence "Add `/webhooks/stripe` only after the owner has checked the Go webhook" to say booking events are forwarded to Python.
- `docs/context/decisions.md`: append `- 2026-11-04 | Go webhook forwards booking-site events to Python; booking logic not ported to Go yet | owner | 0910`. The file is near its token cap (2200): shorten an older line by wording only if `python3 scripts/context_lint.py` complains.
- `docs/tasks/0910-report.md`: the report.

## 4. Steps
1. Read `App/app/booking_webhook.py` (lines 1-26), `App/app/stripe_connect.py` (lines 400-421), `go/internal/payments/webhook.go` (lines 73-160, 186-275, 428-445) and `go/internal/payments/webhook_test.go` (lines 1-30, 100-175).
2. Add the check after `verifyEvent` as described in section 2.
3. Implement the forward as described. Copy the response status and body of Python's answer.
4. Tests in the new file, same package. Use `testPool(t)`, `seedHost`, `seedRequest`, `signFor`, `testNow`. The fake Python is `httptest.NewServer` that records each call (count, body bytes, headers) and answers a chosen status and body. Build the handler with a getenv that returns `test`, `whsec_test` and the fake server URL for `UBYHOST_PY_WEBHOOK_URL` (wrap `webhookEnv`). Build requests with `httptest.NewRequest` + `httptest.NewRecorder` so you can read the response body (`post` returns only the code). Cases:
   - table over the four event types, each with `metadata.site_booking_id` = "7": forwarded once, body and `Stripe-Signature` identical byte for byte, `Content-Type` and `CF-Connecting-IP` copied, Python's 200 `ok` returned, 0 `stripe_webhook_event` rows;
   - Python answers 500 `boom`: Go answers 500 `boom`; Python answers 400: Go answers 400;
   - Python down (start a server, take its URL, `Close()` it): 502 `forward failed`, 0 event rows; the same event again with Python up is forwarded (nothing in Go blocks the retry);
   - `checkout.session.completed` with `payment_status` "paid", `payment_link` of a seeded `sent` request AND `site_booking_id` "7": forwarded, the request stays `sent`, 0 event rows;
   - `checkout.session.completed` WITHOUT `site_booking_id` (same payment link, own request): not forwarded, event row written, request marked `paid`, as in `TestWebhookDatabase`;
   - not forwarded: `site_booking_id` "" ; no `metadata`; `payment_intent.succeeded` with `site_booking_id` "7"; `account.updated`;
   - bad signature with `site_booking_id`: 400, not forwarded; mode `off`: 200 `ignored`, not forwarded.
5. Run the commands; write the report.

## 5. Do not touch
Python files, templates, CSS, migrations, `main.go` routing, Caddy files, compose, other Go packages, the existing tests in `webhook_test.go`. Do not port any booking logic to Go. Do not add a dependency.

## 6. Commands
Setup Postgres: `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""; export UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres`. From `go/`: `go test -count=1 -v ./internal/payments/ 2>&1 | grep -E '^(--- |ok|FAIL|panic)' | tail -30` (no `--- SKIP` line allowed), `go vet ./... 2>&1 | tail -30`, `gofmt -l . | tail`. From the repo root: `python3 scripts/context_lint.py | tail -30`. Work in your own worktree, branch from the commit you are given, commit locally, do not push.

## 7. Acceptance
Forwarded events produce exactly one Python call and no Go-side event row; an event with `site_booking_id` never runs `onPaid` in Go; non-booking events behave as before; all test cases above pass with 0 skipped; vet, gofmt and context lint clean; no dependency added.

## 8. Stop and ask
Stop and report instead of guessing if: the Python service name or port in compose differs from `ubyhost:8080`, or `ubyhost-go` is not on network `web`; `stripeEvent` does not expose `data.object` as a map; `truthy` is missing; existing webhook tests break for a reason you cannot explain.

## 9. Report
`docs/tasks/0910-report.md`: what changed, test counts (pass and skip), any deviation.
