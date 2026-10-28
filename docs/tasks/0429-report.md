# 0429 report: payments dashboard — connect card, request form, list

Status: review

## Files

- `App/app/routes/payments.py` (new): `/payments` section + POST
  `/payments/requests/new` (draft rows); reads the `stripe_account` mirror,
  never calls Stripe.
- `App/app/templates/payments.html` (new): connect card (all five mirror
  states + off), request form (stay, amount, reason chips, guest e-mail),
  request list, empty state; `ui_tip` help popovers (no-JS), the `?` copy:
  Stripe's role, payout timing.
- `App/app/host_i18n.py`: `payments.*` + `nav.payments` strings, en/cs.
- `App/app/main.py`: router included.
- `App/templates/_shell_sidebar.html`, `_shell_tabbar.html`: Payments nav
  (sidebar + phone More sheet); `_icons.html`: credit-card icon.
- `App/tests/test_payments_dashboard.py` (new): 10 tests.
- `tests/test_design_guardrails_browser.py`: `/payments` added to the layout
  guard ROUTES.
- Context: status.md, test-map.md (payments row), decisions (already had).

## Commands (last lines)

- `pytest tests/test_payments_dashboard.py` → 10 passed
- `pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py
  tests/test_stripe_connect.py tests/test_migrations.py` → 59 passed
- `python3 scripts/context_lint.py` → OK
- Browser/geometry row: `/payments` added to the guard routes; the local
  sandbox cannot launch Chromium (missing OS libs `libglib`), so the 390 px
  screenshot and the guard run in CI (browser shard) — owner: check the shard
  in the PR before merging (rule 7).

## Acceptance

- [x] All five mirror states render the right copy; button only in
      none/pending/action_required.
- [x] Draft creation works; invalid reason/amount/foreign stay refused with a
      flash.
- [x] Popovers work without JavaScript (`ui_tip`, real HTML in the response).
- [x] Test-map row updated; lint OK.
- [ ] Browser + geometry 0 skipped + 390 px screenshot — CI only (see above).

## Deviations

- `reservation` has no `owner_user_id`; ownership goes through
  `apartment.owner_user_id` via a join (the model's own tests create rows
  differently, but the route must use the join — same pattern as
  `access.reservation`).
- `ui_button` takes `type='submit'`, not `submit=true`.
- The state `none` (no `stripe_account` row) got its own copy line
  ("Connect your Stripe account…"), which the brief did not list; it is the
  first state a fresh host sees.

## Owner steps

1. Check the browser shard on the PR (the `/payments` page at 390 px).
2. Merge when green; deploy as usual.
3. Stripe Dashboard steps (0428-report.md) still stand for the live flow.
