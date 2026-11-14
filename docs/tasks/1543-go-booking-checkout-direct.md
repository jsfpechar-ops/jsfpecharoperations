# 1543: Go booking checkout: direct payment requests (switched off)

Status: todo
Depends on: 1542 | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (guest data, two mails, bank details shown to a guest). Review: Opus orchestrator reads the risk-listed files.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1543 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1543 step'`, not a fixed base commit.

## 1. Objective

Finish `POST /p/{slug}/checkout` for `pay_mode=direct`: hold the dates for 24 hours, store a `requested` booking, write the audit line, queue the host's mail and the guest's mail with the payment details, then send the guest to the private booking page. After this brief the checkout path is served by Go for both pay modes, so it can be switched as a whole.

## 2. Context

Python mirrored (read-only, open only if a step fails): `App/app/booking_checkout.py` `start_direct` 133-164 and `REQUEST_HOURS` 130; `App/app/booking_direct.py` `notify_request` 115-138, `notify_request_guest` 141-172; `App/app/booking_rails.py` `guest_view` 123-154; `App/app/booking_site.py` `create_pending` 282-322; `App/app/payments.py` `qr_data_uri` 162-163, `normalise_account` 109-125, `format_iban` 128-129, `spayd` 140-150; `App/app/routes/property_page.py` lines 366-372 (the redirect to the manage path).

Parity table:

| Go | Python | Lines | Test |
|---|---|---|---|
| `Direct.Start` | `start_direct` | 133-164 | row status `requested`, pay method `direct`, 24 h hold and deadline `2026-11-29T10:00:00Z` for the clock 28 Nov 10:00 |
| `Direct.notifyHost` | `notify_request` | 115-138 | key `site_booking:<id>:request_host`, Czech text, link to `/apartments/<id>/booking-site` |
| `Direct.notifyGuest` | `notify_request_guest` | 141-172 | key `site_booking:<id>:request_guest`, rails text, `reply_to`, manage link |
| `GuestRails` | `guest_view` | 123-154 | order (host default first), IBAN grouped by four, SPAYD with `AM:6500.00`, variable symbol is the booking id |
| `payments.QRDataURI` | `qr_data_uri` | 162-163 | PNG bytes equal the QR PNG route's |

Money: nothing is charged. The amount printed in the mails and in the SPAYD code is the quote's total as a whole number (fixed test: 6 500 CZK, variable symbol `7`, message `STAY 7`, payload `SPD*1.0*ACC:CZ6508000000192000145399*AM:6500.00*CC:CZK*X-VS:7*MSG:STAY 7`).

Mails: queued through the existing outbox (`ubyport.EnqueueMail`) with Python's idempotency keys, so a request seen by both programs mails once. Payload text is Python's `json.dumps` (non-ASCII escaped). Mail backend off queues nothing. A mail failure is logged by kind and key only and never fails the request, as in Python. No address is logged.

Known differences (accepted): an account number on the legal entity that fails its check digits is an error here and in Python alike (Python raises ValueError, Go returns an error; the guest sees a 500, the request row exists with its hold, and the 24 hour expiry job frees it); `stay_fee_guest_default_rail` of `qr` counts as `iban`, as in Python.

No new outbound request (only queued mail). No schema change. No new personal-data field: the booking row already holds name and e-mail.

**Paths fully served by Go after this brief:** `/p/{slug}/checkout` (POST), both pay modes.

