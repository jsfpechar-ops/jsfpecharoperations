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
