# 1013: Wolt-style restyle only from 768 px; phones get the old settings look back

Status: review
Depends on: PR 807 merged (commit d1afb5c2 is in origin/main) | Base: `origin/main` | Branch: `claude/wolt-desktop-only` | No PR (push the branch only; the orchestrator opens it)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner decision (Josef, 2026-11-08): the Wolt-style restyle from PR 807 (briefs 1012 `ux-wolt-style-cards`, formerly 1006; 1007 billing upgrade cards; 1008 property editor) applies only at `min-width: 768px` (tablet and laptop). Phones (below 768 px) get the old look of the Plan and billing page and the property editor back.

Old look = the files at commit `6bf92920` (before merge `d1afb5c2`). The 807 change in App/app was exactly five files: `static/app2.css` (+52 lines), `templates/billing_plan.html`, `routes/billing.py` (+14), `host_i18n.py` (+16), `templates/base.html` (cache key). The property editor change was CSS only (no `_property_editor.html` edit).

## 2. Context (approach decided by the orchestrator; do not re-audit)

CSS only. Wrap every Wolt rule in `@media (min-width: 768px)` so below 768 px the old base rules apply again. Templates, routes and i18n are NOT reverted: the markup carries new functional content (real upgrade price, yearly saving, TTLock row) and `tests/test_billing_order.py` lines ~240-250 pin the markup classes (`ui-upgrade-card`, `ui-upgrade-strip`, `ui-addon-row`).

What the markup changes look like on a phone once the CSS is wrapped:

| Markup change from 807 | On phones after this brief |
|---|---|
| Upgrade card (`.ui-upgrade-card`: "Max", real price, primary button) | Stays visible (real price is function). Plain stack, no tinted box (small phone-only rule, step 2). |
| Yearly strip (`.ui-upgrade-strip`: saving text + button) | Stays visible, plain row, full-width button. |
| TTLock row (`.ui-addon-row`: title, price line, Add/Remove) | Stays visible, plain row, full-width button. |
| Status badge in the facts list, tips moved into section headings, invoices as `section.ui-section.ui-section-card` | Stay (markup; `.ui-section` base rules give the old card look). |
| Archive moved last, Save bar `order:100` in the property editor | Both are CSS `order`, so they revert with the wrap: DOM order returns on phones. |
| `.ui-page-narrow` wrapper now also contains the back header | Stays; its 720 px max-width is inside the wrap, so phones are full width as before. |

Decision flagged for the owner (state it in the report): hiding the upgrade card, strip and TTLock row below 768 px was rejected because phone hosts would lose the real upgrade price and the one-tap yearly switch. If the owner wants the exact old plain button list on phones, that is a separate brief (hide with `display:none` plus restore the old option loop in the template).

## 3. Files

| Path | Action |
|---|---|
| App/app/static/app2.css | edit (steps 1-2) |
| App/app/templates/base.html | edit (step 3, cache key) |
| App/tests/static_versions.json | edit (step 3, via the script) |
| docs/tasks/1013-report.md | create (step 6) |
| docs/tasks/1013-ux-wolt-desktop-only.md | Status line only |

Do not touch `billing_plan.html`, `routes/billing.py`, `host_i18n.py`, `_property_editor.html`, or any test.

## 4. Steps

Anchors: `grep -nF "<text>" <file>`. Not found: STOP and report. Every grep ends with `| tail -30`. Commit after each step with `1013 step k`.

0. **Branch.** From the repo root:
   `git fetch origin main 2>&1 | tail -3 && git checkout -B claude/wolt-desktop-only origin/main 2>&1 | tail -3 && git log --oneline -1 | cat`
   Expected: on `claude/wolt-desktop-only`. Then
   `grep -nF "/* 1006: Wolt-style section cards" App/app/static/app2.css; grep -nF "/* 1007: billing upgrade card" App/app/static/app2.css; grep -nF "/* 1008: Wolt-style property editor" App/app/static/app2.css; wc -l App/app/static/app2.css | tail -3`
   Expected: 2985, 3004, 3016, and 3036 lines (the Wolt block is lines 2985-3036 at the end of the file). If the numbers differ, trust the greps, but the block must still run to the last line of the file; if other rules follow the `.prop-strip` line, STOP.

