# 2029: Retire payments (OFF in production, kept in repo), keep the guide

Status: todo (draft, needs owner decisions in the Decisions list before step 1)
Depends on: none | Base commit: b5127d006 | Branch: task/2029-retire-payments-<step>
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. Each step in section 4 is its own session and its own draft PR.

## 1. Objective

Turn the payments area (Stripe Connect, host Payments pages, booking-site direct payments, guest pay links, Stripe webhook, payment jobs) fully OFF in production while keeping all code, tables and data so it can be revived by flipping one flag. The host guest guide (`/guide`, guide import, AI guide, guest guide view, Leon) stays untouched and working.

## 2. Context (findings, verified by grep on b5127d006)

**The guide is independent of payments.** `App/app/routes/guest_guide.py`, `guest_guide_view.py`, `guest_leon.py`, `guest_guide_import.py`, Go `register_web_ai_guide.go`, `register_job_guide_import.go`, `register_web_guest_guide_view.go` contain no Stripe/payment code (the "booking" hits in `guest_guide_import.py` are Booking.com listing scraping, unrelated). Layout keeps `guide` as a nav key (`go/internal/hostweb/layout/layout.go:690`). Owner decision D1 in [autopilot-agentic](../plans/autopilot-agentic.md) already says "Hide Payments and Booking sites; the guide stays; delete code after Python is retired (A6)". This brief is plan step A2 (plus the env/Caddy/docs parts of A4).

**What already exists (hide flag).** `UBYHOST_PAYMENTS_HIDDEN` (`go/internal/appconfig/payments_hidden.go`, `App/app/config.py:352`). Go `m.wrap` (`go/cmd/ubyhost-web/main.go:64-67`) calls `hostweb.BlockedPage` (a plain 404 page, `go/internal/hostweb/notfound.go:47`) when `PaymentsHostPathBlocked` matches. Nav: Go layout sets `PaymentsHidden` (layout.go:681), Python templates use `payments_hidden()`; `reservations.html` and `reservation_detail.html` hide the "request payment" menu item. Compose already passes the flag (`deploy/lightsail/docker-compose.yml:169`, default empty = visible).

**Gaps in the existing flag** (why it is not "fully retired"):
1. Blocked paths are only `/payments*`, `/booking-sites`, `/apartments/{id}/booking-site*`. NOT blocked: `/apartments/{id}/page*` (host property-page editor), public `/p/{slug}*` (property page, book, checkout, thanks, manage, iCal), `/pay/*` guest pay links, `/terms/booking`, `/webhooks/stripe`. The comment in `payments_hidden.go` says these stay reachable on purpose.
2. Jobs keep running: `go/cmd/ubyhost-web/register_jobs.go:27` has `stripe_sweep` and `billing_snapshot` in `jobIntervals`; Python `scheduler.py` and `routes/stripe_connect.py` still reference Stripe.
3. Host-visible leftovers: layout fix-hint `"stripe"` -> `/payments#stripe-setup` (layout.go:515, already filtered at :637 by the flag; keep), onboarding wizard and apartment detail show property-page QR (`payments.QRDataURI`).
4. Shared helper: `go/internal/payments` `QRDataURI` is imported by `web/properties/apartment_detail.go`, `web/onboarding/wizard_data.go`, `web/stayfees/page_host.go`. Stay-fee QR must keep working, so the package cannot be removed or its init gated.
5. Docs/legal promise Stripe: `App/app/templates/_booking_terms_{en,cs}.html`, `go/internal/web/booking/templates/terms_*.html`, `docs/privacy/ROPA.md`, `docs/privacy/RETENTION.md`, `docs/ENVIRONMENT.md`, `.env.example`, `README.md`, `docs/HOSTEX.md`, test-map rows, `docs/context/status.md` ("Stripe test", "Billing ON").

**Not payments (must stay ON unless the owner says otherwise, see D1 in the Decisions list):** host subscription billing / invoices (`billing_snapshot`, `/billing`, `go/internal/billing*`, `platform_invoice`, `bank_payment`). Per autopilot-agentic line 52, host subscription billing does not use Stripe (bank transfer + invoices). Stay-fee guest-pay panel (`stay_fee_*`, Revolut/cash rails) is also not Stripe. UbyPort (`go/internal/ubyport`, submit_state, filing jobs) shares no code with payments; step 5 proves it.

**Go-first** ([go-first](../context/go-first.md)): all code changes are Go-side (flag, jobs, Caddy). Python gets only the minimum mirror (config + job skip) while Python still serves. No new dependency. No schema change, no migration.

## 3. Files (all steps together; each step lists its own subset)

