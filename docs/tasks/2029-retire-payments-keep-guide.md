# 2029: Retire payments (OFF in production, kept in repo), keep the guide

Status: todo (owner decisions D1-D4 settled 2026-11-22, see Decisions)
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

### Step 1: one flag blocks the booking and payment routes (Go + Python mirror)
Add `UBYHOST_PAYMENTS_RETIRED` (1/true/yes) in `appconfig`. When set, `PaymentsHidden` is also true, and `PaymentsHostPathBlocked` additionally 404s ONLY these: `/apartments/*/page*` is NOT blocked unless step 1b finds it is booking-only; blocked are `POST /p/{slug}/book`, `/p/{slug}/checkout`, `/p/{slug}/thanks`, `/p/{slug}/b/*` (manage page and its `calendar.ics`), `/pay/*`, `/booking-sites*`. KEPT (also `/terms/booking`, served as the unavailable note in step 5) reachable: `GET /p/{slug}` (property page without booking), `/p/{slug}/{file}` (iCal feed), `/guide` and the guest guide view. Because the helper only sees the path, not the method, block `/p/{slug}/book` by path (it is POST-only). Grep exact patterns in `register_web_booking*.go` first. Keep `UBYHOST_PAYMENTS_HIDDEN` behaviour byte-identical when RETIRED is unset. Add rows to `payments_hidden_test.go`: each blocked path 404 with RETIRED=1; `/p/x`, `/p/x/feed.ics`, `/guide` not blocked. Mirror in `App/app/config.py` `payments_host_path_blocked`.
Files: `go/internal/appconfig/payments_hidden.go`, `payments_hidden_test.go`, `go/cmd/ubyhost-web/payments_hidden_test.go`, `App/app/config.py`.
Tests: `cd go && go test ./internal/appconfig/ ./cmd/ubyhost-web/ -run 'Payments|Blocked' 2>&1 | tail -30`; Python: `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_property_page.py -q --tb=short -x 2>&1 | tail -30`.
Stop if a blocked prefix collides with a non-booking route.

### Step 1b: property page without the booking widget (Go + Python template)
When retired, the property page renders with `Bookable` false so the `#book` section (`go/internal/web/booking/templates/property.tmpl:66`) and book/checkout CTA vanish; rest of the page (photos, rules, iCal link) unchanged. Set it in `go/internal/web/booking/property.go` (`PropertyPageHandler`) from `appconfig.PaymentsRetired(getenv)`. Python mirror: `App/app/routes/property_page.py` and `property_page.py` same condition. Files: `go/internal/web/booking/property.go`, its `_test.go`, `App/app/routes/property_page.py`, `App/app/property_page.py`. Tests: `go test ./internal/web/booking/ 2>&1 | tail -30`; Python `test_property_page.py test_property_page_meta.py`. UX: one 390 px screenshot of `/p/<slug>` (template change, so geometry and browser tests for that page, 0 skipped).

### Step 2: jobs off
In `register_jobs.go` when `PaymentsRetired`: do not schedule `stripe_sweep`; leave `billing_snapshot` running (see D1). Grep `scheduler.py` and `register_scheduler.go` for booking/payment-request/expiry jobs (`rg -n 'stripe|payment_request|booking' go/cmd/ubyhost-web/register_job*.go App/app/scheduler.py`) and skip those too. Update `job-ownership.md` row. A skipped job must log one line `job skipped: payments retired`, never error. Tests: `go test ./cmd/ubyhost-web/ -run 'Scheduler|Jobs' 2>&1 | tail -30`; Python: `scheduler_golden` only if the test-map row names it.

### Step 3: webhook neutral
When retired, `POST /webhooks/stripe` returns 200 with empty body before signature checks and writes nothing (so Stripe never retries forever, per the autopilot plan A2). Test: new case in `go/internal/payments/webhook_test.go` or `cmd` test. Do not delete the handler.

### Step 4: deploy config and Caddy (tier A review: touches deploy)
Compose: add `UBYHOST_PAYMENTS_RETIRED: ${UBYHOST_PAYMENTS_RETIRED:-}` next to line 169. Keep Stripe vars passthrough (needed for revival) but document them as dormant in `.env.example` and `docs/ENVIRONMENT.md` (one section). Check `UBYHOST_GO_PATHS` docs: remove the "Add `/webhooks/stripe`" advice only when retired; do not edit the live `.env`. Caddy: no path matcher is payment-specific beyond `UBYHOST_GO_PATHS`; confirm with `rg -n 'pay|webhook|/p/' deploy/lightsail/caddy` (only a comment-level change expected). Tests: `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`; CI job `caddy` checks both Caddyfiles.

