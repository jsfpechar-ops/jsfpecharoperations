# 1006: Wolt-style section cards (settings pages): shared classes, Plan and billing, Property editor

Status: todo
Depends on: 1005 (same file app2.css; run after it, bump `app2.css?v=` once more) | Base commit: HEAD of claude/wolt-restyle | Branch: claude/wolt-restyle (current branch, do NOT create another)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give settings-style pages one calm look, copied from the Wolt company-settings page the owner showed: one narrow centred column (max 720 px); every section is ONE light card (white, 1 px thin border, 12 px radius, no shadow); title left with at most one small action right on the same row, help "?" right beside the title; fields as a quiet two-column label/value list; small grey strips for notes; no nested boxes. Add the shared classes and the checklist, then apply them to Plan and billing and (wrapper/class changes only) to the Property editor sections.

**Executor flow differs from the usual:** work on the current branch, make the changes, do NOT run `git commit` or `git push`. After the UX gate, take screenshots, copy them, write the report and STOP. The owner approves the screenshots before anything is committed.

## 2. Context

Rules: light mode only; tokens only (no raw hex, no bare px other than 0/1 in app2.css padding/margin/gap/radius per `scripts/design_lint.py` S2: use the numbers already used elsewhere only through `var(--...)` where a token exists, otherwise the nearest existing rule's value as in line 1643 `padding:16px`, which the lint accepts because those props are checked per `PX_PROPS`: if `python3 scripts/design_lint.py` reports S2 for a value, replace the px with a token from `App/app/static/tokens.css`); no `<style>` or `style=""` in templates; copy untouched (no new i18n keys unless §4 step 6 says so); help "?" stays the `ui_tip` macro; auth forms and the property form keep working without JavaScript; AGENTS rules 6, 7, 10.

Existing building blocks (verified):
- `App/app/templates/_ui_layout.html` line 28: `{% macro ui_section(title, actions='', id='', tip='') -%}` renders `<section class="ui-section">` + `<div class="ui-section-h"><h2>..</h2>..</div>`. Line 36: `ui_facts(pairs)` renders `<dl class="ui-facts"><div><dt>..</dt><dd>..</dd></div></dl>`. These macros are NOT edited.
- `App/app/static/app2.css` line 1798: `body.v2 .ui-section-h{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}`; line 1618: `body.v2 .ui-section-h>h2:has(>.help-tip){display:flex;align-items:last baseline}`; line 1638: `body.v2 .settings-lane{max-width:720px}`; line 2150: `body.v2 .settings-lane > .ui-section{margin:0 0 24px}`. `.ui-facts` is styled only under `.guide-page` (lines 1546-1550, 1570), so on `/predplatne` it is unstyled: that is the stack the owner screenshot shows.
- `App/app/templates/billing_plan.html` (133 lines): `<div class="settings-lane">` at line 17; the active-plan branch starts at the line `{% call ui_section(t('billing.plan.current_title')) %}` (inside `{% else %}` after the order form) and uses `ui_facts([...6 pairs...])`; the "Change" section is `{% call ui_section(t('billing.change.title')) %}` with one `<form>` per option, each `<div class="ui-form-actions">{{ ui_button(label, 'secondary', type='submit') }}</div>`; the cancel section is `{% call ui_section(t('billing.cancel.title')) %}` with `ui_tip('tip-billing-cancel', ...)` and a `data-confirm` form; invoices are `{% call ui_section(t('billing.invoices.title')) %}{{ ui_table_begin(...) }}`. Tests: `test_0416_plan_page_browser.py` (asserts the text "Přejít na Max" visible and no sideways scroll), `test_billing_*.py`.
- `App/app/templates/_property_editor.html`: six `<details class="prop-sec" id="sec-...">` at lines 139 (basics), 210 (messages), 288 (police), 366 (fee), 417 (calendars), 425 (lock), inside `<form ... class="property-settings-form">` which is `display:contents` (`app2.css` line 378). Generic card rule `app2.css` line 359: `body.v2 details{background:var(--s);border:1px solid var(--line);border-radius:12px;margin-bottom:10px}`. Phone rules at lines 1008-1018 make `details.prop-sec` borderless.
- `scripts/design_lint.py`: `_findings_template` has T1-T5; `enforced_templates` in `docs/design/catalog.json` line 565+. Neither `billing_plan.html` nor `_property_editor.html` is enforced, so new classes there need no `legacy` entry; the new `ui-*` classes still go into `catalog.json` `classes`.

Anchors (each must be found verbatim, else STOP, §8):
- `App/app/static/app2.css`, last line of the file starts with: `@media (max-width:599px){body.v2 .help-tip .help-tip-body{` (append after the newest end of file; if 1005 added lines after it, append at the very end of file instead).
- `App/app/templates/base.html` line 22: contains `app2.css?v=`.
- `App/app/templates/billing_plan.html` line 17: `<div class="settings-lane">`.
- `docs/design/design-system.md` line 69: `## 6. How it is enforced`.
- `docs/design/catalog.json` line 4: `    "ui-details-box",`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/app2.css | edit | append the 1006 block (§4 step 1) |
| App/app/templates/base.html | edit | bump `app2.css?v=` |
| docs/design/catalog.json | edit | add 9 class names |
| docs/design/design-system.md | edit | new section before `## 6.` |
| App/app/templates/billing_plan.html | edit | classes and structure of the active-plan branch and invoices |
| App/app/templates/_property_editor.html | edit | add class to the six `prop-sec` details (revert if §4 step 7 says so) |
| docs/tasks/1006-report.md | create | report, `Status: awaiting-owner-screenshots` |

No other file may change. Temporary screenshot script: create it under `/tmp`, never in the repo, or delete it before the report.

## 4. Steps

1. **CSS.** Append exactly this to the end of `App/app/static/app2.css`:
```
/* 1006: Wolt-style section cards. One card per section, quiet label/value rows, no nested boxes. */
body.v2 .ui-page-narrow{max-width:720px;margin-left:auto;margin-right:auto;width:100%;box-sizing:border-box}
body.v2 .ui-section-card,body.v2 .ui-page-narrow > .ui-section{display:block;min-width:0;margin:0 0 16px;padding:16px;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:none;box-sizing:border-box}
body.v2 .ui-section-head,body.v2 .ui-section-card > .ui-section-h,body.v2 .ui-page-narrow > .ui-section > .ui-section-h{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 12px;margin:0 0 12px}
body.v2 .ui-section-head > h2,body.v2 .ui-section-card > .ui-section-h > h2,body.v2 .ui-page-narrow > .ui-section > .ui-section-h > h2{margin:0;font-size:16px;font-weight:700;line-height:1.3;min-width:0}
body.v2 .ui-kv,body.v2 .ui-page-narrow dl.ui-facts{display:grid;gap:0;margin:0}
body.v2 .ui-kv-row,body.v2 .ui-page-narrow dl.ui-facts > div{display:grid;grid-template-columns:minmax(0,40%) minmax(0,1fr);gap:4px 16px;align-items:baseline;padding:12px 0;border-top:1px solid var(--line)}
body.v2 .ui-kv-row:first-child,body.v2 .ui-page-narrow dl.ui-facts > div:first-child{border-top:0;padding-top:0}
body.v2 .ui-kv-row:last-child,body.v2 .ui-page-narrow dl.ui-facts > div:last-child{padding-bottom:0}
body.v2 .ui-kv-row > :first-child,body.v2 .ui-page-narrow dl.ui-facts dt{margin:0;font-size:14px;color:var(--ink3)}
body.v2 .ui-kv-row > :last-child,body.v2 .ui-page-narrow dl.ui-facts dd{margin:0;min-width:0;font-size:15px;line-height:1.5;color:var(--ink);overflow-wrap:anywhere}
body.v2 .ui-note-strip{margin:12px 0 0;padding:10px 12px;background:var(--bg);border:0;border-radius:8px;font-size:14px;line-height:1.45;color:var(--ink3)}
body.v2 .ui-section-card .ui-form-actions,body.v2 .ui-page-narrow > .ui-section .ui-form-actions{justify-content:flex-end;margin-top:12px}
body.v2 details.ui-section-card{padding:0;overflow:visible}
body.v2 details.ui-section-card > summary{padding:14px 16px;min-height:44px;box-sizing:border-box}
@media (max-width:599px){body.v2 .ui-kv-row,body.v2 .ui-page-narrow dl.ui-facts > div{grid-template-columns:minmax(0,1fr)}}
```
   If `--bg` is not defined in `App/app/static/tokens.css` (`grep -n "^\s*--bg:" App/app/static/tokens.css | tail -30`), use the page-background token that file does define (grep `--s`, `--line`, `--bg`, `--canvas`) for `.ui-note-strip`. Check: `python3 scripts/design_lint.py 2>&1 | tail -30` prints OK or only findings that are not about these lines; if it reports S1/S2 on the new block, swap the value for a token (raw `#fff` is the same value used at line 2664, if S1 complains use `var(--s)`).
   Note: `ui-kv`, `ui-kv-row` are the reusable form of the same look for markup that is not a `dl` (a `div.ui-kv` containing `div.ui-kv-row` with two children: label first, value last).
2. **Cache bump.** `base.html` line 22: raise the `v=` value of `app2.css` by one (e.g. `20261107-1207` becomes `20261108-1001`; if 1005 already bumped it, bump again). Then `grep -rn "app2.css?v=" App/app/templates | tail -30` and bump any other template with the same old value to the same new value.
3. **Catalog.** `docs/design/catalog.json`: after line 4 `    "ui-details-box",` insert, one per line with the same indentation and a trailing comma: `"ui-section-card"`, `"ui-section-head"`, `"ui-kv"`, `"ui-kv-row"`, `"ui-note-strip"`, `"ui-page-narrow"`. Run `python3 scripts/design_lint.py 2>&1 | tail -30` until it prints OK (also run `python3 -c "import json;json.load(open('docs/design/catalog.json'))"`).
4. **Design system doc.** In `docs/design/design-system.md` insert before the line `## 6. How it is enforced` this section (keep wording):
```
## 5b. Section cards (settings-style pages)

Copied from the Wolt company-settings page. One narrow column (`ui-page-narrow`, max 720 px). Each section is ONE card (`ui-section-card`: white, 1 px `--line`, radius 12, no shadow, padding 16). The head (`ui-section-head`, or the `ui_section` macro's `ui-section-h`) holds the title on the left with its help "?" right after it, and at most one small action on the right. Fields are a quiet two-column list (`ui-kv` / `ui-kv-row`, or `ui_facts` inside `ui-page-narrow`): muted label 40 %, value right, 12 px row padding, 1 px divider between rows, stacked below 600 px. Notes are a small grey `ui-note-strip`. No card in a card, no heavy outlines, no chevron collapse for a simple section.

Checklist for new pages:
- [ ] Help "?" sits beside the title (never on its own, never at the row end).
- [ ] The whole row is clickable; no separate arrow.
- [ ] No action appears only on hover.
- [ ] Required fields carry a red star, with a legend on the page.
- [ ] No truncated pill or label without a tooltip (rule 8 still wins: labels wrap).
- [ ] One date format: dd.mm.yyyy.
- [ ] Uses `ui-section-card`, `ui-kv` and `ui-page-narrow`.
- [ ] No nested boxes.
```
5. **Plan and billing, template.** In `billing_plan.html`:
   a. Line 17: change `<div class="settings-lane">` to `<div class="settings-lane ui-page-narrow">`. (Every `ui_section` direct child becomes a card through the CSS; the order-form branch becomes cards too, which is intended. The `<form>` wrapper in the order branch holds sections one level down, so add `ui-page-narrow`-independent card look there by changing `<form method="post" action="/predplatne" data-billing-order>` to keep as is and verify in the screenshot of the order state in step 8; if its sections are NOT cards, change CSS selector in step 1 by adding `body.v2 .ui-page-narrow > form > .ui-section` next to `.ui-page-narrow > .ui-section` in the three rules that name it, and do the same for `> .ui-section > .ui-section-h`.)
   b. Active-plan section: make the status a small pill instead of plain text. In the `ui_facts([...])` call replace the last pair `(t('billing.plan.fact.status'), t('billing.plan.state.' ~ acc.status)),` with `(t('billing.plan.fact.status'), ui_badge('done' if acc.status == 'active' else 'action' if acc.status in ('overdue', 'canceling') else 'neutral', t('billing.plan.state.' ~ acc.status))),`. `ui_badge` comes from `_ui.html`: if the template does not already import it, add `{% from "_ui.html" import ui_badge with context %}` under the existing `ui_tip` import (line 6). `ui_facts` marks the value `| safe`, and the badge macro output is safe.
   c. Change and Cancel: put them where the owner can see one action row aligned right. For the "Change" section keep the per-option forms (functionality unchanged) but wrap nothing new; the CSS in step 1 already right-aligns `.ui-form-actions` inside cards. For the "Cancel" section nothing else changes. The help `ui_tip` calls inside these sections stay where they are, and the title-beside-help rule is met by passing `tip=`: change `{% call ui_section(t('billing.cancel.title')) %}` to `{% call ui_section(t('billing.cancel.title'), tip=ui_tip('tip-billing-cancel', t('billing.cancel.body', date=period_end))) %}` and delete the now duplicate line `{{ ui_tip('tip-billing-cancel', t('billing.cancel.body', date=period_end)) }}` inside it. Do the same for `billing.change.title` with `tip=ui_tip('tip-billing-change', t('billing.change.apartments_note'))` (delete the line `{{ ui_tip('tip-billing-change', t('billing.change.apartments_note')) }}`) and for `billing.invoices.title` with `tip=ui_tip('tip-billing-invoices', t('billing.invoices.pay_hint'))` (delete the trailing `{{ ui_tip('tip-billing-invoices', t('billing.invoices.pay_hint')) }}`). The macro splits the title on its last space and nowrap-joins the last word with the tip, so single-word titles are fine. Remove any other stray `ui_tip` call that is not directly in a title.
   d. Invoices: the table is already inside `ui_section`, so it sits in a card; make sure there is no `ui-card` wrapper of its own. Nothing to add.
   Check: `grep -n "ui_tip\|ui-page-narrow\|ui_badge" App/app/templates/billing_plan.html | tail -30`; then from `App/`: `.venv/bin/python -m pytest tests/test_0416_plan_page_browser.py tests/test_billing_*.py -q --tb=short -x 2>&1 | tail -30` green.
6. **Copy.** No new i18n keys. If a pill label would be wrong, STOP rather than adding keys.
7. **Property editor, class change only.** In `_property_editor.html` on the six lines starting `<details class="prop-sec" id="sec-basics"`, `sec-messages`, `sec-police`, `sec-fee`, `sec-calendars`, `sec-lock`, change `class="prop-sec"` to `class="prop-sec ui-section-card"` (nothing else on those lines; do not touch `open` logic, summaries, inputs, forms). Check: `grep -c 'class="prop-sec ui-section-card"' App/app/templates/_property_editor.html` prints 6. Existing phone rule (`details.prop-sec` borderless, line 1018) is more specific only inside its media query; if the 390 px screenshot shows a double border or changed spacing there, add to the CSS block `@media (max-width:1023px){body.v2 details.prop-sec.ui-section-card{border:0;padding:0;margin:0;background:transparent}}` and re-check. If after one such fix a layout-lint finding remains, revert this step entirely (`git checkout App/app/templates/_property_editor.html`), keep steps 1-5, and say so in the report. The preview aside and the grid layout stay untouched; the editor is not forced into 720 px.
8. **Tests, from `App/`** (test-map rows: billing, onboarding/properties, host templates/CSS):
```
.venv/bin/python -m pytest tests/test_0416_plan_page_browser.py tests/test_billing_*.py tests/test_property_*.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
```
   Expected: pass, `0 skipped` in the last line, zero host findings. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` OK and `python3 scripts/context_lint.py 2>&1 | tail -30` clean.
9. **Screenshots (real, not from the lint folder only).** Write a throwaway script `/tmp/shoot_1006.py` (outside the repo; or a temporary `App/tests/test_zz_shoot_1006.py` that you delete afterwards) following `App/tests/test_0416_plan_page_browser.py` (fixtures `calendar_workspace`, `calendar_origin`, helpers `launch`, `open_page`, `settle_motion`; set the billing account to `status='active', plan='standard', billing_interval='month', apartments_billed=3, period_end='2099-01-31'` as in that test; keep `locale="en"`). Take full-page shots at 390 and 1280 of `/predplatne` (active plan state with at least one invoice row if the fixture allows; otherwise note it) and of `/apartments/<configured apartment id>?view=settings` with the `#sec-basics` details open (use the `configured_apartment` fixture as `test_layout_lint_browser.py` does at line 59). Save to `/tmp/shots/wolt/billing-390.png`, `billing-1280.png`, `property-390.png`, `property-1280.png`. Open each with Read and inspect: one narrow column, one white card per section, title left with its "?" right beside it, action right on the head or action row, label/value two columns (stacked at 390), status as a pill, invoices table inside a card, no stray "?", no nested boxes, no sideways scroll. Fix with CSS in the §4 block only, then re-run step 8. Also open `/tmp/shots/layout-lint/` shots for the billing page if present (`ls /tmp/shots/layout-lint | grep -i -E "plan|billing|property" | tail -30`) at 768 and write one line for 768 as well.
10. **Copy for the owner.** `mkdir -p /mnt/project-files/ux-shots/wolt && cp /tmp/shots/wolt/*.png /mnt/project-files/ux-shots/wolt/ && ls -l /mnt/project-files/ux-shots/wolt | tail -30`.
11. **Report and STOP.** Write `docs/tasks/1006-report.md` (600 tokens at most): first line `Status: awaiting-owner-screenshots (uncommitted)`; `git status --short | tail -30`; the last 5 lines of each command in step 8; per page "390: ...; 768: ...; 1280: ...", Plan and billing and Property editor; the four screenshot paths; whether step 7 was kept or reverted; the T-new decision (§6). Do NOT `git add`, `git commit`, `git push` or open a PR. The owner approves the screenshots first.

## 5. Do not touch

`_ui_layout.html`, `_ui.html` macros, `host_i18n.py`, `app.js`, `tests/layout_lint.js`, `scripts/design_lint.py` (see §6), any template other than the two named, other CSS files, routes, billing logic. No JS, no `style=""`, no new dependency, no new outbound request. Hard rules: light mode only; no card in a card; one primary per group.

## 6. Commands (out of scope, and the T-new lint rule)

Out of scope: the Stay fees month filter and header, the calendar pages, and restyling every other page. They get their own briefs after the owner has approved these screenshots.

Design-lint rule "T-new" (fail on `<details class="` boxes without `ui-details-box` or `ui-section-card` in enforced templates): **SKIPPED on purpose.** The orchestrator checked: about 45 existing `<details class="...">` in enforced templates would fail it (guest_form_admin, dashboard, reservation_detail, submissions, invoice_detail, settings, guide x24, cleaning, setup_wizard, _smart_locks_panel, _havel_card and more), so it breaks the "no existing violations" condition. Do not edit `design_lint.py`; the report repeats this sentence.

## 7. Acceptance

- [ ] `design_lint.py` OK; `context_lint.py` clean; every §4 step 8 command green, `0 skipped`, zero host findings.
- [ ] `grep -c "ui-section-card\|ui-kv\|ui-note-strip\|ui-page-narrow\|ui-section-head" docs/design/catalog.json` prints 6 or more matching lines (6 new names present).
- [ ] The Plan and billing screenshots show: one card per section, status pill, Change/Cancel aligned right in their cards, help "?" beside titles, invoices in a card, nothing stranded.
- [ ] Property screenshots show the six sections unchanged in behaviour (still collapsible), no double borders, no layout shift at 390.
- [ ] Four PNGs exist in `/mnt/project-files/ux-shots/wolt/`.
- [ ] `git log -1` is unchanged (no commit made); `git status --short` shows only the §3 files.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an anchor excerpt is not found;
- a test fails twice or a layout-lint finding remains after one fix;
- you reach 25 tool calls or about 50k tokens;
- a new dependency, i18n key or a file outside §3 seems needed;
- §5 would be touched;
- you would need push, merge, secrets, SSH or deploy (hand it to the owner with the exact command).

## 9. Report

`docs/tasks/1006-report.md` as in §4 step 11. The owner approves the screenshots; only then does anyone commit.
