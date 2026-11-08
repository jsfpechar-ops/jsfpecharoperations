# 1008 report (executor: Haiku 5.5)

Status: blocked

## Changes since the first commit (coordinator decision: 720 px cap only at >=1024 px)
- app2.css: the 720 px cap and centring moved into `@media (min-width:1024px)`, for `.form.prop-form-single` and the `.property-detail` rule. The strip cap `.prop-strip` 720 px is in the same media query.
- app2.css: `.field > label` and `.field-label-row > label` rules skip checkbox labels (`:not(:has(input[type=checkbox]))`), to fix the OCR checkbox geometry at 390.
- app2.css: label and `.field-label-row` bottom margin 4px to 8px. This did not clear the layout-lint findings.
- base.html: app2.css v=20261108-1011. static_versions.json regenerated.

## Results
- design_lint: OK.
- Browser group 2: test_0948 now passes. The rest of the group passes except the item below.
- Browser group 3 (test_host_geometry, test_host_wide_geometry_browser, test_design_guardrails_browser): 23 passed, 0 skipped.
- test_host_property_controls_browser: 9 passed, 1 failed: test_0984_calendar_rows_keep_state_and_actions_with_a_long_url at 1280. The `.feed-table` inside `.scroll-x` overflows by 55 px, because the 720 px column at 1280 is narrower than the long feed URL row. Not fixed (the cap is the coordinator's decision).
- Layout lint: FAILS, 45 `tight-stack` findings at 320 px on `div.field-label-row` and `label` "IDUB ? The police number of" (fee-setup, property-detail, property-detail-configured, open). Not fixed after one round (margin 4 to 8 px). Also a button "See an example police..." (police-sample-link) at 320 px is flagged.
- Earlier run of the guest checkbox test (OCR checkbox geometry at 390) now passes.

## Screenshots
- Copied to /mnt/project-files/ux-shots/wolt/property-editor-390.png, property-editor-768.png, property-editor-1280.png (layout-lint property-detail-configured+open shots, after the margin change).
- I viewed the 390 image only. It is downsampled by the viewer, so I could not check detail. Seen: one column of cards with a thin border, a single column at the top of the page, Archive card near the bottom, no horizontal scroll visible. 768 and 1280 were not viewed.

## Owner / coordinator decisions needed
1. Layout-lint tight-stack at 320 px: the police label/row needs a larger gap or the `.field-label-row` wrap changed (a fix round is needed).
2. The 720 px cap at 1280 makes the calendar feed table overflow by 55 px: raise the cap (about 776 px) or let the table scroll inside the card.

## Commit
Local commit only, no push, no PR.
