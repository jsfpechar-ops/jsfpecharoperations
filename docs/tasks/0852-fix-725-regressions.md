# 0852 PR #725: real regressions and v2 mockup baselines

Status: todo

Orchestrator note: confirm sections 2B-2D against a fresh CI run after 0851 merges into the branch, then hand to the executor.

## 1. Objective

Fix the browser failures on PR #725 that are not stale locators (those are [0851](0851-fix-725-ci-and-savebar.md)). Run after 0851, same branch `work`. Executor: Haiku 5.5; read only AGENTS.md, executor.md, this brief, and the files named per step.

## 2. Context: triage (orchestrator run on branch 560aea4; main 89a08e1 passes all of these)

### A. v2 mockup style test (`tests/test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles`, 36 cases: cleaning, overview, properties, property, stay, stays) = intended redesign, update the baseline in `App/tests/v2_mockup.py`
Diffs seen: overview 390 `.card.need` padding 16 vs 22, border colour, `.hs .card`; properties 390 `.big, .head h1` size, `.card.prop` radius 12 vs 24, padding 20 vs 16; property 390 `.prop-phone-top .round` and `.prop-phone-top ~ h1.big` missing, `.guest-card` radius/border; property 1280 `.crumb` and `summary small` missing, `main h1` 32/700 vs 24/800; stay 390 `.stay-top .round`, `.host-stay-detail h1.big` missing (19 diffs). The Airbnb design (back header, 12 px value cards, 32/700 titles) is the decision; the mockup file is older.
Steps: (1) For each removed selector add a `missing_ok` entry in that page's spec with reason `"PR #725: Airbnb back header replaces it"` (`.crumb`, `summary small`, `.prop-phone-top .round`, `.prop-phone-top ~ h1.big`, `.stay-top .round`, `.host-stay-detail h1.big`). (2) For style diffs, read `expected_value()` (v2_mockup.py line ~132, read lines 120-160 only) and add each (selector, prop) -> app value listed in the failure message as an override with comment `# PR #725 Airbnb redesign`; for box widths/heights add `phone_box_skip` entries with the same reason. Do not change CSS for these. Command: `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs 2>&1 | tail -30`; repeat once per page if new diffs appear.

### B. Layout guard (`tests/test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard`) = real regressions, fix CSS
- `invoice-detail`, `invoice-new-selected` at 1280/2000: `a.ui-btn.ui-btn-quiet "Invoice settings"` is 24 px tall next to 37 px buttons (button-heights-differ). Fix in `App/app/static/app2.css` (append block `/* 0852 */`): the quiet link in that action row gets the same height as its neighbours (`min-height:var(--control-h);display:inline-flex;align-items:center`), scoped to the row's container class (find it with `grep -n "invoice_settings\|Invoice settings" App/app/templates/invoice_detail.html App/app/templates/invoice_form.html`).
- Same pages at 390: `td "2 nights"` not under `th "Qty"` (cell-not-under-header). Compare `git diff 89a08e1 -- App/app/templates/invoice_detail.html App/app/templates/invoice_form.html`; revert only the table markup change that moved the cell.
- `fee-setup`, `property-detail`, `guest-links`, `automation` at 1280/2000: `button#fee-copy-apply` 13 px off `select#stay_fee_cadence` (field-button-misaligned). Align the button to the select's bottom in the 0852 block (`align-self:end` on the button's grid/flex cell, found via `grep -n fee-copy-apply App/app/templates/_stay_fee_fields.html`).

### C. Missing hooks the branch dropped = regressions, restore the hook (not the old look)
- `tests/test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus` (6 widths): times out on `[data-host-account] > summary`. Check `git diff 89a08e1 -- App/app/templates/base.html`; if the account `<details data-host-account>` was removed or renamed, restore the attribute.
- `tests/test_host_wide_geometry_browser.py` (7 tests): `button[data-sidebar-collapse]` not found, `getComputedStyle` on null, and `properties` at 1024/1440 "layout does not follow the panel width". Diff `App/app/templates/apartments.html` against 89a08e1; restore any removed `data-*` hook and lane class; the properties list must use the same lane wrapper as main.
- `tests/test_host_list_cards_browser.py::test_list_panels_never_scroll_sideways_and_actions_stay_visible`: "synthetic persistent date-change alert not rendered on invoice-new-picker/en/1024"; diff `App/app/templates/invoice_stay_picker.html` against 89a08e1 and restore the alert slot.

### D. Not yet diagnosed (run, read the last 30 lines, fix only if it is a dropped hook or a stale locator for the new design; else STOP and report)
`tests/test_design_guardrails_browser.py::test_sidebar_search_has_a_border`, `tests/test_a11y_guard_browser.py::test_every_page_passes_the_page_checks`, `tests/test_host_help_browser.py` (help-tip interactions, target size), `tests/test_havel_browser.py::test_phone_launcher_and_sheet`. Likely cause for help tips: `page_help()` "?" beside titles (new) must keep >= 24 px target and fit the viewport; fix in CSS, not by loosening the test.

## 3. Files

`App/tests/v2_mockup.py`, `App/app/static/app2.css` (append one `/* 0852 */` block), and only the templates named in 2B-2C (`invoice_detail.html`, `invoice_form.html`, `invoice_stay_picker.html`, `_stay_fee_fields.html`, `apartments.html`, `base.html`), only to restore a dropped hook or table cell.

## 4. Steps

In order 2A, 2B, 2C, 2D; one commit per bullet, message `0852 step k`. Each bullet's fix and command are in section 2.

## 5. Do not touch

Guest pages, UbyPort/submission code, migrations, i18n strings, templates' copy, `test_motion_browser.py`, `main`. No new dependency (playwright 1.63.0 is already the pinned test tool). No push, no merge, no deploy.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, each with `-q --tb=short -rs 2>&1 | tail -30`)
Per section, only the tests named there. At the end: `tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py` once. Ignore `test_motion_browser.py` (4 known fails on main). One 390 screenshot per changed page (invoice detail, property editor, properties list).

## 7. Acceptance
- [ ] Every test named in 2A-2D passes with 0 skipped, or is listed under Questions with its last 5 lines.
- [ ] No test loosened except the 2A baseline entries, each with a reason.

## 8. Stop and ask

An anchor is not found, a fix would change the Airbnb design (back header, pills, value cards, help "?" beside the title), a test still fails after one fix, or a section 2D cause is not a dropped hook or stale locator.

## 9. Report

`docs/tasks/0852-report.md` per executor.md (files, commands with last 5 lines, section 7 ticked, deviations, questions, screenshots). Do not push or merge; the owner merges with `scripts/merge-pr-on-green.sh`.
