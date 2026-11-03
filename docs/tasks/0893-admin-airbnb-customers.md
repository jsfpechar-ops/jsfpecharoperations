# 0893: Airbnb look on admin console, customers list and customer detail

Status: todo
Depends on: none | Base commit: 41e86bd3 | Branch: task/0893-admin-airbnb-customers
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The three admin pages Josef uses most (`/admin`, `/admin/customers`, `/admin/customers/{id}`) get the same look as the host app on phone, tablet and desktop: pill tabs, value cards for counts, a round back button, no fine print (help under an 18 px "?"), 12 px between neighbours, and fewer taps. Visual and copy placement only; the structure and every action stay.

## 2. Context

- References: `/mnt/project-files/settings-area/airbnb-ref/` (IMG_2197 pills, IMG_2198 value cards). Open at most one.
- OUT of scope (owner, admin portal review 2026-11-01): merging Customers and Users, the four-tab restructure, the Today tab, dropping the duplicate Manage/Preview button. Do not move, merge or remove any section, form or button.
- The admin templates extend `host_page.html` and are not v2 yet. Set `{% set v2 = true %}` on each, as 0830 did for other non-v2 pages, so the `body.v2` partial CSS applies.
- New CSS goes in a NEW file `App/app/static/admin2.css`, loaded only by the admin templates through `base.html`'s existing `{% block head_extra %}`. This brief owns that file; 0894 links to it read-only. Do not edit `app2.css` or `base.html`.
- Shared pieces you reuse (read-only): `partials/settings_value_card.html` (needs `label`, `value`, `href`), `tip_label(text, id, help, tag)` from `_components.html` (keeps the "?" on the last word), `ui_tabs` markup `<nav class="ui-tabs" data-sub-tabs ...><a class="ui-tab" ... aria-current="page">` and `ui_stats` markup `<nav class="ui-stats"><a class="ui-stat"><strong class="ui-num">..</strong><span>..</span></a></nav>` from `_ui_layout.html`. `test_admin_section_tabs.py` requires `<nav class="ui-tabs"`: keep that markup and restyle it as pills in CSS.
- Fine print rule: an explanatory line (`.ui-sub` paragraph whose key ends in `.help`, `.help2`, `.lede`, `_help` or `.meta`) moves under a "?" on its section or page title. Status content (`.none`, `as_of`, amounts, e-mails, dates, `legacy_note`, `missing_email_banner`) stays visible at 16 px.

Anchors (exact, on 41e86bd3):

`App/app/templates/admin_home.html`
```
{% block meta %}{{ t('home.admin.meta', date=today) }}{% endblock %}
```
`App/app/templates/admin_customers.html`
```
{% block meta %}{{ t('customers.meta') }}{% endblock %}
```
```
    {{ ui_field('customer-search', t('customers.search'), name='q', value=q, type='search', attrs='maxlength="120"') }}
```
```
  <h2>{{ t('users.create.title') }}</h2>
  <p class="ui-sub">{{ t('users.create.lede') }}</p>
```
`App/app/templates/admin_customer.html`
```
{% block meta %}{{ t('customers.state.' ~ customer.customer_state) }}{% endblock %}
```
```
{% call ui_section(t('customers.account')) %}
```
```
{% call ui_section(t('customers.assign.title'), id='assign-plan') %}
<p class="ui-sub">{{ t('customers.assign.help') }}</p>
```
```
<p class="ui-sub">{{ t('customers.assign.help2') }}</p>
```
```
  <input class="ui-input" type="number" id="extend-days" name="days" min="1" max="365" required>
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/admin2.css` | create | admin Airbnb look |
| `App/app/templates/admin_home.html` | edit | v2, CSS link, title "?" |
| `App/app/templates/admin_customers.html` | edit | v2, CSS link, title "?", create-host "?", search key hint |
| `App/app/templates/admin_customer.html` | edit | v2, CSS link, state value card, assign "?", labels, extend prefill |
| `App/tests/test_0893_admin_airbnb_browser.py` | create | geometry test, 6 widths |
| `App/tests/static_versions.json` | regenerate | `--write`, never by hand |

Existing tests in §6 may get an assertion updated to the new markup; never delete a behaviour test. No other file may change.

## 4. Steps

