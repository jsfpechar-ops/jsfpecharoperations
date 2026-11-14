# 1542: Go booking checkout: card payment through Stripe (switched off)

Status: review
Depends on: 1541 | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (money, guest data, an outbound request to Stripe). Review: Opus orchestrator reads the risk-listed files.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1542 step k` after each step. Acceptance checks use `git log --oneline --grep='^1542 step'`, not a fixed base commit.

## 1. Objective

Port `POST /p/{slug}/checkout` to Go: validate the guest's name, e-mail and terms, hold the dates under the same advisory lock Python takes, store the pending booking, open a Stripe Checkout Session on the host's connected account and show the page with the one link to Stripe. This closes the collision "`POST /p/{slug}/checkout` is Python only while `GET /p/{slug}/checkout` falls into Go's wildcard". `pay_mode=direct` is handed to a function that brief 1543 supplies; until then it answers the "unavailable" error.

## 2. Context

Python mirrored (read-only, open only if a step fails): `App/app/routes/property_page.py` `property_page_checkout` 331-391, `_field_error` 79-87, `_book_error` 318-324, `_EMAIL` 266, limits 267-268; `App/app/booking_checkout.py` `hold_dates` 23-51, `product_name` 59-63, `start` 66-130, `HOLD_MINUTES` 17, `SESSION_MINUTES` 19; `App/app/booking_site.py` `create_pending` 282-322, `set_status` 348-373, `attach_session` 376-380; `App/app/demo.py` `is_demo_apartment` 47-64; `App/app/db.py` `lock_key` 957-965, `audit` 2152.

Money computations (all amounts are whole Czech koruna, no rounding, no fee):

| What | Go | Python | Test with fixed numbers |
|---|---|---|---|
| Amount sent to Stripe | `CheckoutForm`: `unit_amount = AmountCZK * 100` | `booking_checkout.py` 95 `int(q["total_czk"]) * 100` | 6 500 CZK gives `650000` (`TestCheckoutFormFixedNumbers`) |
| Where the total comes from | `GetQuote` (1351, golden-tested) | `booking_site.quote` | apartment 1, 1 to 4 Dec 2026, 2 guests: 3 x 2 000 + 500 = 6 500 (`TestCheckoutCardHappyPath`) |
| Currency | `czk` | 94 | same test |
| Fee | none: no `application_fee_amount` field exists | no fee (direct charge, 0 %) | the test counts the 11 form fields |
| Session lifetime | `now + 31 * 60` s | 99 | `expires_at` equals clock + 1860 (`TestCreateCheckoutSession`) |
| Hold length | 15 minutes, stamp `YYYY-MM-DDTHH:MM:SSZ` | 17, 25-26 | hold expires `2026-11-28T10:15:00Z` |
| Idempotency | a random key per POST, like stripe-python | SDK default | two calls, two different keys |
| Signature | not involved (no webhook here) | | |

Behaviour copied on purpose: rate limit 20 per hour per client (scope `property_page_checkout`, answer `429 slow down`); the language is `cs` only when the form says `cs`; the typed name and e-mail come back in the page after a field error and never in a URL; a terms version that differs from `2026-11-03` redirects with `book=terms`; a Stripe failure deletes the hold and expires the booking; nothing about the card or the guest is logged (the log line holds the booking id and Stripe's error message and code only).

Known differences (accepted): the e-mail pattern is `_EMAIL` with Python's Unicode `\s` written out; the session id and URL must both be present in Stripe's answer, otherwise the booking is expired and the guest sees "unavailable" (Python would raise, with the same effect); no automatic Stripe retry (Python's SDK retries network errors twice with the same key; here the guest sees "unavailable" and the dates are freed).

**PR text (new outbound request):** `POST https://api.stripe.com/v1/checkout/sessions` with the connected account in `Stripe-Account`. Reason: the guest pays for a stay on the host's own Stripe account. Go makes the same call Python makes today in `booking_checkout.start`; it sends the guest's e-mail (so Stripe can send the receipt), the amount, the product name and the booking id. No card data passes through UbyHost. The call counts against `UBYHOST_STRIPE_MONTHLY_API_CALLS` like Python's.

**Paths fully served by Go after this brief:** `/p/{slug}/checkout` (POST only; Python has no GET there). The `direct` pay mode needs 1543 before the path is switched.