1. **Wrap the Wolt block in one media query.** In `App/app/static/app2.css`:
   a. Directly before the line `/* 1006: Wolt-style section cards.` insert two lines:
   ```
   /* 1013: the whole Wolt-style restyle (1006, 1007, 1008) applies from 768 px up; phones keep the old settings look. */
   @media (min-width:768px){
   ```
   b. Append `}` as the new last line of the file (after the `body.v2 .prop-strip{...}` line).
   c. Delete the now-dead rule (phones can no longer match it inside the wrap): the line starting `@media (max-width:599px){body.v2 .ui-kv-row,body.v2 .ui-page-narrow dl.ui-facts > div{grid-template-columns:minmax(0,1fr)}}`.
   d. Move the phone button rule out of the wrap (it is useful on phones): cut the line starting `@media (max-width:599px){body.v2 .ui-upgrade-strip .ui-btn,body.v2 .ui-addon-row .ui-btn{width:100%;justify-content:center}}` from inside the block and put it in step 2's phone block instead (step 2 includes it; so just delete it here).
   Nested `@media` inside `@media` is valid; the existing `@media (min-width:1024px)` lines stay as they are inside the wrap.
   Check: `grep -c '^@media (min-width:768px){' App/app/static/app2.css | tail -3` prints a count that includes the new one, and `tail -3 App/app/static/app2.css | cut -c1-80` ends with `}`. Brace balance: `python3 -c "s=open('App/app/static/app2.css').read(); print(s.count('{')-s.count('}'))"` prints `0`.
   Commit: `git add App/app/static/app2.css && git commit -m "1013 step 1"` (message ends with the two attribution lines from the system reminder).

2. **Phone-only plain fallback for the three new billing blocks.** Append at the very end of `app2.css` (after the closing `}` from step 1):
   ```
   /* 1013: phones, new billing blocks stay visible but plain (no tinted box, no card). */
   @media (max-width:767px){
   body.v2 .ui-upgrade-card,body.v2 .ui-upgrade-strip,body.v2 .ui-addon-row{display:grid;gap:8px;margin:0 0 12px}
   body.v2 .ui-upgrade-card .ui-upgrade-name,body.v2 .ui-upgrade-card .ui-upgrade-price,body.v2 .ui-upgrade-card .ui-sub{margin:0}
   body.v2 .ui-upgrade-card .ui-upgrade-price{font-weight:700}
   body.v2 .ui-upgrade-card .ui-btn,body.v2 .ui-upgrade-strip .ui-btn,body.v2 .ui-addon-row .ui-btn{width:100%;justify-content:center}
   }
   ```
   Check: brace balance command from step 1c prints `0`.
   Commit: `1013 step 2`.

3. **Cache key.** In `App/app/templates/base.html` replace `/static/app2.css?v=20261108-1014` with `/static/app2.css?v=20261108-1013` (anchor: `grep -nF "app2.css?v=" App/app/templates/base.html | tail -3`; exactly one match). Then from `App/`:
   `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -10`
   Expected: writes `tests/static_versions.json`; `git diff --stat | tail -5` shows only `base.html` and `static_versions.json` changed.
   Commit: `1013 step 3`.

4. **Tests (test-map rows for what changed; from `App/`, one command each, 0 skipped).**
   ```
   UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
   UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q -x 2>&1 | tail -30
   .venv/bin/python -m pytest tests/test_billing_order.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
   ls tests | grep -iE 'property|prop_' | tail -30
   ```
   Then run the browser/geometry property editor tests from that list: at least `tests/test_0833_property_editor_browser.py`, `tests/test_host_property_controls_browser.py`, `tests/test_property_navigation_browser.py`, with `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <files> -q --tb=short -x 2>&1 | tail -30`. Drop a file that does not exist and say so.
   Expected: all pass, `0 skipped` on every browser run, zero layout-lint host findings. A test that fails because it pins a Wolt value at 390 px (for example a 776 px width or a card border on a phone): STOP and report the test name and line; do not edit tests, do not silence a finding.