1. Create `App/app/static/admin2.css` with exactly this:
```css
/* 0893: admin pages in the Airbnb pattern. Loaded only by admin templates (head_extra). Light mode only. */
body.v2 .ui-ph h1{font-size:32px;line-height:1.2;font-weight:700;color:#222}
body.v2 .ui-ph-back{width:40px;height:40px;border-radius:50%;background:#f2f2f2;color:#222;display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px;text-decoration:none}
body.v2 .ui-ph-back span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
body.v2 .ui-tabs{display:flex;gap:12px;overflow-x:auto;border:0;padding:4px 0;margin:0 0 24px}
body.v2 .ui-tabs .ui-tab{display:inline-flex;align-items:center;min-height:44px;padding:0 20px;border-radius:999px;border:0;background:#f2f2f2;color:#222;font-weight:600;white-space:nowrap;text-decoration:none}
body.v2 .ui-tabs .ui-tab::after{display:none}
body.v2 .ui-tabs .ui-tab[aria-current="page"]{background:#222;color:#fff}
body.v2 .ui-stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin:0 0 24px}
body.v2 .ui-stats .ui-stat{display:flex;flex-direction:column;gap:8px;padding:20px;border:1px solid #e5e5e5;border-radius:12px;background:#fff;color:#222;text-decoration:none}
body.v2 .ui-stats .ui-num{font-size:28px;font-weight:700}
body.v2 .ui-stats .ui-stat span{font-size:16px}
body.v2 .ui-body .ui-section+.ui-section{margin-top:32px}
body.v2 .ui-body .ui-section-h h2,body.v2 .ui-body .ui-section>h2{font-size:22px;font-weight:700;color:#222}
body.v2 .ui-body .ui-sub,body.v2 .ui-body .admin-label{font-size:16px;line-height:1.5;color:#6a6a6a}
body.v2 .ui-body .admin-label{color:#222}
body.v2 .ui-body .ui-form-actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
body.v2 .ui-body table{border:1px solid #e5e5e5;border-radius:12px;border-collapse:separate;border-spacing:0;overflow:hidden}
body.v2 .ui-body form+form{margin-top:12px}
body.v2 .settings-value-card{border:1px solid #e5e5e5;border-radius:12px;padding:20px;margin:0 0 12px}
```
   Command: `ls -l App/app/static/admin2.css 2>&1 | tail -3`.
2. In each of the three templates, directly after the `{% extends "host_page.html" %}` line, add:
```
{% set v2 = true %}
{% block head_extra %}<link rel="stylesheet" href="/static/admin2.css?v=20261102-0893">{% endblock %}
```
   and after the template's other `{% from ... %}` lines add `{% from "_components.html" import tip_label with context %}`. Command: `grep -c "admin2.css" App/app/templates/admin_home.html App/app/templates/admin_customers.html App/app/templates/admin_customer.html | tail -3`. Expected: 1 each.
3. `admin_home.html`: replace the meta anchor with `{% block page_title %}{{ tip_label(self.title(), 'admin-home-help', t('home.admin.meta', date=today), tag='span') }}{% endblock %}`. Command: `grep -c "block meta" App/app/templates/admin_home.html | tail -3`, expected `0`.
4. `admin_customers.html`: replace the meta anchor with `{% block page_title %}{{ tip_label(self.title(), 'admin-customers-help', t('customers.meta'), tag='span') }}{% endblock %}`. In the search field anchor change `attrs='maxlength="120"'` to `attrs='maxlength="120" enterkeyhint="search"'`. Replace the two-line create-host anchor with `  <h2>{{ tip_label(t('users.create.title'), 'create-host-help', t('users.create.lede'), tag='span') }}</h2>`. Command: `grep -c "users.create.lede\|enterkeyhint" App/app/templates/admin_customers.html | tail -3`, expected `2`.
5. `admin_customer.html`: delete the meta anchor line. After the line `{% call ui_section(t('customers.account')) %}` add:
```
{% with label=t('customers.state'), value=t('customers.state.' ~ customer.customer_state), href='' %}{% include "partials/settings_value_card.html" %}{% endwith %}
```
   Command: `grep -c "settings_value_card" App/app/templates/admin_customer.html | tail -3`, expected `1`.
