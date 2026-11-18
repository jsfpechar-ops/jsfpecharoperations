# 1859: Hide host Payments and Booking sites (Python half, autopilot A2)

Status: todo
Depends on: owner-approved autopilot workstream A2 (Python first; Go half is a separate brief)
Base commit: `main` tip | Branch: `cursor/1859-hide-payments-py-2385`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B

> **Cloud agent mode.** Commit as `1859 step k`. Push the branch and open one draft PR when green.

## Open questions (orchestrator answers before execute)

Owner approved A2 2026-11-18. No open questions.

## 1. Objective

While `UBYHOST_PAYMENTS_HIDDEN=1`, hosts do not see Payments or Booking site in navigation or menus; every host URL under `/payments`, `/booking-sites`, and `/apartments/{id}/booking-site` answers **404** (logged in or out). Scheduler stops booking-checkout expiry (`expire_requests` in the mail job) and the `stripe_sweep` job (payment-request expiry). **Data stays** in the database. The host **guest guide** (`/guide`, including the payments section) stays. **`POST /webhooks/stripe` still returns 2xx** when Stripe is configured (unchanged contract in `routes/stripe_connect.py`). Default in code is hidden **off** (`0`).

## 2. Context

Hard rules: 2 privacy (no new personal data, no new outbound request); 5 SQL only through `db.py` helpers (no schema change here); 6 light mode, auth forms without JS; 9 copy unchanged except nav removal; 11 Go half is out of scope.

Today: Payments and Booking site sit in `_shell_sidebar.html`, `_shell_tabbar.html`, `_shell_v2.html`, `menu.html`, and stay rows link to `/payments?reservation_id=…`. `UBYHOST_STRIPE_MODE=off` already disables Stripe UI but still shows pages. A2 needs a dedicated flag so production can keep Stripe keys for webhooks while hiding unfinished host UI.

**Anchors** (`grep -nF`; missing → STOP §8):

- `App/app/config.py`: `STRIPE_MODE = os.environ.get("UBYHOST_STRIPE_MODE"`
- `App/app/routes/stripe_connect.py`: `@router.post("/webhooks/stripe")`
- `App/app/scheduler.py`: `("expire_requests", booking_checkout.expire_requests)`
- `App/app/scheduler.py`: `id="stripe_sweep"`
- `App/app/templates/_shell_sidebar.html`: `('/payments', 'credit-card'`
- `App/tests/test_stripe_connect.py`: `client.post("/webhooks/stripe"`

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/config.py` | edit | `PAYMENTS_HIDDEN` from `UBYHOST_PAYMENTS_HIDDEN` (default off); `payments_host_path_blocked(path)` |
| `App/app/main.py` | edit | Middleware: blocked host paths → 404 (HTML error page when appropriate) |
| `App/app/templating.py` | edit | Global `payments_hidden()` for templates |
| `App/app/scheduler.py` | edit | Skip `expire_requests` step and `stripe_sweep` schedule when hidden; no-op `_job_stripe_sweep` if invoked |
| `App/app/templates/_shell_sidebar.html` | edit | Omit payments + booking-sites nav rows when hidden |
| `App/app/templates/_shell_tabbar.html` | edit | Omit More-menu links; fix `more_nav` set |
| `App/app/templates/_shell_v2.html` | edit | Omit payments nav + tab highlight |
| `App/app/templates/menu.html` | edit | Omit payments row |
| `App/app/templates/reservation_detail.html` | edit | Hide request-payment links |
| `App/app/templates/reservations.html` | edit | Hide request-payment menu item |
| `docs/ENVIRONMENT.md` | edit | Document `UBYHOST_PAYMENTS_HIDDEN` under Connect payments |
| `App/tests/test_payments_hidden.py` | create | Hidden on: 404 routes, nav absent, webhook 200 when stripe off; hidden off: smoke from existing tests |
| `docs/tasks/1859-report.md` | create | Report (§9) |

## 4. Steps

0. `git checkout cursor/1859-hide-payments-py-2385` from `main`. Verify every anchor in §2.
1. Add `PAYMENTS_HIDDEN` and `payments_host_path_blocked()` in `config.py` (block `/payments*`, `/booking-sites`, `/apartments/*/booking-site*`; never block `/webhooks/stripe` or public `/p/` guest booking pages).
2. In `main.py` `cloudflare_connecting_ip`, before `call_next`, if `payments_host_path_blocked(request.url.path)`: return branded 404 HTML when `_wants_html(request)`, else empty 404.
3. Register `payments_hidden` in `templating.py` (reads `config.PAYMENTS_HIDDEN`).
4. Wrap nav and stay payment links per §3 templates.
5. In `scheduler.py`: when `config.PAYMENTS_HIDDEN`, do not append `expire_requests` to the mail job steps; do not `add_job` for `stripe_sweep`; `_job_stripe_sweep` returns immediately if hidden.
6. Add `docs/ENVIRONMENT.md` row for `UBYHOST_PAYMENTS_HIDDEN` default `0`.
7. Add `test_payments_hidden.py` (logged-in host, monkeypatch hidden on).
8. Run §6, UX gate (layout lint with hidden **off** — default test env), write report, push, open PR.

## 5. Do not touch

Go routes in `go/`; migrations; `guide.html` payments section; public property pages (`property_page.py`); Stripe mirror tables; `payment_request` / `booking_site` writers; `UBYHOST_STRIPE_*` semantics; deploy scripts.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_payments_hidden.py tests/test_booking_site_host.py tests/test_payments_dashboard.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -30`
- `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30` (0 skipped)

From repo root:

- `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- `UBYHOST_PAYMENTS_HIDDEN` unset or `0`: behaviour unchanged (existing tests pass).
- `PAYMENTS_HIDDEN` true: no `/payments` or `/booking-sites` in rendered nav for a signed-in host; `GET /payments`, `/booking-sites`, `/apartments/1/booking-site` → 404 when signed in; `POST /webhooks/stripe` with empty body → 200 when mode off (existing test contract).
- `expire_requests` not called from mail job when hidden (unit assertion or mock in `test_payments_hidden.py`).
- `stripe_sweep` not registered when hidden (inspect scheduler after `start()` in test, or mock).
- Guest guide `/guide` still 200 and still mentions payments section heading.
- `git diff --stat` only §3 paths plus this brief and report.

## 8. Stop and ask

Missing anchor; middleware breaks guest `/p/` book flow; webhook non-2xx when hidden; layout lint needs a skip; any file outside §3 required.

## 9. Report

`docs/tasks/1859-report.md`: commits, §6 output, layout-lint note, per-page screenshot only if layout lint flagged a touched page at 390 px.

## Risk list (for the reviewer)

- Stale deep links in e-mails to `/payments` → 404 (acceptable for A2).
- Go still serves some `/payments` paths when `UBYHOST_GO_PATHS` lists them (Go brief).

## Owner steps

1. Open the draft PR and skim the diff.
2. On staging, set `UBYHOST_PAYMENTS_HIDDEN=1` in `.env`, reload the stack, confirm Payments and Booking site are gone from nav and `/payments` is 404.
3. Send a test Stripe webhook to `/webhooks/stripe` and confirm **200** still arrives (Stripe dashboard or `stripe trigger`).
4. To show the UI again, set `UBYHOST_PAYMENTS_HIDDEN=0` or remove it and reload.