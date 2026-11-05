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

## Chat 5 (gaps closed, step 8 audit)
Status: blocked
- Gaps closed (buttons file, 10 tests): validation (empty house number blocked by the browser, edits kept, bar stays, nothing persisted, Cancel restores and clears); Tab walk from the form reaches Cancel then Save; Escape keeps the edit and the page. Business editor: covered by test_business_editor_save_discard_stay (unsaved-leave asks), not repeated here.
- Audit (test_property_page_audit_browser.py, 3 widths): 1 passed (768), 2 failed (390, 1280). Findings:
  1. 390: focused #internal_name and #addr_obec sit under the sticky Save row. Fix added (focusin scrolls the field clear of the bar, app.js; scroll-padding in app2.css). Still failing: check the bar's position on phone.
  2. 1280: small targets 40 px: "Copy" x2 (guest link card), "Preview as a guest", "Open the guest guide", "Generate a new PIN". Min-height rule added to form buttons; these controls keep 40 px (their class sets height elsewhere). Still failing.
- Keys: app.js 0955f, app2.css 0955g.
- Next step: find the CSS that sets 40 px on .copy-btn and the guest-card buttons (grep -n "copy-btn{" app/static/app2.css), add min-height 44 with a higher-specificity selector, then check the phone bar position with a screenshot of audit-390-3-focus.png in the scratchpad. Then step 9 fixes and the UX gate.

## Chat 6 (audit green, UX gate part)
Status: blocked
- Audit test_property_page_audit_browser.py: 3 passed at 390/768/1280, 0 skipped. Thresholds from docs/design/design-system.md "Touch target" row: 44 px below 1024, 40 px at 1024 and up (the test comment cites it).
- Findings fixed: (1) 390: focused field under the sticky Save row. Causes: scroll-padding rule lost to the havel rule on specificity, and the tab bar height was undefined on html. Now html:has(...):has(.savebar) carries --savebar-h 72px and the tab bar 84px. (2) focus or first edit keeps the field clear of the bar (app.js keepClear on focusin and input). (3) 1280 targets: spec threshold 40 px, no change to desktop buttons.
- Buttons matrix: 10 passed, 0 skipped (save, cancel, typing back, outside lock time, layout at 3 widths, validation, Tab walk, Escape).
- Layout lint (test_layout_lint_browser.py): 4 passed, 0 skipped.
- context_lint: OK. Keys: app.js 0955g, app2.css 0955j.
- Viewed: audit-390-3-focus.png (postcode clear above the Save row, Save above the tab bar); property-save-bar-1280.png earlier.
- Webkit: untested locally (CI only): all new browser tests.
- Not done: step 10 (sticky Preview aside, 1024+, with its test; needs a property whose setup is unfinished), design-system checklist tick, the decision line in docs/context/decisions.md, the 390/768/1280 UX screenshots with per-width notes for the PR.
- Next step: step 10: write App/tests/test_property_preview_sticky_browser.py (1280 and 1440: scroll 1200, aside top 0-120, no overlap with the Save row, static below 1024) with a property whose setup is unfinished, then the design checklist, the decision line, and the PR.

## Chat 7 (final: step 10, UX gate, regression)
Status: review (pending owner merge decision; CI not yet run; webkit untested locally)
- Step 10: Preview aside sticky from 1024 px (the detail body is now the two-column grid; the aside is column 2). App/tests/test_property_preview_sticky_browser.py: 3 passed, 0 skipped (1280, 1440: aside top 0-120 after scrolling 1200, sticky; 768: static). An empty aside is not sticky (the grid rule needs the aside to exist).
- UX notes (viewed):
  - 390, dirty: Save row sits above the tab bar, Cancel left, Save right; the focused field stays above the row. Help bubble hidden on phone.
  - 768, dirty: same layout as phone; the tab bar is still shown below 1024 px; no sideways scroll.
  - 1280, dirty: Preview aside beside the sections, Save row under the main column, clear of the help bubble.
  - 1280, clean: no Save row (hidden until a field differs).
  - 390 and 768 clean were not viewed; the audit asserts the bar is hidden there.
- Regression (24 files, background): 245 passed, 3 failed. The 3 were stale expectations (Save bar hidden until dirty; savebar regex); fixed in tests 4ccddedb; re-run of the 3: 6 passed, 0 skipped.
- Checklist ticked where verified (design-system.md): one Save, no sideways scroll, layout lint, CS/EN keys (none added). Left open: header row, help "?" placement, 12 px spacing, CI watched.
- Decision line added (decisions.md); context lint OK.
- Next step for the owner: merge when CI is green; before merge, confirm the 0955 PR description carries these per-width notes.