**Goes live on deploy:** nothing unless `UBYHOST_GO_PATHS` already holds `/p/*` or `/p/*/checkout`. If it does, card checkouts go to Go the moment this deploys, while direct requests would answer "unavailable" until 1543. Check the server value before merging (brief 1550).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_booking_checkout.go` | create (28 lines) | new file, copied from the sidecar |
| `go/internal/payments/checkout_session.go` | create (120 lines) | new file, copied from the sidecar |
| `go/internal/payments/checkout_session_test.go` | create (136 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/checkout.go` | create (471 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/checkout_test.go` | create (305 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/pay.tmpl` | create (7 lines) | new file, copied from the sidecar |

No other file may change. Not `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `register_web_booking.go`, anything under `App/`, and no other file of `go/internal/payments/`.

## 4. Steps

### Step 1: copy the files

From the repo root:

```bash
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1542-files/go/cmd/ubyhost-web/register_web_booking_checkout.go.txt go/cmd/ubyhost-web/register_web_booking_checkout.go
mkdir -p go/internal/payments && cp docs/tasks/1542-files/go/internal/payments/checkout_session.go.txt go/internal/payments/checkout_session.go
mkdir -p go/internal/payments && cp docs/tasks/1542-files/go/internal/payments/checkout_session_test.go.txt go/internal/payments/checkout_session_test.go
mkdir -p go/internal/web/booking && cp docs/tasks/1542-files/go/internal/web/booking/checkout.go.txt go/internal/web/booking/checkout.go
mkdir -p go/internal/web/booking && cp docs/tasks/1542-files/go/internal/web/booking/checkout_test.go.txt go/internal/web/booking/checkout_test.go
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1542-files/go/internal/web/booking/templates/pay.tmpl.txt go/internal/web/booking/templates/pay.tmpl
```

Expected: no output. Commit `1542 step 1`.

### Step 2: check the files

```bash
sha256sum -c <<'EOT' 2>&1 | tail -15
82405c6f42ecc184b81bf5c2c4374a8c950e987ad584cc43a09ce45f1b06c117  go/cmd/ubyhost-web/register_web_booking_checkout.go
064c1f8f62ba8b3a83b64950401b1a5800f955cae31e034a866b4845e25bd4e4  go/internal/payments/checkout_session.go
adf9183caba5b3dc0836b3074a86b7b7d1212c94c70d0e9dabd46349d5ec8c69  go/internal/payments/checkout_session_test.go
c6b3f0a723939567ed7e539c553b068c2e099ebcfea1bc76ef215581ea95361a  go/internal/web/booking/checkout.go
fc18b059e84115a1ddbc591fe5cf885645d07c328f6a4a8402112ccd2366276f  go/internal/web/booking/checkout_test.go
4ebb2b6fc4bee4a07f1bef43cc7bc1de87a6640fed47589bda00d000efc9ed68  go/internal/web/booking/templates/pay.tmpl
EOT
```

Expected: every line `OK`. `FAILED`: copy that file again once; still failing: STOP.

### Step 3: build, vet, format

```bash
cd go && go build ./... 2>&1 | tail -10 && go vet ./internal/payments/ ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10 && gofmt -l internal cmd 2>&1 | tail -5
```

Expected: no output.

### Step 4: tests (section 6), then the report (section 9).

## 5. Do not touch

Everything outside section 3. Hard rules: no new dependency (standard library, pgx, repo packages); never push to `main`; no secrets; never log card data, payment secrets or guest personal data; no tracking cookie.

## 6. Commands

```bash
cd go && go test -count=1 ./internal/payments/ ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10
```

Expected: `ok` for all three (the payments package takes about 20 seconds). The new tests need PostgreSQL: set `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres` (CI does); without it they skip. No test calls Stripe: the booking tests use a recorder, the payments test an `httptest` server. Say in the report which you ran.

## 7. Acceptance

- [ ] `sha256sum -c` of step 2 printed only `OK`.
- [ ] `git log --oneline --grep='^1542 step' | tail -5` shows step 1; `git show --stat --format=%s $(git log --grep='^1542 step 1' --format=%h -1) | tail -15` lists only section 3 paths.
- [ ] The three section 6 packages print `ok`, with the database variable set.
- [ ] `grep -c 'checkout/sessions' go/internal/payments/checkout_session.go` prints at least 2.
- [ ] No screenshot: no served page changes (pre-switch screenshots are brief 1550).

## 8. Stop and ask

Stop, and write the report, if: a hash differs twice; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1542-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/payments/checkout_session.go`: `CheckoutForm` (amount x 100, currency, metadata, no fee), `CreateCheckoutSession` (key, account header, error text carries no body).
- `go/internal/web/booking/checkout.go`: `HoldDates` (same lock key as Python: `hashtext('booking_site_dates')`, apartment id), `CreatePending` (stored guest data, token hash), `StartCard` (owner and account lookup, demo refusal, the failure path that frees the dates), `Handler` (order of checks, rate limit, ownership: the apartment comes from the slug, never from the form).
- `go/cmd/ubyhost-web/register_web_booking_checkout.go`: the adapter to Stripe.

## Owner steps

1. Nothing changes in production when this merges. Do not route `/p/*/checkout` to Go yet; brief 1550 gives the order and the rollback.