| Path | Step | Action |
|---|---|---|
| `go/internal/appconfig/payments_hidden.go` (+ `_test.go`) | 1 | Add `PaymentsRetired(getenv)` and widen path blocking |
| `go/cmd/ubyhost-web/payments_hidden_test.go` | 1 | Extend table |
| `go/cmd/ubyhost-web/register_jobs.go` (+ `register_scheduler_test.go`) | 2 | Skip `stripe_sweep` and booking/payment jobs when retired |
| `App/app/config.py`, `App/app/scheduler.py` | 2 | Python mirror: same skip |
| `go/cmd/ubyhost-web/register_web.go` | 3 | `/webhooks/stripe` returns 200 and ignores body when retired |
| `deploy/lightsail/docker-compose.yml`, `.env.example`, `docs/ENVIRONMENT.md`, `deploy/lightsail/caddy/Caddyfile.*` | 4 | Env defaults, Caddy paths |
| `docs/privacy/ROPA.md`, `docs/privacy/RETENTION.md`, terms templates (4 files) | 5 | Legal/docs promises (lawyer pass flagged) |
| `docs/context/test-map.md`, `status.md`, `decisions.md`, `known-issues.md`, `docs/plans/autopilot-agentic.md` | 6 | Docs |

## 4. Steps (one executor session each; do in order, one draft PR each)

### Step 1: one flag blocks everything (Go + Python mirror of routing)
Add `UBYHOST_PAYMENTS_RETIRED` (1/true/yes) in `appconfig`. When set, `PaymentsHidden` is also true, and `PaymentsHostPathBlocked` additionally 404s: `/apartments/*/page*`, `/p/*` (all methods), `/pay/*`, `/terms/booking`, `/booking-sites*`. Webhook is NOT blocked here (step 3). Keep `UBYHOST_PAYMENTS_HIDDEN` behaviour byte-identical when RETIRED is unset (existing tests must pass unchanged). Add table rows to `payments_hidden_test.go`: each new path 404 with RETIRED=1, 200/untouched with it unset; guide paths `/guide`, `/g/...` (guest guide view route, grep `register_web_guest_guide_view.go` for the real pattern) never blocked. Mirror in `App/app/config.py` `payments_host_path_blocked` (same list) while Python serves.
Tests: `cd go && go test ./internal/appconfig/ ./internal/hostweb/... ./cmd/ubyhost-web/ -run 'Payments|Blocked|Layout' 2>&1 | tail -30`; Python: `.venv/bin/python -m pytest tests/test_payments_dashboard.py -q --tb=short -x 2>&1 | tail -30`.
Stop if `/p/` or `/g/` prefixes collide with a non-payments route (grep first).

### Step 2: jobs off
In `register_jobs.go` when `PaymentsRetired`: do not schedule `stripe_sweep`; leave `billing_snapshot` running (see D1). Grep `scheduler.py` and `register_scheduler.go` for booking/payment-request/expiry jobs (`rg -n 'stripe|payment_request|booking' go/cmd/ubyhost-web/register_job*.go App/app/scheduler.py`) and skip those too. Update `job-ownership.md` row. A skipped job must log one line `job skipped: payments retired`, never error. Tests: `go test ./cmd/ubyhost-web/ -run 'Scheduler|Jobs' 2>&1 | tail -30`; Python: `scheduler_golden` only if the test-map row names it.

### Step 3: webhook neutral
When retired, `POST /webhooks/stripe` returns 200 with empty body before signature checks and writes nothing (so Stripe never retries forever, per the autopilot plan A2). Test: new case in `go/internal/payments/webhook_test.go` or `cmd` test. Do not delete the handler.

### Step 4: deploy config and Caddy (tier A review: touches deploy)
Compose: add `UBYHOST_PAYMENTS_RETIRED: ${UBYHOST_PAYMENTS_RETIRED:-}` next to line 169. Keep Stripe vars passthrough (needed for revival) but document them as dormant in `.env.example` and `docs/ENVIRONMENT.md` (one section). Check `UBYHOST_GO_PATHS` docs: remove the "Add `/webhooks/stripe`" advice only when retired; do not edit the live `.env`. Caddy: no path matcher is payment-specific beyond `UBYHOST_GO_PATHS`; confirm with `rg -n 'pay|webhook|/p/' deploy/lightsail/caddy` (only a comment-level change expected). Tests: `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`; CI job `caddy` checks both Caddyfiles.

### Step 5: legal and docs promises (drafts, lawyer pass)
Edit terms templates to a short "booking is currently unavailable" note ONLY if the owner confirms D3; otherwise leave templates and mark them dormant in the PR. ROPA/RETENTION: add "dormant, off since <date>" to the Stripe/booking-site rows; do not delete retention lines (data is kept). Run `python3 scripts/context_lint.py | tail -30`. Version bump of legal texts is the lawyer's call, not the executor's.

