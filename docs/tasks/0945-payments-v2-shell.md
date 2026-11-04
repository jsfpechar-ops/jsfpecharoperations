# 0945: Payments pages in the v2 shell

Status: todo. 0908 is merged (on main). Executor: Haiku 5.5, two runs (steps 1-5, then 6-10).
Models to copy (open only the line ranges given): `App/app/templates/invoices.html` 17-83 (head, phone cards, desk table), `App/app/templates/privacy_requests.html` 1-10 (v2 form page with back header).

## 1. Objective
`/payments`, `/payments/new` and `/payments/consent` move from the old `host_page.html` ui-* look to the v2 shell (`{% set v2 = true %}`: light sidebar, phone tab bar, `app2.css`), like `/invoices`. Only the shell, markup classes and one CSS block change. Routes, form actions, field names, CSRF inputs, `data-payments-setup`, `data-payments-step`, `data-payment-services`, `data-service`, `id="new-request"`, `data-confirm`, copy keys and the row-action/row-menu behaviour stay. No money metrics, no descriptions on the page: help text sits under a "?" right after its title or label.

## 2. Context (verified 2026-11-04)
- v2 pages load only `tokens.css` + `app2.css` (`App/app/templates/base.html` lines 20-23), so old classes (`ui-section`, `ui-badge`, `ui-chip`, `setup-summary-*` outside `.wiz-page`) are unstyled there.
- Reused v2 classes: `.head.stays-head`, `.head-title-row`, `h1.big`, `details.ui-how.stays-how`, `.stays-head-actions`, `.round.stays-add.ph-only`, `.stays-phone` (cards below 1024 px), `.card.stays-desk` (table from 1024 px), `.card.stay`, `.in`, `.pill p-ok|p-warn|p-n`, `.btn`, `.btn.ghost.sm`, `.ui-field`, `.ui-pair`, `.ui-form-actions`, `help_tip` (`_components.html` line 10), `partials/settings_back_header.html`.
- Not in scope: `payments_share.html` (needs a Stripe link to reach) and `payments_qr.html` (extends `base.html`, print page). Separate brief later.

## 3. Files
Edit: `App/app/templates/payments.html`, `payments_new.html`, `payments_consent.html`; `App/app/static/app2.css` (append only); `App/app/templates/base.html` (line 22, cache key); `App/tests/static_versions.json` via `--write`; `docs/design/catalog.json`; `App/tests/test_payments_layout_browser.py`; `App/tests/v2_mockup.py`; `App/tests/test_design_guardrails_browser.py`; `App/tests/test_shell_lane_browser.py`.
Create: `docs/tasks/0945-report.md`, `docs/tasks/screenshots-0945/`.

## 4. Steps

### Run 1 (templates, CSS)
1. `payments.html` header lines 1-11: add `{% set v2 = true %}` as line 2; replace the `primary_action` line with `{% block page_title %}{% endblock %}{% block meta %}{% endblock %}{% block primary_action %}{% endblock %}{% block secondary_actions %}{% endblock %}`; imports become `empty_state, row_menu_begin, row_menu_end, help_tip` from `_components.html`, `ui_button` from `_ui.html`, `icon` from `_icons.html`; drop the `_ui_layout.html` import. Then the body starts:
   ```
   <div class="payments-page">
   <div class="head stays-head"><div class="head-title-row"><h1 class="big">{{ t('payments.title') }}</h1>
   <details class="ui-how stays-how" data-how="payments">
     <summary class="ui-how-toggle" aria-label="{{ t('how.toggle') }}">{{ icon('circle-help', 16) }}</summary>
     <div class="ui-how-body"><ol class="ui-how-steps">{% for n in (1, 2, 3) %}<li>{{ t('how.payments.' ~ n) }}</li>{% endfor %}</ol></div>
   </details></div>{% if not stripe_off %}<div class="stays-head-actions"><a class="btn" href="/payments/new">{{ t('payments.overview.request') }}</a></div><a class="round stays-add ph-only" href="/payments/new" aria-label="{{ t('payments.overview.request') }}">{{ icon('plus', 22) }}</a>{% endif %}</div>
   ```
   and the last line before `{% endblock %}` is `</div>`. Keep every `{% if %}` condition exactly.
