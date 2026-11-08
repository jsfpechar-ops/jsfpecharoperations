# 1007: Plan and billing "Change" card: marketing-style upgrade card, yearly strip, add-on row

Status: todo
Depends on: 1006 (its uncommitted edits in billing_plan.html and app2.css must be in the working tree; if `ui-page-narrow` is missing from billing_plan.html line 17, STOP) | Base commit: working tree after 1006 | Branch: current branch (do NOT create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The "Change" section on /predplatne shows three plain grey buttons ("Switch to Max", "Pay yearly", "Add TTLock door codes"). Replace them with one highlighted upgrade card (other plan, real price, one strong button), a slim "Pay yearly and save N%" strip, and a bordered TTLock row. All three keep the same POST /predplatne/zmena forms, csrf and hidden fields. Max hosts get no promo card, only a quiet "Switch to Standard" button.

## 2. Context

Rules: light mode only; tokens only (`var(--acc)`, `var(--accs)`, `var(--acc-text)`, `var(--line)`, `var(--bg)`, `var(--ink3)`); no JS, no `style=""`; no card in a card except the upgrade card and add-on row, which are the only inner boxes allowed (they are the "action" blocks); one primary per group; copy: no sentence the button already says; hosts are Czech/English, so every new key needs EN and CS.

Verified facts:
- Pricing source: `App/app/billing.py` lines 31-37: `BASE`, `MAX_EXTRA`, `TTLOCK = {"month": 49, "year": 470}` per apartment, `quote(apartments, plan, interval, ttlock=, whitelabel=)` returns `{"total": ...}` in whole Kč. Max price depends on apartment count, so prices are computed in the route, never hard-coded.
- Existing per-plan copy: only one sentence per plan, `billing.order.plan_standard` / `billing.order.plan_max` (host_i18n.py lines 6190-6191 EN, 6583-6584 CS). No bullet list and no "Recommended" copy exists, so: ONE sentence (the existing `billing.order.plan_max`), NO pill.
- `App/app/routes/billing.py` `_page()` (lines 35-52) builds the render context; `billing_order.apartments(owner)` gives the billed count.
- Existing keys reused: `billing.change.title`, `billing.change.to_plan` ("Switch to %(plan)s"), `billing.change.to_interval_year/_month`, `billing.change.ttlock_on/_off`, `billing.plan.name.*`, `billing.interval.*`, `billing.order.plan_max`, `billing.change.whitelabel_off`.
- Tokens: `--acc:#d0452d`, `--accs:#fdece8`, `--acc-text:#b83d28`, `--line`, `--bg` are in `App/app/static/app2.css` line 2.

Anchors (each must be found verbatim, else STOP, §8):
- `App/app/routes/billing.py`: line `        "invoices": billing_invoices.for_owner(owner) if acc else [],` and line `    quote = billing_order.quote(owner, values) if ok else None`.
- `App/app/templates/billing_plan.html`: the block from `{% if acc.status in ('active', 'overdue') %}` through the matching `{% endif %}` just before `{% call ui_section(t('billing.cancel.title')` (it contains `<div class="billing-change-row">`).
- `App/app/static/app2.css`: line starting `body.v2 .billing-change-row .ui-form-actions{` (last rule of the 1006 block) and the end of file.
- `App/app/templates/base.html`: contains `app2.css?v=`.
- `App/app/host_i18n.py`: two lines `"billing.change.apartments_note": ...` (one EN near 6227, one CS near 6620).
- `docs/design/catalog.json` line 5 `    "ui-section-card",`; `docs/design/design-system.md` line `## 6. How it is enforced`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/billing.py | edit | add `upgrade` to the context (step 1) |
| App/app/host_i18n.py | edit | 7 new keys, EN and CS (step 2) |
| App/app/templates/billing_plan.html | edit | replace the Change block (step 3) |
| App/app/static/app2.css | edit | append the 1007 block (step 4) |
| App/app/templates/base.html | edit | bump `app2.css?v=` (step 5) |
| docs/design/catalog.json | edit | add class names (step 6) |
| docs/design/design-system.md | edit | extend section 5b (step 6) |
| App/tests/test_billing_self_service.py | edit | add one test (step 7) |
| docs/tasks/1007-report.md | create | report |

No other file may change.

## 4. Steps

1. **Route.** In `App/app/routes/billing.py` `_page()`, after the line `    quote = billing_order.quote(owner, values) if ok else None` insert:
```
    upgrade = None
    if acc and acc.get("plan") in billing.PLANS and acc.get("billing_interval") in billing.INTERVALS:
        n = billing_order.apartments(owner)
        lock, brand = bool(acc.get("addon_ttlock")), bool(acc.get("addon_whitelabel"))
        other = "standard" if acc["plan"] == "max" else "max"
        month = billing.quote(n, acc["plan"], "month", ttlock=lock, whitelabel=brand)["total"]
        year = billing.quote(n, acc["plan"], "year", ttlock=lock, whitelabel=brand)["total"]
        upgrade = {
            "price": _kc(billing.quote(n, other, acc["billing_interval"], ttlock=lock and other != "max",
                                       whitelabel=brand)["total"]),
            "save_pct": round(100 * (12 * month - year) / (12 * month)) if month else 0,
            "ttlock_price": billing.TTLOCK["month"],
        }
```
   and in the render dict, after the line `        "invoices": billing_invoices.for_owner(owner) if acc else [],` add `        "upgrade": upgrade,`. Check: `cd App && .venv/bin/python -c "import app.routes.billing" 2>&1 | tail -30` prints nothing.

2. **Copy.** In `App/app/host_i18n.py` directly after the EN line `"billing.change.apartments_note": "The number of apartments follows the ones you have active.",` add:
```
        "billing.change.upgrade_per_month": "%(price)s Kč per month",
        "billing.change.upgrade_per_year": "%(price)s Kč per year",
        "billing.change.yearly_save": "Pay yearly and save %(pct)s %%",
        "billing.change.yearly_cta": "Pay yearly",
        "billing.change.ttlock_title": "TTLock door codes",
        "billing.change.ttlock_line": "Guests get their door code automatically. %(price)s Kč per apartment per month.",
        "billing.change.add": "Add",
        "billing.change.remove": "Remove",
```
   and directly after the CS line `"billing.change.apartments_note": "Počet apartmánů se řídí aktivními apartmány.",` add:
```
        "billing.change.upgrade_per_month": "%(price)s Kč měsíčně",
        "billing.change.upgrade_per_year": "%(price)s Kč ročně",
        "billing.change.yearly_save": "Platte ročně a ušetřete %(pct)s %%",
        "billing.change.yearly_cta": "Platit ročně",
        "billing.change.ttlock_title": "Kódy do dveří TTLock",
        "billing.change.ttlock_line": "Hosté dostanou kód ke dveřím automaticky. %(price)s Kč za apartmán měsíčně.",
        "billing.change.add": "Přidat",
        "billing.change.remove": "Odebrat",
```
   Check how other `%` characters are written in that file (`grep -n '%%' App/app/host_i18n.py | head -3 | cut -c1-150`); if the file does not double the percent sign in `%(...)s` strings, write a single `%`. Check: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30` green (en/cs parity).

3. **Template.** In `App/app/templates/billing_plan.html` replace the whole block from `{% call ui_section(t('billing.change.title'), tip=ui_tip('tip-billing-change', ...` through its `{% endcall %}` (keep the surrounding `{% if acc.status in ('active', 'overdue') %}` / `{% endif %}`) with:
```
{% call ui_section(t('billing.change.title'), tip=ui_tip('tip-billing-change', t('billing.change.apartments_note'))) %}
{% set other_plan = 'standard' if acc.plan == 'max' else 'max' %}
{% set other_interval = 'month' if acc.billing_interval == 'year' else 'year' %}
{% macro change_form(field, value) -%}
<form method="post" action="/predplatne/zmena">
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
<input type="hidden" name="field" value="{{ field }}"><input type="hidden" name="value" value="{{ value }}">
{{ caller() }}
</form>
{%- endmacro %}
{% if acc.plan != 'max' %}
<div class="ui-upgrade-card">
  <h3 class="ui-upgrade-name">{{ t('billing.plan.name.max') }}</h3>
  <p class="ui-upgrade-price">{{ t('billing.change.upgrade_per_' ~ acc.billing_interval, price=upgrade.price) }}</p>
  <p class="ui-sub">{{ t('billing.order.plan_max') }}</p>
  {% call change_form('plan', 'max') %}{{ ui_button(t('billing.change.to_plan', plan=t('billing.plan.name.max')), 'primary', type='submit') }}{% endcall %}
</div>
{% else %}
{% call change_form('plan', 'standard') %}<div class="ui-form-actions">{{ ui_button(t('billing.change.to_plan', plan=t('billing.plan.name.standard')), 'secondary', type='submit') }}</div>{% endcall %}
{% endif %}
{% if acc.billing_interval == 'month' %}
{% call change_form('billing_interval', 'year') %}
<div class="ui-upgrade-strip">{% if upgrade.save_pct > 0 %}<span>{{ t('billing.change.yearly_save', pct=upgrade.save_pct) }}</span>{% endif %}{{ ui_button(t('billing.change.yearly_cta'), 'secondary', type='submit') }}</div>
{% endcall %}
{% else %}
{% call change_form('billing_interval', 'month') %}<div class="ui-form-actions">{{ ui_button(t('billing.change.to_interval_month'), 'secondary', type='submit') }}</div>{% endcall %}
{% endif %}
{% if acc.addon_whitelabel %}
{% call change_form('addon_whitelabel', '0') %}<div class="ui-form-actions">{{ ui_button(t('billing.change.whitelabel_off'), 'secondary', type='submit') }}</div>{% endcall %}
{% endif %}
{% if acc.plan != 'max' %}
{% call change_form('addon_ttlock', '0' if acc.addon_ttlock else '1') %}
<div class="ui-addon-row"><div class="ui-addon-text"><strong>{{ t('billing.change.ttlock_title') }}</strong><span class="ui-sub">{{ t('billing.change.ttlock_line', price=upgrade.ttlock_price) }}</span></div>{{ ui_button(t('billing.change.remove' if acc.addon_ttlock else 'billing.change.add'), 'secondary', type='submit', attrs='aria-label="' ~ t('billing.change.ttlock_' ~ ('off' if acc.addon_ttlock else 'on')) ~ '"') }}</div>
{% endcall %}
{% endif %}
{% endcall %}
```
   The old `billing-change-row` markup is gone. If Jinja rejects `{% macro %}` with `caller()` inside a `{% call %}` block (render error), move the macro above the `{% call ui_section(...) %}` line; if it still fails, STOP. If `ui_button` does not accept `attrs=` with a string (see how line `ui_button(t('billing.order.ares'), 'secondary', type='submit', attrs='name="do" ...')` already uses it: it does), keep as written. Check: `grep -c "billing-change-row" App/app/templates/billing_plan.html` prints 0.

4. **CSS.** Append at the very end of `App/app/static/app2.css`:
```
/* 1007: billing upgrade card, yearly strip, add-on row. */
body.v2 .ui-upgrade-card{display:grid;gap:8px;margin:0 0 12px;padding:16px;background:var(--accs);border:1.5px solid var(--acc);border-radius:12px;box-sizing:border-box}
body.v2 .ui-upgrade-card .ui-upgrade-name{margin:0;font-size:18px;font-weight:700;line-height:1.3;color:var(--acc-text)}
body.v2 .ui-upgrade-card .ui-upgrade-price{margin:0;font-size:20px;font-weight:700;line-height:1.3;color:var(--ink)}
body.v2 .ui-upgrade-card .ui-sub{margin:0}
body.v2 .ui-upgrade-card form{margin:4px 0 0}
body.v2 .ui-upgrade-card .ui-btn{width:100%;min-height:44px;justify-content:center}
body.v2 .ui-upgrade-strip{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 12px;margin:0 0 12px;padding:10px 12px;background:var(--accs);border-radius:8px;font-size:14px;font-weight:600;color:var(--acc-text)}
body.v2 .ui-addon-row{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 12px;margin:0 0 12px;padding:12px;background:#fff;border:1px solid var(--line);border-radius:12px;box-sizing:border-box}
body.v2 .ui-addon-text{display:grid;gap:2px;min-width:0;flex:1 1 200px;font-size:15px}
body.v2 .ui-addon-row .ui-btn,body.v2 .ui-upgrade-strip .ui-btn{min-height:44px}
@media (max-width:599px){body.v2 .ui-upgrade-strip .ui-btn,body.v2 .ui-addon-row .ui-btn{width:100%;justify-content:center}}
```
   Confirm the button class: `grep -n "def ui_button\|macro ui_button" -A6 App/app/templates/_ui.html | tail -30`; if the button root class is not `ui-btn`, use the real class in the rules above. Then `python3 scripts/design_lint.py 2>&1 | tail -30` must be OK; if it flags `1.5px` or a raw size, use `1px` for the border, nothing else may change. In a `.ui-form-actions` inside the Change card the 1006 rule right-aligns the single secondary buttons; that is intended.

5. **Cache bump.** `App/app/templates/base.html`: raise the `app2.css?v=` value by one step (same pattern as 1006); `grep -rn "app2.css?v=" App/app/templates | tail -30` and bump every template using the old value to the new one. If `App/tests/static_versions.json` has an entry for app2.css, update it the way 1006 did (`git diff App/tests/static_versions.json | tail -30` shows the pattern).

6. **Catalog and docs.** `docs/design/catalog.json`: after line 5 `    "ui-section-card",` insert `    "ui-upgrade-card",`, `    "ui-upgrade-name",`, `    "ui-upgrade-price",`, `    "ui-upgrade-strip",`, `    "ui-addon-row",`, `    "ui-addon-text",`. `docs/design/design-system.md`: in section 5b, before the line `Checklist for new pages:` add: `Upgrade blocks inside a card (billing): ONE highlighted card for the other plan (`ui-upgrade-card`: `--accs` tint, 1.5 px `--acc` border, plan name, real price, one full-width primary button, no pill unless the copy exists); a slim `ui-upgrade-strip` for the yearly saving; each add-on a bordered `ui-addon-row` (title, one line, secondary Add/Remove). Never more than one upgrade card per page.` Check: `python3 scripts/design_lint.py 2>&1 | tail -30` OK and `python3 -c "import json;json.load(open('docs/design/catalog.json'))"` prints nothing.

7. **Test.** Append to `App/tests/test_billing_self_service.py` (follow the fixtures and helpers already used in that file or in `test_billing_order.py` lines 205-225: `host`, `TestClient(app)`, `login_as`, `_set(owner, status="active", plan="standard", billing_interval="month")`; copy their imports if missing) one test `test_the_change_card_shows_the_real_upgrade_and_keeps_the_forms`: log in, set the account active standard monthly, `GET /predplatne?lang=en`, assert `"ui-upgrade-card" in page`, `"Switch to Max" in page`, `"ui-upgrade-strip" in page`, `"Pay yearly" in page`, `"ui-addon-row" in page`, `page.count('action="/predplatne/zmena"') == 3`; then set `plan="max"` and assert `"ui-upgrade-card" not in page`, `"Switch to Standard" in page`, `"ui-addon-row" not in page`. If a helper is absent, STOP rather than inventing fixtures.

8. **Run tests, from `App/`** (test-map row: billing):
```
.venv/bin/python -m pytest tests/test_billing_self_service.py tests/test_billing_order.py tests/test_0416_plan_page_browser.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
```
   Expected: pass, `0 skipped`, zero host findings. Existing tests post to `/predplatne/zmena` by field name only (test_billing_order.py line 212), so none needs changing; if one fails on button text, update only the asserted text and say so in the report. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30` clean.

9. **Screenshots.** Throwaway script `/tmp/shoot_1007.py` (outside the repo) following `App/tests/test_0416_plan_page_browser.py` (fixtures `calendar_workspace`, `calendar_origin`, `launch`, `open_page`, `settle_motion`; set `billing_account` to `status='active', plan='standard', billing_interval='month'`, `BILLING_ENABLED` true), or reuse the throwaway you used for 1006 in `/tmp`. Take `/tmp/shots/wolt/billing-upgrade-{390,768,1280}.png` of /predplatne. Open all three with Read and write what you see (upgrade card tinted with border, button full width at 390, strip, add-on row, nothing clipped or sideways-scrolling, Cancel card intact). Also read `/tmp/shots/layout-lint/` billing screenshots if present. If anything is cramped, fix CSS once and re-shoot.

10. **Copy out and commit locally (owner authorised full execution while asleep).** `mkdir -p /mnt/project-files/ux-shots/wolt && cp /tmp/shots/wolt/billing-upgrade-390.png /tmp/shots/wolt/billing-upgrade-1280.png /mnt/project-files/ux-shots/wolt/ && ls -l /mnt/project-files/ux-shots/wolt | tail -30`. Then `git add` ONLY the §3 files plus the still-uncommitted 1006 files (`git status --short | tail -30` to list them), `git commit` with a message `UX: billing upgrade card, yearly strip, add-on row (1007)` ending with the two attribution lines from the session reminder. Do NOT push, merge or open a PR.

11. **Report.** Write `docs/tasks/1007-report.md` (600 tokens at most): `Status: review`, files changed, last 5 lines of each step 8 command, per page "390: ...; 768: ...; 1280: ...", the two screenshot paths, deviations. Set this brief's `Status: review`, and commit the report in a second local commit.

## 5. Do not touch

`_ui.html`, `_ui_layout.html`, `billing.py`, `billing_order.py` (pricing and change logic), the order-form branch and invoices of billing_plan.html, `app.js`, `tests/layout_lint.js`, `scripts/design_lint.py`, other templates and CSS files. No JS, no `style=""`, no new dependency, no new outbound request, no invented price, feature, or "Recommended" pill. No push, merge or deploy.

## 6. Commands

As in step 8. Expected last lines: `N passed`, `0 skipped`, design_lint OK, context_lint clean.

## 7. Acceptance

- [ ] Standard: one tinted upgrade card (Max, real price for the host's apartment count and interval, existing Max sentence, full-width primary button on 390 px); monthly hosts see the "Pay yearly and save N %" strip (N from `billing.quote`); TTLock is a bordered row with Add/Remove.
- [ ] Max: no promo card, only a secondary "Switch to Standard"; no TTLock row.
- [ ] `grep -c 'action="/predplatne/zmena"'` in the rendered standard page is 3 (new test) and POST field names are unchanged.
- [ ] New classes are in `docs/design/catalog.json` and mentioned in design-system 5b.
- [ ] Layout lint green with 0 skipped, zero findings; 390/768/1280 screenshots read and described; two PNGs in `/mnt/project-files/ux-shots/wolt/`.
- [ ] Local commits exist; nothing pushed.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor excerpt is not found, or 1006's edits are missing;
- a test fails twice or a layout-lint finding remains after one fix;
- you reach 25 tool calls or about 50k tokens;
- a new dependency or a file outside §3 seems needed;
- §5 would be touched;
- you would need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

`docs/tasks/1007-report.md` as in step 11.