6. `admin_customer.html`: replace the two-line assign anchor with `{% call ui_section(tip_label(t('customers.assign.title'), 'assign-help', t('customers.assign.help') ~ ' ' ~ t('customers.assign.help2'), tag='span'), id='assign-plan') %}` and delete the line `<p class="ui-sub">{{ t('customers.assign.help2') }}</p>`. Command: `grep -c "assign.help" App/app/templates/admin_customer.html | tail -3`, expected `1`.
7. `admin_customer.html`: replace every `<label class="ui-sub"` with `<label class="admin-label"` (Edit with replace_all). In the extend-days anchor add `value="14" inputmode="numeric"` before `required` (owner question Q2 in 0895; 14 is the default until he answers). Command: `grep -c "label class=\"ui-sub\"" App/app/templates/admin_customer.html | tail -3`, expected `0`.
8. Write `App/tests/test_0893_admin_airbnb_browser.py`. Copy the `host` and `base` fixtures and the cookie hand-off from `App/tests/test_0786_settings_geometry_browser.py` (lines 1 to 30, 143 to 176, 181 to 184). In `host`, after `create_account`, run `db.execute("UPDATE user_account SET role = 'admin' WHERE id = ?", (owner_id,))` before `login_as`, and create a second plain host account (the customer) whose id you return as `customer`. Export two helpers at module level, `fine_print_and_gap_findings(page)` and `shoot(page, name, width)`, because 0894 imports them. Pages: `admin_home` `/admin`, `admin_customers` `/admin/customers`, `admin_customer` `/admin/customers/{customer}`; widths 320, 390, 768, 1024, 1280, 1440; `?lang=en`. Checks per page and width:
   - `body.v2`; exactly one visible `h1`, font-size >= 28 px; no horizontal overflow;
   - `nav.ui-tabs` present; each `.ui-tab` >= 44 px tall, neighbours >= 12 px apart, exactly one `aria-current="page"`;
   - `.ui-stat` and `.settings-value-card`: 1 px border, radius >= 12, text >= 16 px from the edge;
   - `admin_customer`: `.ui-ph-back` visible, 40 +/- 1 px, above or left of the h1;
   - each `.help-tip-btn` in a title sits on the title's last line;
   - `fine_print_and_gap_findings`: no visible text under 14 px in `.ui-body`; no visible `p`, `small` or `.ui-sub` text over 60 characters outside `.help-tip-body`; among visible `h2, .ui-btn, .ui-input, label, .ui-sub, .ui-stat, .settings-value-card, .ui-tab` in `.ui-page` that neither overlap nor contain each other, every vertical or horizontal gap is >= 12 px (table cells excluded).
   `shoot`: with `UBYHOST_SHOTS_0893=1`, save `docs/tasks/screenshots-0893/<page>-<width>.png` at 390 and 1280.
   Run §6 command 1; fix only `admin2.css` until green, 0 skipped.
9. From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
10. Run §6 command 2. If a test fails only because the page is now v2 (shell markup, alert stack), update the assertion if it checks looks; if it checks an action or a link that disappeared, STOP.
11. §6 command 3 for the screenshots; look at each 390 px image once.

## 5. Do not touch

`admin_users.html` and every Users route (merge is out of scope), `admin_billing.html`, `admin_operations.html` (0894), `host_page.html`, `base.html`, `_ui*.html`, `_components.html`, `partials/*`, `app.css`, `app2.css`, `app.js`, any Python or i18n file. AGENTS.md rules 2, 5, 6, 7, 9.

## 6. Commands

From `App/`:
1. `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0893_admin_airbnb_browser.py -q -rs --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed|skipped" | cut -c1-240 | tail -20`. Expected: passed, 0 skipped.
2. `.venv/bin/python -m pytest tests/test_admin_customers.py tests/test_admin_section_tabs.py tests/test_admin_route_split.py tests/test_admin_helpers.py tests/test_design_admin.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs --tb=line -p no:cacheprovider 2>&1 | tail -10`. Expected: passed, 0 skipped.
3. `UBYHOST_SHOTS_0893=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0893_admin_airbnb_browser.py -q -k "390 or 1280" -p no:cacheprovider 2>&1 | tail -5`.
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Command 1: passed at all six widths, 0 skipped.
- [ ] Command 2 passed, 0 skipped.
- [ ] Every form, button and link that existed before still renders (compare `grep -c "<form\|ui_button" ` before and after per template in the report).
- [ ] One 390 px screenshot per page (and 1280) in `docs/tasks/screenshots-0893/`.
- [ ] Report lists taps to extend a trial and to find a customer, before and after.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in §2 is not found verbatim;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a section, form or button would have to move, merge or disappear;
- a file outside §3 needs a change, or a Python change seems needed;
- a step is unclear.

## 9. Report

Write `docs/tasks/0893-report.md` (600 tokens at most) and set `Status: review`. The report has: files changed (`git diff --stat`); each §6 command with its last 5 lines; §7 ticked; Deviations; Questions; owner steps left.

## Risk list (for the reviewer)

`admin_customer.html` (operator actions, consent withdraw, deletion forms), `admin2.css` (also used by 0894).

## Owner steps

1. Open the PR and check the 390 px screenshots.
2. On staging, open `/admin/customers` on your phone, open one customer, extend a test trial.
