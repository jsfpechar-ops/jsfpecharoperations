# 0736 report (executor, Haiku 5.5)

Status: blocked
Done: step 1, item 2 only (test_property_navigation_browser.py). Left: items 1, 6 (step 1), steps 2, 3, 4.

## Files changed
- App/tests/test_property_navigation_browser.py: item 2. Save from section=automation now asserts section=reporting.

## Item 1 (unsaved changes): not fixed
- Brief fix applied (read loaded_status after the #sec-lock summary click). Still fails: `assert 'Enabled' == ''` at tests/test_host_unsaved_changes_browser.py:283 (en/cs, 360 and 1280). Reverted, so the file is unchanged.
- Brief's diagnosis does not match: the status text reads '' even with the section open. Needs owner or orchestrator review.

## Item 6 (controls): not fixed
- tests/test_host_property_controls_browser.py:448 fails before the `select_option("other")` step: `#label_other` is visible by default, so the brief's "section closed" cause does not hold. Reverted, so the file is unchanged.
- test_property_and_operator_controls_render_and_work_in_browser also fails. Not named in the brief; not investigated.

## Test results (chromium, -k "not webkit")
- tests/test_property_navigation_browser.py: `12 passed in 15.25s`
- tests/test_host_unsaved_changes_browser.py: `4 failed` (save_bar_discard, the 4 parametrized cases), line 283 as above
- tests/test_host_property_controls_browser.py: `2 failed` (see item 6)

## Not run
- Items 3, 4, 5, 7, 8, section 6 commands, screenshots. Stopped at the step-1 failures per executor rules.
- webkit not installed (not run).

## Questions
1. Item 1: the status element may only fill on toggle. Should the test click the door-code switch first, then assert the loaded text, or compare against a known string?
2. Item 6: why is #label_other visible at line 448 when the platform is the default? Is the expected state wrong, or was the brief's failure from another test?
3. Report path: the executor doc says docs/tasks/NNNN-report.md; the brief says section "0736" in docs/tasks/0536-report.md. This report uses docs/tasks/0736-report.md.

## Owner steps left
- None yet. No push, no PR (status blocked).

## Run 2 (section 10 items 1 and 6; commit bec40cd)
Status: blocked
Done: items 2 (1de31cd), 1 (partly), 6. Left: items 1 (focus assertion, JS), 3, 4, 5, 7, 8, section 6, screenshots.

### Item 1 diagnosis (temporary probe, deleted, not committed)
- `#door_codes-status` exists once. At load and after `#sec-lock > summary` click: textContent "Enabled", display inline, visibility visible, nearest details open.
- `innerText` is "" in both states, so the old test read "" before the section opened. Cause of the blank innerText not traced further (an ancestor is not rendered; not checked).
- JS (app.js ~2029) sets textContent to data-on/data-off/data-unsaved, so textContent is the right comparison. Changed the test to read `loaded_status` after the summary click and to use `text_content().strip()`.
- Remaining failure: `_focused(page)` after discard is the skip link, not the save button (line 287, en/cs, 360 and 1280). app.js ~2111 focuses `.host-property-save [type=submit]` or `.actions [type=submit]` after reset; neither selector matches the savebar at `_property_editor.html:385`, so nothing is focused. Fix needs a JS selector change (brief section 8 stop). Not done.

### Item 6 (controls)
- Cause: the hide rule for `.calendar-other-platform` is in `host.css` (line 796), which v2 does not load. Added to `app2.css` end: `body.v2 .calendar-add-form:has(#label option[value="other"]:not(:checked)) .calendar-other-platform{display:none}`. No JS change.
- `test_host_property_controls_browser.py`: 2 passed, 1 failed. Failing `test_property_and_operator_controls_render_and_work_in_browser` at line 232: `/apartments?lang=en` has 0 `.ui-tabs`, expected 1 (0099 list tabs). List-page markup, not triaged further; not ours or needs owner call.

### Key bump
- `base.html` app2.css `?v=20261101-0735` to `20261101-0736`; `test_static_versions.py --write` (41 files); static tests 3 passed.

## Test results (chromium, -k "not webkit", UBYHOST_REQUIRE_BROWSER=1)
- tests/test_host_unsaved_changes_browser.py: `4 failed, 11 passed in 21.47s` (save_bar_discard, focus line 287)
- tests/test_host_property_controls_browser.py: `1 failed, 2 passed in 12.10s` (line 232, see above)
- tests/test_static_versions.py: `3 passed in 0.10s`
- tests/test_property_navigation_browser.py: 12 passed (run 1)

## Not run
- Items 3, 4, 5, 7, 8, section 6 remaining files, design_lint, context_lint, screenshots (`docs/tasks/screenshots-0736/`): none taken. Stopped at the checkpoint (about 50k tokens, 20 tool calls).
- webkit not installed (not run).

## Deviations
- Done: steps 1 (partial). Left: items 3, 4, 5, 7, 8; section 6 commands and screenshots. Next session starts at item 1 focus fix (needs JS selector change: owner or orchestrator call), then items 3 to 5 (CSS and heading), then 7, 8.

## Questions
1. Item 1 focus: may the JS selector in app.js (~2111) change to the savebar's submit (`.savebar [type=submit]`), or should the test assert focus on the page instead?
2. Item 6 list test at line 232: is `.ui-tabs` on `/apartments` expected in v2, or should the 0099 assert change?

## Owner steps left
- None. No push, no PR.

## Run 3 (section 11 first, then items 3 to 5; commits b6235d7, step 2)
Status: blocked
Done: section 11 item 1 (focus selector `.savebar [type=submit]` first, dead `.host-property-save` dropped, app.js key 0736). Item 3 CSS and heading (h2 in `_property_editor.html`), item 4 CSS, item 5 test change. Left: item 3 a11y still fails, item 4 still fails, item 6 list test, items 7, 8, section 6 remainder, screenshots.

### Test results (chromium, UBYHOST_REQUIRE_BROWSER=1, -k "not webkit"; webkit not installed)
- tests/test_host_unsaved_changes_browser.py: `15 passed in 20.75s` (0 skipped)
- tests/test_0252_touch_sweep_browser.py: `1 passed in 34.20s`
- tests/test_static_versions.py: written with `App/tests/test_static_versions.py --write` (41 files); pytest flag `--write` is not accepted by pytest.
- tests/test_a11y_guard_browser.py: `2 failed, 2 passed in 78.70s`. `test_every_page_passes_the_page_checks`: `12 findings {'heading-level-skipped': 12}` after the h2 change. `test_keyboard_focus_is_visible_and_not_covered`: `focus-not-visible` on `properties 1280 button#:Copy link`. Not analysed further.
- tests/test_onboarding_wizard_browser.py: `4 failed, 81 passed in 175.79s`. `test_wizard_polish_and_overview_cards[False-360-en|360-cs|390-cs]` still overflow on `/apartments/1?view=settings&section=guests`, so the item 4 CSS did not fix it. `test_review_fixes_in_the_browser` also fails (not in brief, not triaged).

### Item 5 change
- No cue in the mockup props view (rows have only a `.dots` cell). Test change only: in `test_0252_touch_sweep_browser.py` the noCue probe skips `tr.clickable-row` inside `.props-card` (the v2 list row is role=link). Scoped to the v2 list, not all pages.

### Not checked
- Setup-continue contrast: `color:#fff` on `var(--coral-600)` (#ad4942), computed about 5.5:1 by hand; not measured in the browser.
- Screenshots (`docs/tasks/screenshots-0736/`): none taken.

## Deviations
- Done: section 11 item 1; items 3 (partial), 5; item 4 (CSS only, test still failing). Left: a11y heading findings and focus finding; onboarding 360/390 overflow; item 6 list test; items 7, 8; section 6 remainder; screenshots.
- The brief file `docs/tasks/0736-property-page-last-ci-fixes.md` has the orchestrator's sections 10 and 11 uncommitted in the working tree; not staged by the executor.

## Questions
1. Heading: which heading is skipped now (12 findings)? Needs a look at the page-check output with the h2 change.
2. Onboarding guests at 360: what element is wider than the viewport on the guests section (probe needed)?

## Owner steps left
- None. No push, no PR.
