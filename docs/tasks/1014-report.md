# 1014 report

Status: review

## Round 2 (1014b, after Josef's laptop screenshots of 2026-11-08)

All CSS sits inside the `@media (min-width:768px)` Wolt block in `App/app/static/app2.css`. Cache key is `20261108-1014e`, and `static_versions.json` was regenerated.

- Section titles: the summary is now `padding:14px 16px`. The title is 16px/700 and sits 16 px in from the card edge, the same inset as the fields. Round 1 put the inset on the first child, which is the dot, and the dot is hidden from 1024 px up, so the title stayed flush.
- One column: `.prop-after-strip` (Continue setup card and Leon bar) gets `max-width:776px` from 1024 px, like the status strip. The strip, setup card, Leon bar, form and sections all measure left 362 / width 776 at 1280, and 20 / 728 at 768. The Leon bar gets the same white tile as the setup card: `--line` border, 14px radius, 12px padding.
- Field rhythm: round 1's `input{margin:0}` lost to `body.v2 .prop-sec :is(input…)`, so inputs still had a 12px bottom margin. I raised its specificity. The section and its grids now own one 16 px gap, and `.field`, `.grid`, `.hint` and `.field-label-row` children add no margin. From 768 to 1023 px the section and its grids become grids so the same 16 px gap applies there. Every gap is now 16 px: label to input 6 px, field to field 16 px.
- "Business & legal details" link is 14px/600, the same as the labels.
- "?" icons: the measured gap from label text to the tip box is 8 px everywhere.
- Pill buttons: white with a `--line` outline (from round 1), confirmed in the screenshots.
- test_0710: added `WIDE_OVERRIDES` in `App/tests/v2_mockup.py`, applied only at width >= 768 in `test_0710_v2_mockup_match_browser.py`, with the comment `owner decision 2026-11-08 (Josef's laptop screenshots): section titles need an inset`. It covers `property:.prop-sec > summary` padding 14/16 and `.prop-sec summary b` weight 700. I also added a `property:summary b` 16px/700 override, which only desktop specs use. Phone (<768) expectations are untouched.

## Tests (from App/, UBYHOST_REQUIRE_BROWSER=1, 0 skipped)
- test_layout_lint_browser.py: 4 passed. No `double-primary` on cleaning@1024.
- test_0710_v2_mockup_match_browser.py: 183 passed
- test_0833 + test_host_property_controls + test_property_navigation: 31 passed
- test_static_versions.py: 3 passed

## Phone
The 390 px full-page render of the configured property editor (all sections open, Leon bar present) is pixel-identical before and after: PIL `ImageChops.difference(...).getbbox()` is `None`.

## Screenshots
`/mnt/project-files/ux-shots/spacing2/`: property-editor-1280-top.png, -1280-police.png, -1280-full.png, -768-top.png, -768-police.png, -390-top.png.

## Left
- From 768 to 1023 px, the help "?" keeps its 44 px touch circle (existing tablet rule), so it looks larger than on a laptop.
- "Hide setup guide" (ui-btn-quiet) keeps its own 12 px button padding, so its text sits 12 px right of "Continue setup".