### Step 6: docs and status
test-map: mark the payments rows "dormant, run only when reviving". `status.md` (5 lines max): "Payments retired (flag), Stripe off". Append decision lines. `autopilot-agentic.md` A2: mark done. Do NOT mark A6 (code deletion) done.

### Step 7: proof that the guide and UbyPort are unaffected (no code change; report only)
With `UBYHOST_PAYMENTS_RETIRED=1` run: `go test ./internal/ubyport/... ./internal/hostweb/... 2>&1 | tail -30`; Python test-map rows "Guest pages / guide" and filing. Browser/UX gate: one 390 px screenshot of `/guide`, the host dashboard and the side nav (confirm no Payments / Booking site item at 390/768/1280); `test_layout_lint_browser.py` green, 0 skipped. Write what was seen per page in the PR.

## 5. Do not touch
`go/internal/ubyport`, `submit_state`, filing jobs, `go/internal/payments` package layout (QR helper is shared), any `App/migrations_pg/*`, any `DROP`/`DELETE` SQL, live `.env`, secrets. No code deletion (that is plan A6, after Python retires).

## 6. Commands

Test commands are inside each step (test-map rows only, each ending `| tail -30`).

### Data and migration implications
No migration. Tables kept: `payment_request`, `stripe_webhook_events`, `site_booking*`, `stripe_account` columns, billing tables. No data purge; retention windows keep running via `retention.py` (harmless on empty tables). Revival = unset the flag plus restore the Stripe env values; nothing to restore in the DB.

### Owner steps (plain words, never paste secrets into chat or PRs)
1. On the server run one read-only count and send me only the numbers: open payment requests and direct bookings (expected 0; plan A2 says never used).
2. In Stripe Dashboard (test mode is what production uses): Developers, Webhooks, open the UbyHost endpoint. Leave it enabled until step 3 is deployed (it then returns 200 and ignores events). After that you may disable the endpoint. Do NOT delete it or roll the signing secret if you want an easy revival.
3. Connected accounts: Stripe Dashboard, Connect, note any test connected accounts. Nothing to do for production hosts (none).
4. Keep `UBYHOST_STRIPE_SECRET_KEY` and `UBYHOST_STRIPE_WEBHOOK_SECRET` in `.env` as they are (dormant) or blank them; either way set `UBYHOST_STRIPE_MODE=off`. After the PR merges and auto-deploys, add `UBYHOST_PAYMENTS_RETIRED=1` to the server `.env`, then run the normal deploy/restart.
5. Verify in a browser: `/payments` shows "Page not found", sidebar has no Payments or Booking sites, `/guide` works.
6. Revive later: remove `UBYHOST_PAYMENTS_RETIRED`, set Stripe mode and secrets, re-enable the Stripe webhook.

### Risks
- `/p/*` blocking removes public property pages and iCal feeds (`/p/{slug}/{file}`) that hosts may have given to Airbnb/Booking. If any host syncs a calendar from UbyHost, they break. Owner must confirm D2.
- QR helper lives in `go/internal/payments`; do not gate package init.
- Python is still alive for some routes; both stacks must read the flag or one stack leaks payment pages.
- Legal text version bump re-triggers acceptance (A4); keep it separate and lawyer-led.
- Stripe retries failed webhooks for days; step 3 must ship before the owner disables anything.

### Decisions needed from the owner (before step 1)
- D1: "Subscriptions / predplatne": keep host subscription billing and invoices ON (they do not use Stripe) or retire too? Default: keep ON.
- D2: Retire the public property page and its iCal export (`/p/*`) too, or only the booking/payment parts? Default: retire all of `/p/*`.
- D3: Replace booking terms with an "unavailable" note, or leave dormant text? Default: leave dormant, mark in docs.
- D4: Keep the stay-fee guest-pay panel (not Stripe)? Default: keep.

## 7. Acceptance
- [ ] With `UBYHOST_PAYMENTS_RETIRED=1`: listed paths 404 in Go (tests green); `/guide` and UbyPort tests green.
- [ ] Without it: behaviour identical to today (existing tests unchanged).
- [ ] No migration, no deleted file, no secret in any diff.
- [ ] 390 px screenshots and per-page notes in step 7 PR.

## 8. Stop and ask
Any excerpt not found verbatim, any route prefix collision, any test needing a secret, or any step above 30 tool calls: stop and report.

## 9. Report

Per step: PR link, files changed, test output tail, screenshots (step 7), and any deviation.
