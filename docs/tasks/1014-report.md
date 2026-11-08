# 1014 report

Status: review (partial; see Deviations)

## Files changed
- App/app/static/app2.css (steps 1-3, all inside the `@media (min-width:768px)` Wolt block)
- App/app/templates/base.html (cache key `20261108-1014b`)
- App/tests/static_versions.json (regenerated with `--write`)

## Tests (from App/, UBYHOST_REQUIRE_BROWSER=1 where browser)
- test_layout_lint_browser.py: 4 passed, 0 skipped
- test_0710_v2_mockup_match_browser.py: 183 passed, 0 skipped
- test_0833 + test_host_property_controls + test_property_navigation: 31 passed, 0 skipped
- test_static_versions.py: 3 passed

## Phone
Every added CSS line sits inside the min-width:768px block. The only removed line is the summary min-height rule, replaced by the 768 px rule. Phone rules unchanged.

## Screenshots (copied to /mnt/project-files/ux-shots/spacing/)
- property-editor-390.png, property-editor-768.png, property-editor-1280.png
- Visual review was coarse: the 390 and 768 full-page images are too tall to read at display size; the 1280 image shows the status cards and form column aligned, but I could not confirm the Leon bar width or label spacing from it. Not signed off.

## Defects
1. Accordion padding: fixed. Inset is on the dot (margin-left 16px) and chevron (margin-right 16px); summary box stays 12px 0 because test_0710 pins it.
2. Leon bar width/size: rule added, not visually confirmed.
3. Field rhythm: label 14px/600, margin 0 0 6px; inputs margin 0. Not visually confirmed.
4. Title typography: NOT fixed. test_0710 pins summary b to 16px/600 at 768 and 14px/700 at 1024, which conflicts with the brief's 16px/700.
5. Help icon: `.help-tip` margin-left 8px, vertical-align middle.
6. Pill buttons: white bg and 1px var(--line) border added. min-height 44px dropped because test_host_property_controls geometry requires equal heights.
7. Card widths: width:100% added; not visually confirmed.

## Deviations
- Brief said "property_detail.html" for Leon; that file does not exist. Leon bar markup is `.pv` with `a[data-leon-card]` in _property_editor.html.
- Step 1 fallback applied (inset moved to children). Title override dropped (see defect 4).
- Pill min-height dropped (geometry test).
- Cache key: `20261108-1014` failed the static test after a CSS change, so the key is `20261108-1014b`.
- Row gap for two-column grids not added (no grid class found).
- "Business & legal details" and "Check-in time" headings not resized (no class identified).

## Owner or orchestrator steps left
- Decide on defect 4 (test_0710 pins conflict with the brief).
- Confirm visually at 390/768/1280 before merge (UX gate).
- Push done by executor; PR 814 update is the orchestrator's.
