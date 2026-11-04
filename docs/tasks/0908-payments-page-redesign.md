# 0908: Payments page in the phone v2 design

Status: todo. Owner OK on the mockup: 2026-11-04 (Josef, "Ok"). Executor: Haiku 5.5, two runs (steps 1-4, then 5-8).
Mockup (the visual target, Czech copy is final): `docs/design/mockup/payments-v1.html`. Open it with `#home`, `#new`, `#setup`.
Read first: AGENTS.md, docs/context/executor.md, docs/design/MASTER.md section 7 (grep `### 7.3`, `### 7.5`, `### 7.11`, `### 7.14`), docs/design/pages/payments.md.

## 1. Objective
`/payments` becomes the phone v2 screens in the mockup, built only from the closed MASTER catalog. No new CSS, no inline styles, no new components. If a mockup element has no catalog equivalent, use the nearest one and list it under "Deviations" in the report; never add CSS.

## 2. Context
Overview, new-request screen, redirects and error flow:
Screens:
- **Overview** `/payments` (template `payments.html`):
  1. Setup not done: the existing 4-step list stays as is (same markup, it already is the catalog setup card) and its one primary button. Only the copy changes (step 5 keys).
  2. Setup complete: one status row card "Platby kartou jsou zapnuté / Peníze chodí na váš účet" (a `row` with a `done` badge), then section "Vaše služby", then section "Požadavky".
  3. Header primary action (block `primary_action`): `Vyžádat platbu` -> `/payments/new`, only when Stripe is complete or rail QR is available (same condition the old form used; keep it).
  4. "Vaše služby": one `row` per service: primary = name, secondary = `{amount} Kč`, action = `secondary compact` link `Vyžádat` -> `/payments/new?service={id}`. Remove goes in the row menu (7.8) with the existing confirm. Last row "Přidat službu" opens a `dialog` (7.9, a bottom sheet on phone) holding the existing 2-field add form (POST `/payments/services`).
  5. "Požadavky": one `row` per request (primary = reason or note, secondary = guest name or "Bez pobytu" + date, badge = status, meta = amount `800 Kč`). Row actions stay exactly as today (Get link, Send, QR preview) inside the row menu / the one row action. Empty: `empty_state` keys unchanged.
  6. Stripe off / rejected / disabled: unchanged state copy, no list of services or requests.
- **New request** `GET /payments/new` (new template `payments_new.html`, body_kind `form`, back link `/payments`): fields in this order: amount (text_input type number, label "Částka (Kč)"), reason (the existing `ui-chips` radios, label "Za co"), stay (select, "Pobyt", first option "Bez pobytu"), guest e-mail ("E-mail hosta (nepovinné)"), rail ("Jak host zaplatí", Kartou / Bankovní QR chips). One primary submit `Získat odkaz` (card) ; keep the old draft behaviour: POST target `/payments/requests/new` unchanged, same field names (`reservation_id`, `amount_czk`, `reason`, `guest_note`, `guest_email`, `rail`). The old "What the guest pays for" note field stays but only shows when reason is `custom` (a plain `<details>` is NOT allowed; show it always below the chips with label "Poznámka (nepovinné)" if you cannot hide it without JS).
- **Old links keep working:** `GET /payments` with any of `service`, `reservation_id` in the query answers `303` to `/payments/new` with the same query string (the `#new-request` fragment survives the redirect). Do not edit the links in reservations.html / reservation_detail.html.
- Failed POST validation today redirects to `/payments` with a flash; point it at `/payments/new` instead (`_back("/payments", err=` inside `payment_request_new`, line 150-156 of App/app/routes/payments.py).

## 3. Files
Edit: `App/app/routes/payments.py` (`/payments` handler, new `/payments/new`, error redirects; `main.py` only includes the router), `App/app/templates/payments.html`, `App/app/host_i18n.py` (`payments.*` keys), `docs/design/pages/payments.md`, `App/tests/test_payments_dashboard.py`, `App/tests/test_payment_services.py`, `App/tests/test_payments_setup_browser.py`, `App/tests/test_design_guardrails_browser.py` (ROUTES).
Create: `App/app/templates/payments_new.html`, `docs/tasks/0908-report.md`, `docs/tasks/screenshots-0908/`.

## 4. Steps

### Run 1 (templates and routes)
1. `cd App && grep -n '"/payments' app/main.py` and read the `/payments` GET handler and the `payment_request_new` POST handler (lines 85-190, in two ranges). Add `GET /payments/new` that builds the same context the old form used (`stays`, `reasons`, `prefill`, `selected_reservation_id`) and renders `payments_new.html`. Add the 303 redirect at the top of the `/payments` handler. Run: `.venv/bin/python -m pytest tests/test_payments_dashboard.py -q -x 2>&1 | tail -20` (expect failures only in tests that fetch the old form on `/payments`; note them for step 7).
2. Rewrite `app/templates/payments.html` per section 1 (overview). Keep `data-payments-setup`, `data-payments-step`, `data-payment-services` attributes (tests use them).
3. Create `app/templates/payments_new.html` per section 1. Keep `id="new-request"` on the form.
4. Commit: `git add` the named files only (never `git add -A`). Run: `python3 ../scripts/context_lint.py | tail -20`.

### Run 2 (copy, tests, screenshots)
5. Add the new `payments.*` keys to `app/host_i18n.py` in Czech and English with matching keys (Czech wording as in the mockup, English natural, no "Connect/KYC/payout/webhook"). Literal keys only in `_flash(` calls. Run `.venv/bin/python -m pytest tests/test_host_i18n.py -q 2>&1 | tail -10` after `tests/test_payments_dashboard.py`.
6. Update `docs/design/pages/payments.md` (keep under 40 lines, no px, no colours): add `/payments/new`, the dialog, the redirect rule.
7. Fix the tests from step 1 and run the test-map row "Payments dashboard + rails" plus the design row: `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_services.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_links.py tests/test_payment_qr.py tests/test_payments_setup_browser.py -q -x 2>&1 | tail -30`.
8. Geometry and browser (Chromium, 0 skipped): extend `tests/test_payments_setup_browser.py` (or add `tests/test_payments_layout_browser.py`) so, for `/payments` in states setup / complete-with-services-and-requests / empty, and for `/payments/new`, at widths 320, 390, 768, 1024, 1280, 1440: no horizontal scroll, no element outside the viewport, every button/input/chip/row at least 44 px high at 390 and below, no clipped primary text, the one primary button per group. Then: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` (add `/payments/new` to ROUTES in `tests/test_design_guardrails_browser.py`). Expected: green, 0 skipped. Copy `/tmp/shots/layout-lint/payments*-{390,768,1280}.png` to `docs/tasks/screenshots-0908/`.

## 5. Do not touch
Payment link/Stripe/webhook code, migrations, reservations.html, reservation_detail.html, payments_share.html, payments_qr.html, payments_consent.html, host2.css and any other CSS.

## 6. Commands
Every command is written in the steps; use only those.

## 7. Acceptance
- All commands above green, 0 skipped; lint findings zero.
- Report `docs/tasks/0908-report.md`: per page "390: ...; 768: ...; 1280: ..." (what you saw), Deviations list, token note. Draft PR, branch `task/0908-payments-redesign`, never push to main.

## 8. Stop and ask
An anchor or handler is not where this brief says, a mockup element needs new CSS, or a test outside the named files fails: stop and report.

## 9. Report
`docs/tasks/0908-report.md` as in section 7.

## 10. Owner steps
After merge and deploy, open /payments on the phone once; nothing else to do.
