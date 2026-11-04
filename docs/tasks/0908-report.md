# 0908 report: payments page in phone v2

Status: review. Both findings from the first run are fixed with catalog patterns (no new CSS): request and service actions use `row-actions` with one visible `row-action-form` and the rest in `row_menu_begin/end`; the setup "Upravit" link is a compact secondary button. PR not opened (owner or orchestrator opens it).

## Files changed
- `App/app/routes/payments.py`: 303 redirect for `service` / `reservation_id`; `GET /payments/new`; failed-POST redirects to `/payments/new`.
- `App/app/templates/payments.html`: overview rewritten (setup card, status row, services and requests as card tables, inline add form). Header action `payments.overview.request` -> `/payments/new` whenever Stripe is not off.
- `App/app/templates/payments_new.html` (new): body_kind form, back link `/payments`, `id="new-request"`.
- `App/app/host_i18n.py`: 11 new keys (`payments.overview.*`, `payments.new.*`), Czech and English.
- `docs/design/pages/payments.md`: `/payments/new`, redirect rule, table rows (37 lines).
- `App/tests/test_payments_dashboard.py`, `App/tests/test_payment_services.py`: expectations updated (list needs Stripe on; service rows selected by `[data-service]`; complete copy).
- `App/tests/test_design_guardrails_browser.py`: ROUTES gets `payments-new`.
- `App/tests/test_payments_layout_browser.py` (new): setup, complete-with-rows, empty states at 320-1440 px.
- `docs/tasks/screenshots-0908/`: lint shots `payments-{390,768,1280}.png`, `payments-new-{390,768,1280}.png`; test shots `payments-{setup,complete,rows}-390.png`, `payments-new-{setup,complete,rows}-390.png`.

## Test results (UBYHOST_BROWSER_EXECUTABLE set, UBYHOST_REQUIRE_BROWSER=1)
- Payments row (request model, services, dashboard, setup browser, stripe connect, new layout test, host i18n): `79 passed`, 0 skipped.
- `tests/test_layout_lint_browser.py`: `2 passed`, 0 skipped (after the fix).
- `python3 scripts/context_lint.py`: OK (earlier run).
- Note: `tests/test_host_i18n.py` run alone shows 3 `no such table` failures on the base branch too (pre-existing, DB order). In the combined run above they pass.

## Per page (what I saw)
- `/payments` (lint fixture, Stripe off): 390: one card "Card payments are off on this server", no overflow. 768: same, centred lane. 1280: sidebar plus card, no overflow.
- `/payments/new`: 390: fields stacked, reason chips wrap, Card / Bank QR chips, full-width "Get link". The fixed bottom tab bar covers the lower fields in the full-page capture (capture artifact). 768: single lane, chips wrap. 1280: narrow centred form, chips in two rows.
- `/payments`, setup state (`payments-setup-390.png`): the setup steps fit; "Upravit" is now a 44 px compact secondary button in step 2.
- `/payments`, rows state (`payments-rows-390.png`, test shot): header action "Vyžádat platbu" fits. Services: one row with name, amount, the visible "Vyžádat" form button, and the row menu (three dots) holding Remove. Requests: one row with reason, date, status pill, amount and the visible "Získat odkaz" button (open card request). Nothing overflows at 320, 390 or 768.

## Deviations
- Header action is shown whenever Stripe is not off (per coordinator); label is the new key `payments.overview.request` ("Vyžádat platbu"), not the existing "Nová platební žádost".
- Service row button keeps the existing key `payments.services.request` ("Požádat o platbu"); the mockup says "Vyžádat".
- Add-service form stays inline under "Přidat službu" (no dialog). Rail column dropped from the request table.
- Setup state shows services and requests below the setup card too (brief does not forbid it).
- Primary-button check is automated for the body and the header (max one each); the "clipped primary text" check is not automated.

## Owner steps left
- Open the draft PR (the orchestrator opens it).