2. `payments.html` status and setup (old lines 13-71): each old `<div class="ui-section">` becomes `<section class="card payments-box">`. Complete state: `<p><span class="pill p-ok">{{ t('payments.overview.on') }}</span>{{ help_tip('pay-help-on', t('payments.overview.on_sub') ~ ' ' ~ t('payments.help.stripe_role')) }}</p>` (the `ui_tip` goes). Setup: keep h2, the `payments.connect.*` paragraphs, the `<ul ... data-payments-setup>` (drop class `host-property-grid`), each `li` and the primary buttons (lines 57-68) as they are, except: delete `<p>{{ t('payments.setup.lead') }}</p>`; the step badge becomes `<span class="pill {{ 'p-ok' if step.status == 'done' else 'p-warn' if step.status == 'attention' else 'p-n' }}">{{ t('payments.setup.badge.' ~ step.status) }}</span>` (no ✓); the `stripe_help` / `live_help` `<span class="ui-sub">` lines become `{{ help_tip('pay-help-' ~ step.key, t('payments.setup.' ~ step.key ~ '_help')) }}` placed right after `<strong>...</strong>` inside one `<span>` wrapper: `<span><strong>..</strong>{{ help_tip(..) }}</span>` (only for `stripe` and `live`).
3. `payments.html` services and requests (old lines 72-156). Define two macros at the top of the file (after the imports, outside blocks, as `housebook.html` does): `svc_actions(s)` = old lines 82-91 verbatim, and `req_actions(req)` = old lines 123-147 verbatim; in both, button class `ui-btn ui-btn-secondary` becomes `btn ghost sm`. Then per section: `<section data-payment-services>` (services only; requests: `<section>`) holding `<h2>{{ t('payments.overview.services') }}{{ help_tip('pay-help-services', t('payments.services.empty')) }}</h2>` (requests: `<h2>{{ t('payments.overview.requests') }}{{ help_tip('pay-help-list', t('payments.help.payout')) }}</h2>`), then if rows exist: `<div class="stays-phone">` with one `<div class="card stay">` per row = `<span class="in"><b>NAME</b><small>DETAIL</small>PILL</span>` + `{{ svc_actions(s) }}` / `{{ req_actions(req) }}`; then `<div class="card stays-desk"><table aria-label="...">` with `<thead>` columns as the old `ui_table_begin` list and one `<tr>` per row (services `<tr data-service="{{ s.id }}">`, the phone card never carries `data-service`), last cell `<td class="row-actions">` + macro. Services: NAME `s.name`, DETAIL `{{ s.amount_czk }} {{ t('payments.czk') }}`, no pill. Requests: NAME old line 118 expression, DETAIL `{{ req.created_at | date_cz }} &middot; {{ req.amount_czk }} {{ t('payments.czk') }}`, PILL `<span class="pill p-n">{{ t('payments.status.' ~ req.status) }}</span>`. Services empty: nothing (the `ui-sub` line goes). Requests empty: `{{ empty_state(t('payments.list.empty_title')) }}`. Add-service form: `<section class="card payments-box"><h2>{{ t('payments.overview.add_service') }}</h2><form method="post" action="/payments/services">` + `<div class="ui-pair">` two `<div class="ui-field"><label for="pay-svc-name">` / `pay-svc-amount` + the same inputs with that `id` (drop class `ui-input`) `</div>` + `<div class="ui-form-actions">{{ ui_button(t('payments.services.add'), 'secondary', type='submit') }}</div></form></section>`.
4. `payments_new.html` and `payments_consent.html`: add `{% set v2 = true %}`; blocks `page_title`, `meta`, `primary_action`, `secondary_actions` empty (drop `back_url`/`back_label`); body starts `{% with href='/payments', title=t('payments.new.title') %}{% include "partials/settings_back_header.html" %}{% endwith %}<div class="payments-page">` (consent: `payments.consent.title`) and ends `</div>`. The old `<div class="ui-section" ...>` becomes `<div class="card payments-box" ...>` (keep `id="new-request"`). In `payments_new.html` each `<label class="ui-field"><span>X</span><input ...>` becomes `<div class="ui-field"><label for="pay-new-NAME">X</label><input id="pay-new-NAME" ...></div>` (NAME = field name, drop class `ui-input`), fieldsets keep `ui-chips`/`ui-chip`, the submit goes in `<div class="ui-form-actions">`. Consent: all legal copy stays; the submit goes in `<div class="ui-form-actions">`.
5. Append at the very end of `App/app/static/app2.css`, exactly:
   ```
   /* 0945 payments (v2) */
   body.v2 .payments-page h2{font-size:17px;font-weight:700;margin:28px 0 12px}
   body.v2 .payments-box{padding:20px 22px;margin:0 0 16px}
   body.v2 .payments-box>h2:first-child{margin-top:0}
   body.v2 .payments-page .setup-wizard-checklist{list-style:none;margin:16px 0;padding:0;display:grid;gap:12px}
   body.v2 .payments-page .setup-summary-card{display:flex;flex-wrap:wrap;align-items:center;gap:12px 14px;padding:16px;border:1px solid var(--line);border-radius:16px;background:var(--s)}
   body.v2 .payments-page .setup-summary-icon{width:40px;height:40px;border-radius:50%;background:var(--accs);color:var(--acc-text);display:grid;place-items:center;flex:none}
   body.v2 .payments-page .setup-summary-copy{display:flex;flex-direction:column;align-items:flex-start;gap:12px;min-width:0;flex:1}
   body.v2 .payments-page .ui-chips{display:flex;flex-wrap:wrap;gap:12px}
   body.v2 .payments-page .ui-chip{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border:1px solid #d9d9d4;border-radius:999px;background:var(--s);color:var(--ink);font-size:15px;font-weight:600;cursor:pointer}
   body.v2 .payments-page .ui-chip:has(input:checked){border-color:var(--ink);box-shadow:inset 0 0 0 1px var(--ink)}
   body.v2 .payments-page .card.stay form{margin:0}
   ```
   Then `base.html` line 22: `app2.css?v=0903b` -> `app2.css?v=20261104-0945`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Add `payments-page` and `payments-box` to `docs/design/catalog.json` ("classes" list plus a description entry like `"stays-add"`). Run: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Commit `0945 step 1-5` (`git add` named files only).