### Step 5: legal and docs promises (drafts, lawyer pass)
Decision D3: retire the booking terms by serving a short "Booking is currently unavailable" note at `/terms/booking` instead of 404 (old e-mailed links keep working). Edit `go/internal/web/booking/templates/terms_en.html`, `terms_cs.html` and Python `App/app/templates/_booking_terms_{en,cs}.html`: keep the old text out of the live page but do NOT delete it from git (it is in history; revival restores it). Short note must follow rule 9 (one explanation, no tracking-cookie wording). Because of this, step 1 must NOT block `/terms/booking`; remove it from the step 1 blocked list when the executor reaches step 5 order conflict: step 1 blocks only the others. (Brief rule: `/terms/booking` stays out of the block list.) ROPA/RETENTION: add "dormant, off since <date>" to the Stripe/booking-site rows; keep retention lines. Run `python3 scripts/context_lint.py | tail -30`. Legal version bump is the lawyer's call.
Files: the four terms templates, `docs/privacy/ROPA.md`, `docs/privacy/RETENTION.md`.

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
No production pre-check is needed (owner confirmed nothing open exists).
1. Merge step 3 (webhook neutral) first and let it deploy. Then in Stripe Dashboard (test mode): Developers, Webhooks, open the UbyHost endpoint and disable it. Do not delete it and do not roll the signing secret, so revival is easy.
2. Keep `UBYHOST_STRIPE_SECRET_KEY` and `UBYHOST_STRIPE_WEBHOOK_SECRET` in the server `.env` (dormant) or blank them; set `UBYHOST_STRIPE_MODE=off`.
3. After steps 1-4 are merged and deployed, add `UBYHOST_PAYMENTS_RETIRED=1` to the server `.env` and run the normal deploy/restart.
4. Check in a browser: `/payments` shows "Page not found", sidebar has no Payments or Booking sites, a property page has no booking box, its iCal link still works, `/guide` works.
5. Revive later: remove `UBYHOST_PAYMENTS_RETIRED`, set Stripe mode and secrets, re-enable the Stripe webhook.

### Risks
- Blocking by path inside `/p/*` must not catch the iCal feed `/p/{slug}/{file}` (test it with a real `.ics` name) or `/p/{slug}/b/.../calendar.ics` confusion: the latter is a booking stay calendar and is retired.
- QR helper lives in `go/internal/payments`; do not gate package init.
- Python is still alive for some routes; both stacks must read the flag or one stack leaks payment pages.
- Legal text version bump re-triggers acceptance (A4); keep it separate and lawyer-led.
- Stripe retries failed webhooks for days; step 3 must ship before the owner disables anything.

### Decisions (owner, 2026-11-22)
- D1: host subscription billing and invoices stay ON (`billing_snapshot` keeps running).
- D2: retire only the booking and payment parts of `/p/*`; the property page and iCal feeds stay.
- D3: booking terms retired: `/terms/booking` serves a short unavailable note (old links keep working); old text stays in git history.
- D4: stay-fee guest-pay panel stays.
- No production count and no owner pre-check.

### Step order and parallelism
Order: 1, then 1b, 2, 3 (parallel after 1), then 4, 5, 6, 7.
- Parallel after step 1 (disjoint files): 1b (booking handler/templates, property_page.py), 2 (`register_jobs.go`, `scheduler.py`, scheduler tests), 3 (`register_web.go`, webhook test). Step 2 also touches `App/app/config.py` only if it needs the flag: it must read the flag from step 1; do not edit `config.py` in step 2.
- Parallel with the above (no overlap): 5 (terms templates, privacy docs) and 4 (compose, env docs, Caddy) once step 1 has landed.
- Sequential last: 6 (docs/test-map/status, shared files) then 7 (proof, report only).

## 7. Acceptance
- [ ] With `UBYHOST_PAYMENTS_RETIRED=1`: listed paths 404 in Go (tests green); `/guide` and UbyPort tests green.
- [ ] Without it: behaviour identical to today (existing tests unchanged).
- [ ] No migration, no deleted file, no secret in any diff.
- [ ] 390 px screenshots and per-page notes in step 7 PR.

## 8. Stop and ask
Any excerpt not found verbatim, any route prefix collision, any test needing a secret, or any step above 30 tool calls: stop and report.

## 9. Report

Per step: PR link, files changed, test output tail, screenshots (step 7), and any deviation.
