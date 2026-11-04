# 0946: Payments pages match the mockup

Status: todo. 0945 is committed (HEAD). Executor: Haiku 5.5, two runs (steps 1-6, then 7-10). Do NOT commit, push or open a PR: the orchestrator commits. Never `git add -A`. Do NOT open screenshots: the orchestrator does.
Target: `docs/design/mockup/payments-v1.html` (screens `#home`, `#new`, `#setup`). Do not open it; every value you need is below.

## 1. Objective
`/payments` and `/payments/new` look like the mockup at 390, 768 and 1280 px: status card with green check, services as a list card with outline "Vyžádat" buttons and a "Přidat službu" row that opens the add form (`<details>`, works without JS), requests as cards (title, "no stay · date", dot+text status, amount right, actions below), setup as numbered steps (done = green check, current = coral number). `/payments/new`: big centred amount, chips instead of radio dots (real radios stay, hidden visually), full-width primary button, centred 560 px lane. From 1024 px the overview is two columns (services left, requests right); the hover-only desk tables go, so every row action is always visible. Decision: the primary button stays inline, full width; a fixed action bar would sit on the fixed tab bar (84 px) and the help bubble.
Keep: routes, form actions, field names, the add form as it is (no CSRF input added), `data-payments-setup`, `data-payments-step`, `data-payment-services`, `data-service`, `id="new-request"`, `data-confirm`, the macros' logic, every `{% if %}`, all copy keys.