5. **Screenshots (UX gate, rule 10).** Find the files: `ls /tmp/shots/layout-lint | grep -iE 'billing|plan|property-detail' | tail -30`. For Plan and billing (the `billing-plan` page; if lint has no screenshot of an active account with the upgrade card, say so) and for `property-detail` (use the `-configured+open` variant if present) open the 390, 768 and 1280 PNGs with the Read tool (tall images: crop the top 1600 px with PIL into `/tmp/crop_<name>.png` and open that). Look at what rules miss:
   - 390: old look (no centred 720/776 px column, no Wolt label/value grid, Archive in its old DOM position, Save bar as before); the upgrade card, yearly strip and TTLock row readable with full-width buttons, no overflow.
   - 768 and 1280: still the Wolt look from 807 (cards, thin borders, Archive last), unchanged.
   Save the six PNGs plus nothing else:
   ```
   mkdir -p /mnt/project-files/ux-shots/revert && cp <each file> /mnt/project-files/ux-shots/revert/<page>-<size>.png && ls -l /mnt/project-files/ux-shots/revert | tail -30
   ```
   Names: `billing-plan-390.png`, `billing-plan-768.png`, `billing-plan-1280.png`, `property-editor-390.png`, `property-editor-768.png`, `property-editor-1280.png`.
   Tests may rewrite tracked PNGs in the repo. Restore them with a path-limited checkout, never commit PNGs: `git status --short | grep -i '\.png' | tail -30`, then for each listed path `git checkout -- <path>`. Final `git status --short | tail -30` must show no PNG.

6. **Report.** Write `docs/tasks/1013-report.md` (600 tokens at most): `git diff --stat origin/main | tail -10`, last line of each command in step 4, per page "390: ...; 768: ...; 1280: ..." (what you saw, Plan and billing and property editor), the six screenshot paths, the owner decision flag from section 2 (upgrade card, strip and TTLock row kept visible and plain on phones), deviations. Set this brief `Status: review`. Commit: `git add docs/tasks/1013-report.md docs/tasks/1013-ux-wolt-desktop-only.md && git commit -m "1013 report"`.

7. **Push, no PR.** `git push -u origin claude/wolt-desktop-only 2>&1 | tail -5`. Never push to `main`. If the push is refused, give the owner the exact command in the report. Do not open a PR (the orchestrator does).

## 5. Do not touch

`billing_plan.html`, `routes/billing.py`, `host_i18n.py`, `_property_editor.html`, any test, any file outside section 3.

## 6. Commands

See the commands inside steps 0-7 above (test-map rows: layout lint browser, `test_0710_v2_mockup_match_browser.py`, `test_billing_order.py`, `test_static_versions.py`, property editor browser tests).

## 7. Acceptance

- [ ] `grep -c '1013: the whole Wolt-style restyle' App/app/static/app2.css` is 1 and the CSS brace balance is 0.
- [ ] `git diff --stat origin/main` lists only `app2.css`, `base.html`, `static_versions.json`, this brief and the report.
- [ ] Layout lint and `test_0710_v2_mockup_match_browser.py`: green, 0 skipped. `test_billing_order.py` and the property editor browser tests green.
- [ ] Six screenshots exist in `/mnt/project-files/ux-shots/revert/`; no PNG in `git status`.
- [ ] Branch `claude/wolt-desktop-only` pushed; nothing on `main`.

## 8. Stop and ask

An anchor is missing or other rules follow the Wolt block; a test needs a test edit; a layout-lint finding at 390 px that only the old look would clear; more than 30 tool calls. Stop, write what you found in the report, hand over.

## 9. Report

Step 6 writes `docs/tasks/1013-report.md`; reply with its path and the owner decision flag.
