# 0955 report (chat 1 of 4)
Status: blocked

## Files changed
- App/app/templating.py (inline_flash_section from ?sec=, property page only)
- App/app/templates/_section_notice.html (new macro)
- App/app/templates/base.html (toast suppressed for inline section; ?v=20261104-0955a)
- App/app/templates/_property_editor.html (import, 7 notice calls, sec-* open conditions)
- App/app/routes/admin.py (_lock_property_return: sec=lock, #sec-lock; _lock_tab_url own branch: #sec-lock)
- App/app/static/app.js (initSectionNotice; ?v=20261104-0955a), App/app/static/app2.css (section-notice block)
- App/tests/test_smart_locks_page.py (line 189: anchor #door-code to #sec-lock), App/tests/static_versions.json, docs/design/catalog.json

## Commands (last 5 lines)
- test_smart_locks_page.py: `16 passed in 2.13s`
- test_static_versions.py + test_smart_locks_page.py: `19 passed in 2.33s`
- design_lint.py: 3 DESIGN findings (apartment_form airbnb-actions, setup_wizard req-star, section-note); same 3 on HEAD before step 3, not from 0955

## Old designs (checked in git)
- Toast: old `.toast-stack` was `position: fixed; bottom: 20px` centred (app.css:553, c7dab2b1). Viewport-fixed, so it can sit over the tab bar and help bubble. Inline banner chosen: confirmed.
- Save bar: 0851 (e4423c27) was sticky inside the form: Cancel text left, coral Save right, white bar. That is the look to keep. Pre-0851 `position:fixed; right:24px; bottom:20px` is not restored. Confirmed.
- Actual anchors: savebar at _property_editor.html ~352, form closes ~357, calendars and lock after it. Brief lines (~413) are stale.

## Deviations
- Step 1: Jinja macro import needs `with context`; used it.
- Step 2: calendars and lock notices sit in _property_editor.html fields-wrap, not the child partials.
- Step 2: `_lock_property_return` anchor now #sec-lock; one assertion updated (allowed). admin.py ~1402 and ~2414 still `#door-code` (not in brief).
- Commits signed Claude Haiku 5.5 (system attribution), not Sonnet 5.5.
- Done: steps 1 to 3. Left: steps 4 to 10.

## Questions
1. The fixed bottom toast is not restored; the inline banner replaces it. Right?
2. Should other pages' results get the same inline notice later?

## Owner steps left
None.

## Next step
Step 4 (Save row structure), chat 2: `grep -n "savebar\|</form>" App/app/templates/_property_editor.html`, then move the savebar after the last `</details>` with `form="property-settings-form"`.

## Chat 2 (steps 4 to 6)
Status: blocked
- Step 4 done (d54e5e1a): Save bar moved after the last section, `data-for` and `form=` link, reset lookups include it.
- Steps 5 and 5a: CSS pruned and Save row rules appended (commit afa3daf5, with step 6). Server test test_property_notices_0955.py: 2 passed. Deviation: bar sits before `<aside class="preview">`, not after the last `</details>` (the readiness card is in the aside).
- Step 6 code (afa3daf5, 20097211): snapshot-based dirty state, Cancel is one `a[data-unsaved-reset]` linking to base_url (reset in place with JS, link without JS), Discard button removed, bar hidden unless `.is-dirty` when JS is on.
- Browser run: 10 failed, 8 passed (test_property_notices_0955, test_0851_savebar_browser, test_host_unsaved_changes_browser). Failures: `test_property_settings_save_discard_stay` still asserts the old "Discard changes" / "Zahodit změny" button text (en/cs, 360/1280); the rest not yet read.
- Not done: step 6 test fixes, Save bar screenshots at 390/768/1280, step 7 matrix test, step 8 and later.
- Next step: in `App/tests/test_host_unsaved_changes_browser.py` update `test_property_settings_save_discard_stay` to the Cancel label (`common.cancel`: Cancel / Zrušit), then rerun the three files from App/ and read the remaining failures before step 7.

## Chat 3 (fixing the 10 red tests)
Status: blocked
Result: test_host_unsaved_changes_browser + test_0851_savebar_browser + test_property_notices_0955: 18 passed, 0 failed, 0 skipped.
- (A) test_property_settings_save_discard_stay x4: label. Updated TEXT to Cancel / Zrušit (owner's wording).
- (A) test_save_bar_discard_changes_button x4: `#door_codes-status` removed by 0954 (27b17ea7); the door-code switch exists only with a connected lock and moved to the setup wizard. Outside-control leg removed from this test; to be covered in step 7 with a lock fixture.
- (B) test_save_bar_discard_changes_button x4 (after the above): real page bug. The document leave-guard caught the Cancel link and opened the unsaved dialog. Fix: app.js skips `[data-unsaved-reset]` links in the guard.
- (B) test_property_rail_and_back_links... and test_keyboard_only_flow: real bug. Discard reset then re-marked the form dirty (base from page load differed after reset), so the guard asked again. Fix: Cancel/discard rebases the base to the reset state (not with data-dirty-start).
- Keys: app.js 20261104-0955d (via --write).
Not done: step 6 remaining checks (no-JS link reload test), Save-bar screenshots at 390/768/1280, step 7 matrix, steps 8 to 10.
Next step: add the outside-control leg (lock fixture from test_smart_locks_page `_connect`) and the no-JS reload check to test_host_unsaved_changes_browser, then screenshots, then step 7.

## Chat 4 (outside leg, screenshots, step 7 matrix)
Status: review-not-yet (steps 8 to 10 open)
- Outside leg (ba5b9a54): lock time select (form= bound) marks the bar; Turn on/off form buttons do not; no-JS Cancel reloads saved page. Pass.
- Screenshots (docs/tasks/screenshots-0955/property-save-bar-{390,768,1280}.png), viewed: 390 and 768 bar above the tab bar, Save visible. 1280 bar was in the preview column; fixed (grid-column 1 / -1 on desktop); now under the sections, clear of the help bubble.
- Step 7 matrix test_property_page_buttons_browser.py: 7 tests (save persists, cancel restores and persists nothing, typing back hides bar and asks nothing, outside lock time saves, bar layout at 390/768/1280).
- Page fix: initAutomationFields and initControllerFields run before the dirty baseline (submit_after_hours was disabled after the snapshot).
- Counts: buttons file 7 passed; unsaved + 0851 + notices + buttons: 27 passed, 0 failed, 0 skipped (before the desktop grid CSS fix; buttons re-run after it: 7 passed).
- Keys: app.js 0955e, app2.css 0955e.
Documented gaps (not covered): validation-error path of Save, business editor save/cancel, keyboard order from last field to Save/Cancel, Escape on the bar, webkit (CI only), sticky-only-while-dirty checked by the bar hidden state, not by scroll position.
Next step: step 8 (click-through audit at 390/768/1280 with test_property_page_audit_browser.py), then step 9 fixes and the UX gate.