## 2. Context (verified 2026-11-04)
- Tokens in `App/app/static/app2.css` line 2: `--acc` (coral #d0452d), `--ok`, `--oks`, `--warn`, `--ink`, `--ink3`, `--line`. `.tabs` is fixed at the bottom below 1024 px (line 240).
- `app2.css` line 80 hides `tbody tr .btn.sm.ghost` until hover: that is why "Vyžádat" is missing at 1280. Fixed by dropping the tables.
- `tests/test_payment_services.py` line 149 counts `[data-payment-services] [data-service]` == 2 (one per service, so only one markup copy).
- Selector `body.v2 .ui-field input:not(...)...` (app2.css line 1788) is (0,5,2); the amount rule below is (0,6,2) on purpose.

## 3. Files
Edit: `App/app/templates/payments.html`, `App/app/templates/payments_new.html`, `App/app/host_i18n.py` (2 lines), `App/app/static/app2.css` (append only), `App/app/templates/base.html` (line 22), `App/tests/static_versions.json` (via `--write`), `docs/design/catalog.json`, `App/tests/test_payments_layout_browser.py` (line 27 and docstring line 6). Create: `docs/tasks/0946-report.md`.

## 4. Steps

### Run 1 (templates, copy, CSS)
1. `payments.html` macros: lines 12, 28, 33 class `btn ghost sm` -> `payments-mini`. Lines 60-62 become:
   `<section class="card payments-state"><span class="payments-state-ic" aria-hidden="true">{{ icon('check', 22) }}</span><span class="t"><b>{{ t('payments.overview.on') }}</b><small>{{ t('payments.overview.on_sub') }}</small></span>{{ help_tip('pay-help-on', t('payments.help.stripe_role')) }}</section>`
2. `payments.html` setup list, lines 73-93 (`<ul class="setup-wizard-checklist" ...>` to `</ul>`) become:
   ```
   {% set ns = namespace(cur='') %}{% for step in setup.steps %}{% if not ns.cur and step.status != 'done' %}{% set ns.cur = step.key %}{% endif %}{% endfor %}
   <ul class="payments-steps" data-payments-setup>
     {% for step in setup.steps %}
     <li class="payments-step is-{{ step.status }}{% if step.key == ns.cur %} is-cur{% endif %}" data-payments-step="{{ step.key }}">
       <span class="payments-step-n" aria-hidden="true">{% if step.status == 'done' %}{{ icon('check', 18) }}{% else %}{{ loop.index }}{% endif %}</span>
       <span class="t"><span><b>{{ t('payments.setup.step.' ~ step.key) }}</b>{% if step.key in ['stripe', 'live'] %}{{ help_tip('pay-help-' ~ step.key, t('payments.setup.' ~ step.key ~ '_help')) }}{% endif %}</span>
       {% if step.key == 'details' and setup.entity %}<small>{{ setup.entity.name }}{% if setup.entity.contact_email %} · {{ setup.entity.contact_email }}{% endif %}</small>{{ ui_button(t('payments.setup.details_edit'), 'secondary', href=step.href, size='compact') }}
       {% elif step.key == 'details' %}<small>{{ t('payments.setup.details_missing') }}</small>
       {% else %}<small>{{ t('payments.setup.badge.' ~ step.status) }}</small>{% endif %}</span>
     </li>
     {% endfor %}
   </ul>
   ```
3. `payments.html` lines 110-152 (`<section data-payment-services>` to the requests `</section>`) become one `<div class="payments-cols">` ... `</div>` holding two sections:
   - `<section data-payment-services>` + the line-111 `<h2>` unchanged + `<div class="card payments-list">`, inside: `{% for s in services %}<div class="payments-row" data-service="{{ s.id }}"><span class="t"><b>{{ s.name }}</b><small>{{ s.amount_czk }} {{ t('payments.czk') }}</small></span>{{ svc_actions(s) }}</div>{% endfor %}` then `<details class="payments-add"{% if not services %} open{% endif %}><summary class="payments-row"><span class="t"><b>{{ t('payments.overview.add_service') }}</b><small>{{ t('payments.services.add_sub') }}</small></span>{{ icon('chevron-right', 20) }}</summary>` + the old add form (lines 127-133) with these changes: `<form class="payments-add-form" method="post" action="/payments/services">`, `<div class="ui-pair">` -> `<div class="payments-add-grid">`, no `<section>`/`<h2>` around it; then `</details></div></section>`.
   - `<section>` + the line-135 `<h2>` unchanged + `{% if requests %}{% for req in requests %}{% set tone = 'p-ok' if req.status == 'paid' else 'p-warn' if req.status in ['sent', 'awaiting_payment'] else 'p-n' %}<div class="card stay"><span class="in"><b>` + the line-139 name expression + `</b><small>{% if not req.reservation_id %}{{ t('payments.field.no_stay') }} &middot; {% endif %}{{ req.created_at | date_cz }}</small><span class="pill {{ tone }}">{{ t('payments.status.' ~ req.status) }}</span></span><span class="payments-amt">{{ req.amount_czk }} {{ t('payments.czk') }}</span><div class="payments-acts">{{ req_actions(req) }}</div></div>{% endfor %}{% else %}{{ empty_state(t('payments.list.empty_title')) }}{% endif %}</section>`.
   No `stays-phone`, `stays-desk` or `<table>` remains in the file.
4. `payments_new.html`: move line 16 `<div class="payments-page">` above line 15 and make it `<div class="payments-page payments-new">`. Line 17 -> `<div class="payments-form" id="new-request">`. Line 19 `<div class="ui-field">` -> `<div class="ui-field payments-amount">` and add `inputmode="numeric"` to that input. Line 38 `<div class="ui-chips">` -> `<div class="ui-chips payments-seg">`. Nothing else.
5. `host_i18n.py`: after the line `"payments.overview.add_service": "Add a service",` add `        "payments.services.add_sub": "Save what you charge often",`; after `"payments.overview.add_service": "Přidat službu",` add `        "payments.services.add_sub": "Uložte si, co účtujete často",`. Find both with `grep -nF`.
6. Append at the very end of `app2.css` (after the 0945 block), exactly:
   ```
   /* 0946 payments mockup fidelity (v2) */
   body.v2 .payments-state{display:flex;align-items:center;gap:14px;padding:18px 22px}body.v2 .payments-state-ic{width:44px;height:44px;border-radius:50%;background:var(--oks);color:var(--ok);display:grid;place-items:center;flex:none}
   body.v2 .payments-state .t,body.v2 .payments-row .t,body.v2 .payments-step .t{flex:1;min-width:0}body.v2 .payments-state b{display:block;font-size:17px;font-weight:700}
   body.v2 .payments-state small,body.v2 .payments-row small,body.v2 .payments-step small{display:block;color:var(--ink3);font-size:14px;margin-top:2px}body.v2 .payments-cols h2{font-size:13px;font-weight:700;color:var(--ink3);text-transform:uppercase;letter-spacing:.06em;margin:28px 0 12px}
   body.v2 .payments-list{padding:6px 22px}body.v2 .payments-row{display:flex;align-items:center;gap:12px;min-height:56px;padding:12px 0}
   body.v2 .payments-row+.payments-row,body.v2 .payments-row+.payments-add{border-top:1px solid var(--line)}body.v2 .payments-row b{display:block;font-size:17px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
   body.v2 .payments-row form,body.v2 .payments-acts form{margin:0}body.v2 .payments-mini{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border-radius:999px;border:1.5px solid var(--ink);background:#fff;color:var(--ink);font:inherit;font-size:14px;font-weight:700;white-space:nowrap;cursor:pointer}
   body.v2 .payments-add>summary{list-style:none;cursor:pointer}body.v2 .payments-add>summary::-webkit-details-marker{display:none}
   body.v2 .payments-add[open]>summary svg{transform:rotate(90deg)}body.v2 .payments-add-form{padding:0 0 16px}
   body.v2 .payments-add-grid{display:grid;grid-template-columns:minmax(0,1fr) 120px;gap:12px}body.v2 .payments-add-form .ui-form-actions{display:flex;margin-top:12px}
   body.v2 .payments-page .card.stay{display:flex;flex-wrap:wrap;align-items:center;gap:12px 16px;padding:16px;margin:0 0 14px}body.v2 .payments-page .card.stay .in{flex:1;min-width:0;display:flex;flex-direction:column;align-items:flex-start}
   body.v2 .payments-page .card.stay .in b{font-size:17px;font-weight:700;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}body.v2 .payments-page .card.stay .in small{color:var(--ink3);font-size:14px}
   body.v2 .payments-page .card.stay .pill{display:inline-flex;align-items:center;gap:6px;background:none;padding:0;margin-top:6px;font-size:13px;font-weight:700}body.v2 .payments-page .card.stay .pill:before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
   body.v2 .payments-page .card.stay .pill.p-ok{color:var(--ok)}body.v2 .payments-page .card.stay .pill.p-warn{color:var(--warn)}body.v2 .payments-page .card.stay .pill.p-n{color:var(--ink3)}body.v2 .payments-amt{font-weight:800;font-size:17px;white-space:nowrap}
   body.v2 .payments-acts{display:flex;flex-wrap:wrap;align-items:center;gap:12px;width:100%}body.v2 .payments-acts:not(:has(*)){display:none}
   body.v2 .payments-steps{list-style:none;margin:8px 0 20px;padding:0}body.v2 .payments-step{display:flex;gap:16px;align-items:flex-start;padding:16px 0}
   body.v2 .payments-step+.payments-step{border-top:1px solid var(--line)}body.v2 .payments-step-n{width:36px;height:36px;border-radius:50%;background:#f4f3ef;display:grid;place-items:center;font-weight:800;flex:none}
   body.v2 .payments-step.is-done .payments-step-n{background:var(--oks);color:var(--ok)}body.v2 .payments-step.is-cur .payments-step-n{background:var(--acc);color:#fff}
   body.v2 .payments-step b{font-size:17px}body.v2 .payments-step .ui-btn{margin-top:12px}
   body.v2 .payments-new{max-width:560px;margin:0 auto}body.v2 .payments-new fieldset.ui-field{border:0;margin:0 0 18px;padding:0;min-width:0}
   body.v2 .payments-new legend,body.v2 .payments-new .ui-field>label{display:block;font-size:13px;font-weight:700;color:var(--ink3);margin:0 0 6px;padding:0}body.v2 .payments-new .payments-amount input[type=number][name=amount_czk][id]{width:100%;min-height:64px;font:inherit;font-size:44px;font-weight:800;letter-spacing:-.02em;text-align:center;border:0;border-bottom:2px solid var(--line);border-radius:0;background:none;padding:8px 0;color:var(--ink);appearance:textfield;-moz-appearance:textfield}
   body.v2 .payments-amount input::-webkit-inner-spin-button,body.v2 .payments-amount input::-webkit-outer-spin-button{-webkit-appearance:none;margin:0}body.v2 .payments-new .payments-amount input[type=number][name=amount_czk][id]:focus{outline:0;border-bottom-color:var(--ink)}
   body.v2 .payments-new .ui-chip{position:relative;border:0;background:#f4f3ef;padding:0 18px;box-shadow:none}body.v2 .payments-new .ui-chip input{position:absolute;left:0;top:0;width:1px;height:1px;margin:0;opacity:0}
   body.v2 .payments-new .ui-chip:has(input:checked){background:var(--ink);color:#fff;box-shadow:none}body.v2 .payments-new .ui-chip:has(input:focus-visible){outline:2px solid var(--acc);outline-offset:2px}
   body.v2 .payments-seg{display:grid;grid-template-columns:1fr 1fr}body.v2 .payments-seg .ui-chip{justify-content:center}
   body.v2 .payments-new .ui-form-actions{display:block;margin-top:8px}body.v2 .payments-new .ui-form-actions .ui-btn{width:100%;min-height:50px;justify-content:center}
   @media (min-width:1024px){body.v2 .payments-cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;align-items:start}}
   ```
   `base.html` line 22: `app2.css?v=20261104-0945b` -> `app2.css?v=20261104-0946`. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. `docs/design/catalog.json`: after `"payments-box",` (line 344) add `"payments-state", "payments-state-ic", "payments-cols", "payments-list", "payments-row", "payments-mini", "payments-add", "payments-add-form", "payments-add-grid", "payments-amt", "payments-acts", "payments-steps", "payments-step", "payments-step-n", "payments-new", "payments-form", "payments-amount", "payments-seg"` (one per line, same indent); after the `"payments-box": ...` description line (1251) add one line each, `"<class>": "Payments mockup fidelity (0946).",`. Run: `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`.

### Run 2 (tests, screenshots, report)
7. `tests/test_payments_layout_browser.py` line 27 and docstring line 6: `screenshots-0945` -> `screenshots-0946`. Nothing else.
8. From `App/`: `.venv/bin/python -m pytest tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payment_rails.py tests/test_payments.py tests/test_payments_consent.py tests/test_payment_share_browser.py tests/test_payment_services.py -q --tb=short -x 2>&1 | tail -30`. Then (0 skipped): `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_payments_layout_browser.py tests/test_payments_setup_browser.py tests/test_payment_services.py tests/test_0901_hit_area_browser.py -q -rs --tb=short -x 2>&1 | tail -30`, then the same env with `tests/test_0710_v2_mockup_match_browser.py -k payments -q -rs --tb=short -x 2>&1 | tail -30`.
9. UX lint: `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30` (zero findings). Then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30`. Then from the repo root: `git checkout docs/tasks/screenshots-0729 docs/tasks/screenshots-0762 2>&1 | tail -30` and `git status --short 2>&1 | tail -30`.
10. Write the report. List the screenshot files in `docs/tasks/screenshots-0946/` (`ls 2>&1 | tail -30`); do not open them.

## 5. Do not touch
`App/app/routes/`, Stripe/webhook code, migrations, `payments_consent.html`, `payments_share.html`, `payments_qr.html`, `host_page.html`, `_components.html`, `_ui.html`, any existing CSS rule (0945 block included), any test other than step 7.

## 6. Commands
Only the ones in steps 6, 8, 9, 10.

## 7. Acceptance
- [ ] Step 6, 8, 9 commands green, 0 skipped, layout lint zero findings, ruff clean.
- [ ] `grep -cE 'stays-desk|stays-phone|<table' App/app/templates/payments.html` gives 0.
- [ ] `grep -c 'data-service=' App/app/templates/payments.html` gives 1.
- [ ] 27 PNGs in `docs/tasks/screenshots-0946/` (payments, payments-new, payments-consent x setup, complete, rows x 390, 768, 1280); `complete` is the empty state.
- [ ] `git status` shows no change under `screenshots-0729` or `screenshots-0762`; nothing committed.

## 8. Stop and ask
A line or anchor is not as quoted, a test fails twice, a fix needs CSS outside the 0946 block or a change to a test other than step 7, or the layout lint reports a payments finding.

## 9. Report
`docs/tasks/0946-report.md` (executor format, 600 tokens): files changed, each command's last 5 lines, §7 ticked, the screenshot list, Deviations, Questions. Set `Status: review`. No commit, no PR.

## 10. Owner steps
After merge and deploy: 1. Open /payments on the phone. 2. Tap "Přidat službu", then "Vyžádat platbu". Nothing else.
