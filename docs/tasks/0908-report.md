# 0908 report: payments page in phone v2

Status: blocked. Two layout findings need a CSS or catalog decision (brief section 8: new CSS needed). PR not opened (owner or orchestrator opens it).

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
- Payments row (request model, services, dashboard, setup browser, stripe connect, new layout test, host i18n): `2 failed, 77 passed`. 0 skipped. The 2 failures are the findings below.
- `tests/test_layout_lint_browser.py`: `2 passed`, 0 skipped.
- `python3 scripts/context_lint.py`: OK (earlier run).
- Note: `tests/test_host_i18n.py` run alone shows 3 `no such table` failures on the base branch too (pre-existing, DB order). In the combined run above they pass.

## Per page (what I saw)
- `/payments` (lint fixture, Stripe off): 390: one card "Card payments are off on this server", no overflow. 768: same, centred lane. 1280: sidebar plus card, no overflow.
- `/payments/new`: 390: fields stacked, reason chips wrap, Card / Bank QR chips, full-width "Get link". The fixed bottom tab bar covers the lower fields in the full-page capture (capture artifact of the fixed bar). 768: single lane, chips wrap, button left. 1280: narrow centred form, chips in two rows, button left.
- `/payments`, setup state (`payments-setup-390.png`): step cards fit. FAIL: the "Upravit" link is 18 px high (existing 0729 setup markup, `setup-summary-action`), under the 44 px rule.
- `/payments`, rows state (`payments-rows-390.png`, test shot): FAIL: the row action buttons ("Požádat o platbu", "Získat odkaz", "Odebrat") run past the card's right edge. At 320, 390 and 768 the Get-link/Request button ends at 350, 420 and 790 px. Horizontal scroll at those widths. Needs CSS on the stacked action cell (or a catalog change), which the brief forbids.

## Deviations
- Header action is shown whenever Stripe is not off (per coordinator); label is the new key `payments.overview.request` ("Vyžádat platbu"), not the existing "Nová platební žádost".
- Service row button keeps the existing key `payments.services.request` ("Požádat o platbu"); the mockup says "Vyžádat".
- Add-service form stays inline under "Přidat službu" (no dialog). Rail column dropped from the request table.
- Setup state shows services and requests below the setup card too (brief does not forbid it).
- Primary-button check is automated for the body and the header (max one each); the "clipped primary text" check is not automated.

## Owner steps left
- Decide: fix the stacked action cell overflow and the 18 px "Upravit" link (CSS or catalog). Until then the layout test stays red; do not merge on green.
- Open the draft PR after that.