### Run 2 (tests, screenshots)
6. `tests/test_payments_layout_browser.py`: `screenshots-0908` -> `screenshots-0945`; `WIDTHS = (320, 390, 768, 1024, 1280, 1440, 1920)`; add `("/payments/consent", "payments-consent")` to `PAGES`; replace `if width == 390:` / its screenshot line with `if width in (390, 768, 1280):` saving `f"{slug}-{state}-{width}.png"`. States stay `setup`, `complete` (= empty), `rows`.
7. `tests/v2_mockup.py` after line 356 (`"name": "invoices"`) add: `{"name": "payments", "path": "/payments", "view": "stays", "phone_view": "pobyty", "phone_mockup": PHONE_MOCKUP_V2, "selectors": [".head h1"], "phone_selectors": [".tabs", ".tab.on", ".mh .big, .head h1", ".card.stay", ".stay .in b", ".stay .in small"], "missing_ok": {".tab.on": "payments is not a tab bar item", ".card.stay": "fixture has no payment service or request", ".stay .in b": "fixture has no payment service or request", ".stay .in small": "fixture has no payment service or request"}},`
8. Old-shell tests that used `/payments`: `tests/test_shell_lane_browser.py` line 18 `PAGES = ("/payments",)` -> `PAGES = ("/invoices/new",)`; `tests/test_design_guardrails_browser.py` line 447 `/payments?lang=en` -> `/invoices/new?lang=en`; same file after line 46 add `"payments-consent": "/payments/consent",` to `ROUTES`.
9. From `App/` (Chromium, 0 skipped): `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_links.py tests/test_payment_qr.py tests/test_payment_services.py -q --tb=short -x 2>&1 | tail -30`, then `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_payments_layout_browser.py tests/test_payments_setup_browser.py tests/test_payment_services.py tests/test_0901_hit_area_browser.py tests/test_shell_lane_browser.py "tests/test_design_guardrails_browser.py::test_sidebar_search_has_a_border" -q -rs --tb=short -x 2>&1 | tail -30`, then `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k payments -q -rs --tb=short -x 2>&1 | tail -30`.
10. UX gate: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30` (zero findings). Open `docs/tasks/screenshots-0945/{payments,payments-new,payments-consent}-{setup,complete,rows}-{390,768,1280}.png` and `/tmp/shots/layout-lint/payments*-{390,768,1280}.png`; check: v2 sidebar/tab bar, "?" right after its title, no text paragraph under a heading, ≥12 px between neighbours, one coral button per group. Commit `0945 step 6-10`.

## 5. Do not touch
`App/app/routes/`, Stripe/webhook/payment-link code, `host_i18n.py`, migrations, `payments_share.html`, `payments_qr.html`, `host_page.html`, any CSS outside the appended block, any existing app2.css rule.

## 6. Commands
Only the ones in the steps.

## 7. Acceptance
- [ ] Step 9 and 10 commands green, 0 skipped, layout lint zero findings.
- [ ] `grep -c 'set v2 = true' App/app/templates/payments*.html` gives 1 for payments, payments_new, payments_consent.
- [ ] `grep -nE 'ui-section|ui-sub|ui_tip|ui-badge' App/app/templates/payments.html` finds nothing.
- [ ] 27 screenshots in `docs/tasks/screenshots-0945/`; report has per page "390: ...; 768: ...; 1280: ...".

## 8. Stop and ask
An anchor or line is not as quoted (0908 not merged yet), a test fails twice, the fix needs CSS outside the 0945 block, or `/invoices/new` lacks the old-shell sidebar in step 8.

## 9. Report
`docs/tasks/0945-report.md` (executor format). Draft PR from branch `task/0945-payments-v2`, never push to `main`.

## 10. Owner steps
After merge and deploy: 1. Open /payments on the phone. 2. Tap "?" next to "Platby". Nothing else.
