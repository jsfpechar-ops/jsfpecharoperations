# 0527 report: stays list v2, tests and screenshots

Status: blocked

Done: step 0 (commit bf1cef19); step 1 (commit 5d7eb9eb, stays PAGES entry plus fixes). Left: step 2 (old tests, 18 failed and 25 errors, not started), step 3 (screenshots, not started).

## Step 1 changes
- Template: phone `.big` is now `<h1 class="big">` (one visible h1 at every width; the desktop h1 is hidden below 1024).
- Template: `stays-filter` on the filter form, `stays-panel` on the add-stay panel, `stays-pager` around pagination.
- app2.css: page-level tap sizes (44 px below 1024, 36 px from 1024) for filter controls, add-panel controls and pagination; `.stays-desk .stay-identity-link` min-height 44 below 1024, 24 from 1024; input look (1px #dcdcd7, radius 8px, padding 9px 10px).
- PAGES: desktop uses `.chip` (the mockup has `.tools .chip`, not `.chips .chip`); pill checks use `.pill.p-ok` / `.pill.p-warn`; `main .pill.p-ok` and `.row .pill.p-ok` are in `missing_ok` (tone depends on data, same as overview).
- Key `20261101-0527b`, manifest written (41 files).

## Step 1 result
`pytest tests/test_0710_v2_mockup_match_browser.py -k stays -q --tb=line -rs`: 3 failed, 9 passed, 0 skipped. All geometry checks pass at 320-1440. Failing: style at 320, 390 and 768.

## Remaining mismatches
- Waiting on shell (Overview thread): phone `.top .round` font-size, colour and padding; `.chip.on` background and border (app2.css line 56, global `!important` in red); `.head h1` 32 px and `.head .btn` radius/weight at 768 (0718 phone rules below 1024).
- Waiting on owner or copy: chip width (173 vs 123 px) and pill width at 320/390 (the app labels are longer than the mockup copy); `.list .row` border colour and height 101 vs 103 px; `.row .t` width 188/258 vs 180/250 px (row children, not checked further).
- Tablet 768 decision for owner: the test compares 768 with the desktop mockup, but the table at 768 overlaps text ("Guests" and "Direct booking" cells). The page keeps the phone list below 1024 (0526 design). Choose: hide columns at 768-1023 (markup change) or accept that 768 is compared with the phone layout (test change, not done).

## Step 2 note (not started)
`tests/test_host_list_page_layout_browser.py`, `tests/test_host_filter_panels_browser.py` and others use `page.locator("h1")`, which now matches the hidden desktop h1 and the phone h1 (strict mode error). Step 2 should use a visible-only locator.

## Commands
- Old tests (brief §6 list), last lines: `18 failed, 34 passed, 25 errors in 70.36s`. Examples: `test_host_list_page_layout_browser.py` ("no clickable row", `.stays-view` selectors removed by 0526); `test_host_filter_panels_browser.py:169` strict h1 violation; `:405` `[data-filter-toolbar]` not visible at 360 px.
- Lint, static versions: `test_static_versions.py --write` ran (41 files). Design and context lint not run in this session.

## Deviations
- Step 1: the brief said `.chips .chip` on desktop; that selector does not exist in the mockup, so `.chip` is used.
- Pagination uses page-level classes, not `.btn ghost sm` markup.

## Questions / owner
- Shell: approve the `.chip.on` !important change and `.head h1` / `.head .btn` below 1024 (Overview thread).
- Tablet 768: table or phone list (see above).
- Confirm copy length for chips and pills (owner).
- Steps 2 and 3 need a new session.