**Goes live on deploy:** nothing unless `UBYHOST_GO_PATHS` already holds `/p/*` or `/p/*/checkout`; then direct requests move to Go at once (brief 1550).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/payments/qrdatauri.go` | create (17 lines) | new file, copied from the sidecar |
| `go/internal/payments/qrdatauri_test.go` | create (23 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/direct.go` | create (316 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/direct_test.go` | create (170 lines) | new file, copied from the sidecar |
| `go/cmd/ubyhost-web/register_web_booking_checkout.go` | edit (step 2, one line) | passes `booking.Direct{...}.Start` as `c.Direct` |

No other file may change. `docs/tasks/1543-register-direct.patch` is the exact diff of the last row.

## 4. Steps

### Step 1: copy the files

From the repo root:

```bash
mkdir -p go/internal/payments && cp docs/tasks/1543-files/go/internal/payments/qrdatauri.go.txt go/internal/payments/qrdatauri.go
mkdir -p go/internal/payments && cp docs/tasks/1543-files/go/internal/payments/qrdatauri_test.go.txt go/internal/payments/qrdatauri_test.go
mkdir -p go/internal/web/booking && cp docs/tasks/1543-files/go/internal/web/booking/direct.go.txt go/internal/web/booking/direct.go
mkdir -p go/internal/web/booking && cp docs/tasks/1543-files/go/internal/web/booking/direct_test.go.txt go/internal/web/booking/direct_test.go
```

Expected: no output. Commit `1543 step 1`.

### Step 2: wire the direct starter

Anchor check, then apply the diff:

```bash
grep -nF 'pay_mode=direct answers "unavailable" until brief 1543 passes a Direct func.' go/cmd/ubyhost-web/register_web_booking_checkout.go | tail -3
git apply --check docs/tasks/1543-register-direct.patch 2>&1 | tail -5 && git apply docs/tasks/1543-register-direct.patch 2>&1 | tail -5
```

Expected: the grep prints one line; `git apply` prints nothing. The grep printing nothing: STOP (section 8). Commit `1543 step 2`. For live traffic this changes nothing: the route is not routed to Go yet.

### Step 3: check the files

```bash
sha256sum -c <<'EOT' 2>&1 | tail -10
7c0941057d2a72bec8a1e47828f40ed7991fe5838f6e24f7ce58d81a460ddb36  go/internal/payments/qrdatauri.go
944b13236ded0083f6e7fde474608d6dbf053a8855a5f6132a8ab01ab5aeb61e  go/internal/payments/qrdatauri_test.go
864f1cf31d5801874de524f8397109f70c1bd37d86570a30cb488b746621998b  go/internal/web/booking/direct.go
c895d9d4d1277b2094fedf775c215626bd0abfe8d0912cd0a2e80c223626b287  go/internal/web/booking/direct_test.go
EOT
sha256sum docs/tasks/1543-register-direct.patch | cut -c1-64
```

Expected: every line `OK`; the patch hash `2ff76e46fc319fc506361d0d84338ee413b486ead4e813120d93b749f99e004d`.

### Step 4: build, vet, format

```bash
cd go && go build ./... 2>&1 | tail -10 && go vet ./internal/payments/ ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10 && gofmt -l internal cmd 2>&1 | tail -5
```

Expected: no output.

### Step 5: tests (section 6), then the report (section 9).

## 5. Do not touch

Everything outside section 3. Hard rules: no new dependency; never push to `main`; no secrets; never log guest personal data or bank details.

## 6. Commands

```bash
cd go && go test -count=1 ./internal/payments/ ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10
```

Expected: `ok` for all three. The new tests need PostgreSQL (`UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres`; CI sets it); without it they skip. Say in the report which you ran.

## 7. Acceptance

- [ ] Step 3 printed only `OK` and the patch hash matches.
- [ ] `git log --oneline --grep='^1543 step' | tail -5` shows steps 1 and 2; `git show --stat --format=%s $(git log --grep='^1543 step 2' --format=%h -1) | tail -5` lists only `register_web_booking_checkout.go`.
- [ ] The three section 6 packages print `ok`, with the database variable set.
- [ ] `grep -c 'Direct' go/cmd/ubyhost-web/register_web_booking_checkout.go` prints 2 or more.

## 8. Stop and ask

Stop, and write the report, if: an anchor or a hash differs twice; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1543-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/booking/direct.go`: `Start` (refusals: demo, no rail, taken; hold length; audit), `GuestRails` and `guestIBAN` (bank details shown to a guest), `notifyGuest` (recipient, `reply_to`, link), the mail payload text.
- `go/cmd/ubyhost-web/register_web_booking_checkout.go`: the one added line.

## Owner steps

1. Nothing changes in production when this merges. Brief 1550 gives the switch order.
