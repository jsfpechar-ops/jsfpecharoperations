# 0851 PR #725: fix CI (stale tests) and the property editor savebar

Status: todo

## 1. Objective

Make PR #725 (branch `work`, head 560aea4) green for the unit job and for the browser tests that only check old markup, and restyle the property editor savebar. Real regressions and the v2 mockup diffs are in [0852](0852-fix-725-regressions.md); do not touch them here.

Executor: Haiku 5.5. Branch `work` (PR #725). Read only AGENTS.md, docs/context/executor.md, this brief and the files named here. The intended new design stays: Airbnb back header (`partials/settings_back_header.html`: `div.airbnb-header > a.airbnb-back + h1.airbnb-title`), pills (`partials/settings_pills.html`: `nav.settings-pills > a.settings-pill.is-current`), value cards, help "?" beside the title (`page_help()`).

## 2. Context (orchestrator triage 2026-11-02, branch vs main 89a08e1)

Main passes all of these; only its 4 `test_motion_browser.py` tests fail (known, ignore them). Every failure below is a **stale assertion**: the branch replaced `.crumb`, `a.round` back buttons, `div.chips.stays-chips` and the `/payments` old shell on purpose.

| Test | Cause | Fix |
|---|---|---|
| `test_0534_property_page_v2.py::test_page_is_one_scroll_page_without_tabs` | `.crumb` replaced by the back header | assert `class="airbnb-back"` |
| `test_design_properties.py::test_property_page_keeps_local_tabs_without_section_tabs` | same | same |
| `test_overhaul.py::test_filtered_stays_return_path_and_guest_links_workspace` | stay detail back link is now `a.airbnb-back` with aria-label "Back", not "Back to stays" | assert `class="airbnb-back"` |
| `test_signed_in_chrome.py::test_a_workspace_with_a_property_keeps_the_page_header` | `ph-hide` span now also holds `page_help('dashboard')` after the title | assert the span start only |
| `test_signed_in_chrome.py::test_the_support_line_is_not_part_of_the_legal_link_row` | `/payments` is v2 now (no old rail) | use `/stay-fees` (old shell, `stay_fees.html` has no `set v2`) |
| `test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar` | same | use `/stay-fees` |
| `test_stays_empty_workspace.py::test_the_toolbar_and_filters_return_with_a_property` | chips became pills | assert `<div class="stays-pills">` |
| `test_host_unsaved_changes_browser.py` (property_settings_save_discard_stay x4, keyboard_only_flow, without_javascript_nothing_changes), `test_property_navigation_browser.py::test_tabs_hashes_drafts_history_and_validation_in_browser`, `test_fee_setup_compatibility.py::test_set_up_link_opens_visible_editor_and_save_returns_to_the_list` | locators `.crumb a`, `.crumb a[href="/apartments"]`, `a.round[href="/apartments"]` time out | use `a.airbnb-back` |
| `test_host_filter_panels_browser.py::test_filter_draft_calendar_and_month_grid_commit_once` | waits for `.chips .chip.on` on /reservations | use `.settings-pills .settings-pill.is-current` |

Savebar (Josef: "weird"): `App/app/templates/_property_editor.html` line ~385 has `div.savebar` = `a.btn.ghost` Cancel, `button.btn.ghost[data-unsaved-reset][hidden]` Discard changes, `button.btn[type=submit]` Save changes. CSS is scattered in `App/app/static/app2.css` (lines 352-353, 821, 944, 946, 993-996, 1007-1010, 1020): fixed floating buttons at desktop, wrapping 30%/100% buttons at phone. Do not change the template or any copy; override with one CSS block.

## 3. Files

Tests: `App/tests/test_0534_property_page_v2.py`, `test_design_properties.py`, `test_overhaul.py`, `test_signed_in_chrome.py`, `test_0705_v2_shell_browser.py`, `test_stays_empty_workspace.py`, `test_host_unsaved_changes_browser.py`, `test_property_navigation_browser.py`, `test_fee_setup_compatibility.py`, `test_host_filter_panels_browser.py`, `v2_mockup.py`. CSS: `App/app/static/app2.css` (append only). New: `App/tests/test_0851_savebar_browser.py`.

## 4. Steps (one commit each, message `0851 step k`)

1. `test_0534_property_page_v2.py` line 35: `assert 'class="crumb"' in html` -> `assert 'class="airbnb-back"' in html`.
2. `test_design_properties.py` line 22: `'class="crumb"' in detail` -> `'class="airbnb-back"' in detail`.
3. `test_overhaul.py` line 509: `assert "Back to stays" in detail.text` -> `assert 'class="airbnb-back"' in detail.text`. Keep line 510 (the return_to href check).
4. `test_signed_in_chrome.py` line 206: replace `f"<span class=\"ph-hide\">{host_i18n.STRINGS['en']['dashboard.title']}</span>" in page` with `f"<span class=\"ph-hide\">{host_i18n.STRINGS['en']['dashboard.title']}" in page` (drop only `</span>`). Line 133: `/payments?lang=en` -> `/stay-fees?lang=en`, comment -> `# old-shell rail; /payments is v2 since PR #725`.
5. `test_0705_v2_shell_browser.py` line 17: `/payments?lang=en` -> `/stay-fees?lang=en`; line 16 comment: replace `/payments (held for the Stripe rework)` with `/stay-fees (/payments is v2 since PR #725)`.
6. `test_stays_empty_workspace.py` line 232: `'<div class="chips stays-chips">'` -> `'<div class="stays-pills">'`.
7. Browser locators. Run `grep -nE 'crumb|a\.round\[href' App/tests/test_host_unsaved_changes_browser.py App/tests/test_property_navigation_browser.py App/tests/test_fee_setup_compatibility.py`. In every **locator string** (inside `locator(`, `click(`, `focus(`, `wait_for_selector(`, `query_selector(`) replace `.crumb a[href="/apartments"]`, `.crumb a` and `a.round[href="/apartments"]` with `a.airbnb-back`. Leave other `crumb` text (comments, asserts on HTML) alone; if an assert says `crumb` must be present, STOP and ask.
8. `test_host_filter_panels_browser.py`: `grep -n 'chip' ` the file; replace `.chips .chip.on` with `.settings-pills .settings-pill.is-current` and `.chips .chip` with `.settings-pills .settings-pill` only where the page is `/reservations` (stays). Leave other routes.
9. `v2_mockup.py` line 216: remove `".savebar .btn",` from the `property` spec `selectors` (comment `# 0851: savebar has its own test, test_0851_savebar_browser.py`).
10. Savebar CSS. Append at the end of `App/app/static/app2.css` exactly:
```css
/* 0851 property editor savebar: Discard/Cancel as quiet text left, Save as the one coral pill right */
body.v2 form.property-settings-form .savebar,body.v2 form.property-settings-form:has(details.prop-sec[open]) .savebar{position:sticky;left:auto;right:auto;bottom:0;z-index:20;width:auto;flex-wrap:nowrap;align-items:center;justify-content:space-between;gap:16px;margin:24px 0 0;padding:12px 0 calc(12px + env(safe-area-inset-bottom,0px));background:#fff;border-top:1px solid var(--line);white-space:nowrap}
body.v2 form.property-settings-form .savebar .btn,body.v2 form.property-settings-form:has(details.prop-sec[open]) .savebar .btn{flex:0 0 auto;width:auto;min-width:0;height:48px;min-height:48px;padding:0 24px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;font-size:16px;font-weight:600;line-height:1;white-space:nowrap}
body.v2 form.property-settings-form .savebar .btn.ghost,body.v2 form.property-settings-form:has(details.prop-sec[open]) .savebar .btn.ghost{margin-right:auto;padding:0 12px;background:transparent;border:0;color:var(--ink);text-decoration:underline;text-underline-offset:3px}
body.v2 form.property-settings-form .savebar .btn[type="submit"],body.v2 form.property-settings-form:has(details.prop-sec[open]) .savebar .btn[type="submit"]{margin-left:auto;min-width:160px;background:var(--acc);color:#fff;border:0}
body.v2 form.property-settings-form .savebar:has([data-unsaved-reset]:not([hidden])) a.btn.ghost{display:none}
body.v2 form.property-settings-form .savebar [hidden]{display:none}
@media (max-width:1023px){body.v2 form.property-settings-form .savebar,body.v2 form.property-settings-form:has(details.prop-sec[open]) .savebar{bottom:calc(var(--tabbar-h) + var(--tabbar-safe));padding-bottom:12px}}
```
Do not set `display` on `.savebar` (the phone rule that hides it until a section is open stays). Rules 6, 7, 9 hold: light only, no copy change, one coral primary.
11. New `App/tests/test_0851_savebar_browser.py`. Open `App/tests/test_0833_property_editor_browser.py` (if absent, `App/tests/test_0830_airbnb_pages_browser.py`) and copy its imports, fixtures and the way it opens the property editor (`/apartments/<id>?view=settings`). One test, parametrized over viewports (390,844), (768,1024), (1280,900): open the editor, make sure `#sec-basics` is open, fill the first `#sec-basics input[type=text]` with its value + `" x"` (this shows Discard), then measure with `page.evaluate` the boxes of `.savebar [data-unsaved-reset]` (D), `.savebar [type=submit]` (S) and `.savebar` (B). Assert: D and S visible; `abs(D.height-48)<=1` and `abs(S.height-48)<=1`; `abs(D.top-S.top)<=1` (no wrap); `S.left - D.right >= 12`; `D.left < S.left`; `S.right <= innerWidth - 12`; `B.bottom <= innerHeight + 1`; `document.documentElement.scrollWidth <= innerWidth`; `a.btn.ghost` inside `.savebar` is hidden. At 390 save `docs/tasks/screenshots-0851/property-savebar-390.png` (`page.screenshot(path=..., full_page=False)`).

## 5. Do not touch

Guest pages, UbyPort/submission code, migrations, i18n strings, templates' copy, `test_motion_browser.py`, `main`. No new dependency (playwright 1.63.0 is already the pinned test tool). No push, no merge, no deploy.

## 6. Commands (from `App/`; browser needs `.venv/bin/pip install playwright==1.63.0` once and `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)

- Steps 1-6: `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_design_properties.py tests/test_overhaul.py tests/test_signed_in_chrome.py tests/test_0705_v2_shell_browser.py tests/test_stays_empty_workspace.py -q --tb=short -x 2>&1 | tail -30`
- Step 7: `.venv/bin/python -m pytest tests/test_host_unsaved_changes_browser.py tests/test_property_navigation_browser.py::test_tabs_hashes_drafts_history_and_validation_in_browser tests/test_fee_setup_compatibility.py::test_set_up_link_opens_visible_editor_and_save_returns_to_the_list -q --tb=short -rs 2>&1 | tail -30`
- Step 8: `.venv/bin/python -m pytest tests/test_host_filter_panels_browser.py::test_filter_draft_calendar_and_month_grid_commit_once -q --tb=short -rs 2>&1 | tail -30`
- Steps 9-11: `.venv/bin/python -m pytest tests/test_0851_savebar_browser.py tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_0541_property_page_phone_browser.py -q --tb=short -rs 2>&1 | tail -30`
- Then: `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py::test_sidebar_search_has_a_border -q --tb=short -rs 2>&1 | tail -30` (layout-guard failures belong to 0852; note them, do not fix).
- Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

Each browser run is slow (up to 8 min); run each once, never the whole suite. Ignore `test_motion_browser.py`.

## 7. Acceptance

- [ ] All commands above pass, 0 skipped.
- [ ] Screenshot `docs/tasks/screenshots-0851/property-savebar-390.png` in the report (Discard left as underlined text, Save coral pill right, one row, 48 px).
- [ ] No template, copy or i18n change. No App/ change outside the files in section 3.

## 8. Stop and ask

An anchor is not found, a test still fails after one fix, a test asserts the old markup must exist (not just appear), or the savebar overlaps the phone tab bar in the screenshot.

## 9. Report

`docs/tasks/0851-report.md` per executor.md (files, commands with last 5 lines, section 7 ticked, deviations, questions, screenshots). Do not push or merge; the owner merges with `scripts/merge-pr-on-green.sh`.
