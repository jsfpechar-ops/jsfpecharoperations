# 0852 PR #725: real regressions and v2 mockup baselines

Status: todo

Orchestrator note: 2B-2D causes confirmed and every fix test-run locally on e4423c2 (0851 applied); ready for the executor.

## 1. Objective

Fix the browser failures on PR #725 left after [0851](0851-fix-725-ci-and-savebar.md): v2 mockup baselines (2A), CSS regressions (2B) and tests that still point at pages PR #725 moved to v2 (2C, 2D). Run after 0851, same branch `work`. Executor: Haiku 5.5; read only AGENTS.md, executor.md, this brief, and the files named per step.

## 2. Context: triage (orchestrator run on branch 560aea4; main 89a08e1 passes all of these)

### A. v2 mockup style test (`tests/test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles`, 36 cases: cleaning, overview, properties, property, stay, stays) = intended redesign, update the baseline in `App/tests/v2_mockup.py`
Diffs seen: overview 390 `.card.need` padding 16 vs 22, border colour, `.hs .card`; properties 390 `.big, .head h1` size, `.card.prop` radius 12 vs 24, padding 20 vs 16; property 390 `.prop-phone-top .round` and `.prop-phone-top ~ h1.big` missing, `.guest-card` radius/border; property 1280 `.crumb` and `summary small` missing, `main h1` 32/700 vs 24/800; stay 390 `.stay-top .round`, `.host-stay-detail h1.big` missing (19 diffs). The Airbnb design (back header, 12 px value cards, 32/700 titles) is the decision; the mockup file is older.
Steps: (1) For each removed selector add a `missing_ok` entry in that page's spec with reason `"PR #725: Airbnb back header replaces it"` (`.crumb`, `summary small`, `.prop-phone-top .round`, `.prop-phone-top ~ h1.big`, `.stay-top .round`, `.host-stay-detail h1.big`). (2) For style diffs, read `expected_value()` (v2_mockup.py line ~132, read lines 120-160 only) and add each (selector, prop) -> app value listed in the failure message as an override with comment `# PR #725 Airbnb redesign`; for box widths/heights add `phone_box_skip` entries with the same reason. Do not change CSS for these. Command: `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs 2>&1 | tail -30`; repeat once per page if new diffs appear.

### Root cause for 2B-2D (verified locally on e4423c2; every fix below was applied and run, then reverted)
PR #725 set `{% set v2 = true %}` on `payments.html`, `invoice_detail.html`, `invoice_form.html`, `invoice_stay_picker.html`, `submission_detail.html` (and billing, Leon, cleaning settings, guest questions). A v2 page loads `app2.css` instead of `app.css`/`host2.css`, gets the v2 shell (no old sidebar, no More sheet) and no alert stack (`base.html` line 78). The move to v2 is the Airbnb redesign (keep it). Result: tests that used `/payments` as "the old shell page" are stale (old shell still lives on `/invoices`, `/stay-fees`, `/submissions`), and the invoice pages lost some `host2.css` styling = real CSS regressions.

