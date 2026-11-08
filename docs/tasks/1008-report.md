# 1008 report (executor: Haiku 5.5)

Status: blocked

## Final CSS (commit 3)
- Removed the two `.field > label` / `.field-label-row` rules that 1008 added. Label styling is back to main.
- Desktop-only (min-width:1024px) cap raised to 776 px for `.form.prop-form-single`, `.property-detail`, and `.prop-strip`.
- base.html app2.css v=20261108-1013; static_versions.json regenerated; design_lint OK.

## Results
- Layout lint (test_layout_lint_browser.py): 4 passed, 0 skipped. The 320 px tight-stack findings are gone with the label rules removed. No revert needed; the 1007 comparison was not run.
- test_0948 and test_0984 (1280 feed table): pass with the 776 px cap.
- Browser group 2: 63 passed, 1 failed: test_host_property_controls_browser.py line 443 (`#calendar-add #label` is_visible, `#calendar-connect` hash, lang=cs). It passed in some earlier runs and failed in others, so it may be flaky or tied to the cs label. Not diagnosed (budget).
- Group 3 (earlier run, before the final CSS): 23 passed.
- Screenshots copied: /mnt/project-files/ux-shots/wolt/property-editor-390.png, -768.png, -1280.png. Not viewed in this session (budget); only the earlier 390 shot was looked at, and it was downsampled.

## Owner / coordinator next step
- Look at line 443 of test_host_property_controls_browser.py (cs, calendar label) before this can go to review.
- Group 3 and the screenshots need one final look with the 776 px CSS.

## Commit
Local commit only. Nothing pushed.

## Note: browser shard 2 flake (test_calendar_platform_controls_in_browser)

- Root cause (not CSS): `#label` sits inside `details#sec-calendars.prop-sec`, which is closed by default. `app.js` `initPage` is bound to `turbo:load` when Turbo is loaded, and that event fires after the `load` event that `page.goto` waits for. The handler opens `#sec-calendars` and removes `is-collapsed`. The test calls `is_visible()` with no wait, so on a slow runner it can run first (CI run 42434064573, shard 2, line 443, `cs`).
- Local check: the 1008 CSS rules do not hide the field. Computed display, visibility, opacity and height were visible at 360, 390 and 1280 in both languages. The real test file passed 3 times locally.
- Fix options (not applied here, need a decision): (a) run `initPage` on `DOMContentLoaded` for the first load, or (b) have the test wait for `#label` to be visible. Option (b) edits a test, so it needs the owner's approval.