### B. CSS fixes: append this exact block at the end of `App/app/static/app2.css` (one commit, `0852 step B`)
```css
/* 0852 */
body.v2 a.ui-btn-primary{color:#fff}
body.v2 .e-page .stay-command-actions .ui-btn-quiet{align-self:stretch;font-size:14px}
body.v2 #stay-fee-settings > .field:has(> .copyrow){grid-column:1 / -1}
body.v2 .prop-sec .copyrow{display:flex;flex-wrap:wrap;align-items:center;gap:12px}
body.v2 .prop-sec .copyrow > select#fee-copy-source{margin-bottom:0;flex:1 1 220px;min-width:0}
body.v2 .props-card thead{display:table-header-group}
@media (max-width:1023px){body.v2 .e-page table.ui-table-stack thead{display:none}}
```
Why, line by line:
1. a11y contrast 3.72 on "Download PDF" (invoice-detail, invoice-new-selected, en+cs, 390+1280): `:where(body.v2 .ui-btn)` sets white text with 0 specificity, so `body.v2 a{color:inherit}` wins and an `<a class="ui-btn ui-btn-primary">` gets ink on coral. White on coral is about 4.6:1.
2. button-heights-differ (invoice pages 1280/2000): `.e-page .ui-btn-group` centres items and `body.v2 .ui-btn-quiet` is 24 px / 12 px text, so "Invoice settings" (invoice_detail.html line 54) is 24 px beside 37 px buttons. Stretch it to the row height; 14 px text (no fine text).
3-5. field-button-misaligned, `#fee-copy-apply` vs `#stay_fee_cadence` -13 px (fee-setup, property-detail, guest-links, automation at 1280/2000; fee-setup 390 after the first fix): `#stay-fee-settings` is a 2-column grid, so the "Copy from" field sat beside the cadence select, and the `.prop-sec select{margin-bottom:12px}` rule (0830C) offset it. The copy field now spans the full row, and its select and Copy button share one centred flex row. Line 5 needs the `#fee-copy-source` id: the 0830C margin rule has higher specificity.
6. properties 1024/1440 "layout does not follow the panel width" (`test_host_list_cards_browser.py`): 0830C added `body.v2 .props-card thead{display:none}` (app2.css about line 1361), which hides the desktop table headers and also removes them from screen readers. Restore them. Side effect: the 2A properties mockup run then shows `main table th padding-left: app=16px mockup=14px` and `.head .sub: missing in app`; add those to the 2A baseline (override and `missing_ok`, reason `"PR #725: Airbnb back header replaces it"`).
7. cell-not-under-header `td "2 nights"` / `th "Qty"` (invoice pages 390): the v2 stacked table clips its thead to 1x1 px but the th boxes still sit at desktop positions. Below 1024 px the stacked rows carry `data-label` captions, so hide the thead as the v2 entities and technical tables already do (app2.css lines about 1136 and 1167). Do not change the table markup.
Command: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard tests/test_a11y_guard_browser.py::test_every_page_passes_the_page_checks tests/test_host_list_cards_browser.py -q --tb=short -rs 2>&1 | tail -30`

### C. Stale tests: old-shell checks move from `/payments` to `/invoices` (one commit, `0852 step C`)
`/invoices` (`invoices.html`, no `v2`) still renders `_shell_sidebar.html` (`button[data-sidebar-collapse]`, `[data-host-account]`, `.ui-search-row`) and the old tabbar (`[data-sheet-open='more-sheet']`). The hooks were not dropped; `/payments` just moved to v2. Exact edits (each old string occurs once):
- `App/tests/test_design_guardrails_browser.py` (`test_sidebar_search_has_a_border`): `page.goto(f"{wide_base}/payments?lang=en")` -> `page.goto(f"{wide_base}/invoices?lang=en")`.
- `App/tests/test_onboarding_followup_browser.py` (`test_rows_hover_...`, the `width >= 1440` branch): `page.goto(f"{base}/payments?lang={lang}")` -> `page.goto(f"{base}/invoices?lang={lang}")`.
- `App/tests/test_havel_browser.py` (`test_phone_launcher_and_sheet`): `page.goto(origin[0] + "/payments")` -> `page.goto(origin[0] + "/invoices")`; in the comment above it, `/payments (0785a)` -> `/invoices (0852: /payments is v2 since PR #725)`.
- `App/tests/test_host_wide_geometry_browser.py`:
  - `("payments", "/payments", ".ui-section"),` -> `("invoices", "/invoices", ".ui-table-wrap, .ui-empty"),` and in the comment above it `runs on /payments` -> `runs on /invoices`.
  - `def _rail_page(context, wide_base, path="/payments"):` -> `def _rail_page(context, wide_base, path="/invoices"):` and in the comment above it `run on /payments` -> `run on /invoices`.
  - `test_host_wide_lanes_align` ("synthetic persistent date-change alert not rendered on invoice-new-picker"): the v2 shell has no alert stack by design (0538 precedent; the dashboard card carries the alert). Extend the existing tuple: `"guest-links", "automation", "smart-locks"):` -> `"guest-links", "automation", "smart-locks", "invoice-new-picker", "invoice-new-selected", "invoice-detail", "submission-detail"):`.
Command: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py::test_sidebar_search_has_a_border tests/test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus tests/test_havel_browser.py::test_phone_launcher_and_sheet tests/test_host_wide_geometry_browser.py -q --tb=short -rs 2>&1 | tail -30`

### D. Stale tests: property-page hint is behind its "?" again (one commit, `0852 step D`)
PR #725 (app2.css `body.v2 .property-settings-form .help-tip*`, about lines 1530-1540 of the 0831 block) turned the always-visible property hints into 24 px "?" tips with a 50 px hit area (`::after inset:-13px`), opened by click/focus/hover. This is the intended design; 0543's "hint always visible" assertions are stale. Edits in `App/tests/test_host_help_browser.py`:
- In `_open_page`: `page.locator(TIP).scroll_into_view_if_needed()  # 0543: the ? button is hidden on the v2 property page` -> `page.locator(BTN).scroll_into_view_if_needed()  # PR #725: the hint sits behind the ? button again`.
- In `test_help_tip_interactions_aria_and_fit`: replace the two lines `            # the hint is visible in its field and inside the viewport` / `            tip.wait_for(state="visible")` with four lines: `            # the hint opens from its ? button and stays inside the viewport` / `            button.click()` / `            tip.wait_for(state="visible")` / `            assert button.get_attribute("aria-expanded") == "true"`.
- In the touch loop: before `                tpage.locator(TIP).wait_for(state="visible")` insert `                tpage.locator(BTN).click()`.
- In `test_help_tip_target_size_and_no_js_reachability`: before `        tip = page.locator(TIP)` insert `        page.locator(BTN).focus()  # PR #725: without JS the hint shows on focus/hover of its ? button`.
Command: `.venv/bin/python -m pytest tests/test_host_help_browser.py -q --tb=short -rs 2>&1 | tail -30`

Verified result with B+C+D applied: the 8 test targets above gave 31 passed, 0 skipped; `tests/test_design_guardrails_browser.py` fully passes. Only the 2A mockup cases still fail until 2A is done.

## 3. Files

`App/tests/v2_mockup.py` (2A), `App/app/static/app2.css` (append the one `/* 0852 */` block from 2B), `App/tests/test_design_guardrails_browser.py`, `App/tests/test_onboarding_followup_browser.py`, `App/tests/test_havel_browser.py`, `App/tests/test_host_wide_geometry_browser.py` (2C), `App/tests/test_host_help_browser.py` (2D). No template changes.

## 4. Steps

In order 2B, 2C, 2D, then 2A last (2B changes the properties mockup diffs); one commit per section, message `0852 step <letter>`. Each section's exact edit and command are in section 2.

## 5. Do not touch

Guest pages, UbyPort/submission code, migrations, i18n strings, templates' copy, `test_motion_browser.py`, `main`. No new dependency (playwright 1.63.0 is already the pinned test tool). No push, no merge, no deploy.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, each with `-q --tb=short -rs 2>&1 | tail -30`)
Per section, only the tests named there. At the end: `tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py` once. Ignore `test_motion_browser.py` (4 known fails on main). One 390 screenshot per changed page (invoice detail, property editor, properties list).

## 7. Acceptance
- [ ] Every test named in 2A-2D passes with 0 skipped, or is listed under Questions with its last 5 lines.
- [ ] No test loosened except the 2A baseline entries (each with a reason) and the 2C/2D page and interaction moves written in this brief.

## 8. Stop and ask

An anchor is not found, a fix would change the Airbnb design (back header, pills, value cards, help "?" beside the title), or a test still fails after one fix (report its last 5 lines).

## 9. Report

`docs/tasks/0852-report.md` per executor.md (files, commands with last 5 lines, section 7 ticked, deviations, questions, screenshots). Do not push or merge; the owner merges with `scripts/merge-pr-on-green.sh`.
