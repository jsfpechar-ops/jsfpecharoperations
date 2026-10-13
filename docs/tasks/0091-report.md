# 0091 report

Base: ab0a2f1 (main) plus merge of claude/quirky-lamport-9svmd1 (00e5c4e: 0087/0095 corrections, combined-staging plan). Status: review.

## What changed
- `App/app/static/host.css`: one `/* 0091 */` block. `.stays-view` is a named inline-size container (`stays-list`). Lane >= 900px: one grid row per stay under one header row, no per-cell labels (6 columns: Stay | Property with Source muted below | Guests | Reporting | Deadline | Actions); actions right-aligned, wrap inside their cell. Lane < 900px: compact card (dates + nights and status pill; property and source; guests and deadline; wrapping actions); below 600px actions share the full width. Cell labels are screen-reader text only. 44px tap targets at <= 720px, including the open row menu (panel lives in body).
- `reservations.html`: `.scroll-x` removed; Source is no longer its own column (it sits under the property, class `stay-col-source` kept, portal link kept).
- Lane cap: `.wrap.with-sidebar > * { max-width: 1080px }` (host.css:41) pre-existed and is shared by all host pages and the lane-alignment tests, so it is kept (lane 994 at 1280 expanded, 1078 at 1440+). Row mode needs 900px minimum.
- Row heights (EN, lane 994/1078): 66px typical at 1280 and 1440, 78px for one row that wraps a long name, 109px for Send rows in CS (Send + Copy wrap in the actions cell). Cards: about 150-153px at 760-1024 (44px buttons).
- Tests: `test_host_fit_browser.py` (new: EN/CS x 9 widths x sidebar states; no overflow; bounds; fonts; no overlaps; row mode iff lane >= 900 with lower-median row height <= 72 and max <= 125; card median <= 160 / 200 below 600px). `test_host_wide_geometry_browser.py` (two spots) and `test_host_stay_actions_browser.py`: actions may wrap onto distinct rows, never overlap or clip; nothing removed or skipped.
- Screenshot writes in `test_host_stay_actions_browser.py` are gated by `UBYHOST_CAPTURE_0041=1`.
- Original defect: at 1280 expanded, Copy/More were clipped by the panel (table chosen by viewport, lane about 996).

## Baseline failures (6)
| Test | Now | Cause |
|---|---|---|
| wide_geometry::test_host_wide_lanes_align | pass | actions clipped at 1280 (layout) |
| wide_geometry::test_stay_row_actions_fit_midwidth_lanes | pass | layout |
| wide_geometry::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned | pass | layout |
| stay_actions::test_stays_guest_link_copy_is_status_independent_and_token_guarded | pass | layout (Copy beyond lane) |
| feedback::test_host_copy_feedback_truth_and_geometry | pass | failed on onboarding meter overflow at 360 (401px); fixed by the merged 0087/0095 work, not by 0091 |
| quiet_dashboard::test_dashboard_geometry_locales_and_screenshots | FAIL | see below |

Dashboard test, three separate causes, outside my files:
1. At 360 the test clicks More on a row below the fold. Playwright scrolls, and app.js `window.addEventListener("scroll", closeAll, true)` (app.js:518) closes the just-opened menu. Proposed test fix: `more_action.scroll_into_view_if_needed(); page.wait_for_timeout(150)` before the click (line ~214). Tried locally, then reverted.
2. Menu items were 39.7px high at <= 390px: fixed here in host.css (0091 block).
3. After 1 and 2, line 254 (`activeElement !== document.body`) fails after Tab from the last menu item: focusOutsideMenu in app.js finds no next focusable after the last dashboard row. Needs an app.js decision (return focus to the trigger when nothing follows) or a test change. dashboard.html and app.js are outside section 3.

## Tests run (from App)
- wide_geometry: 6 passed. stay_actions, fit, feedback, controls, filter_panels, geometry, redesign: 22 passed. 0 skipped. Dashboard test fails as above.
- Not run: whole suite and coverage gate (instructed).

## Audit (read-only; evidence = existing wide-geometry matrix, EN/CS, 360/390/760/1024-2048, no-overflow and no-obstruction assertions passing)
| Family | Result |
|---|---|
| Dashboard | Rows fit at all widths. Menu items under 44px at <=390 fixed (shared CSS). Test issues above |
| Properties list/detail/create | No overflow in matrix; edits belong to other briefs |
| Stays / detail | Stays fixed here; detail already correct in matrix |
| Reports/register (housebook) | Intentional wide record kept; no accidental overflow |
| Invoices list/create/detail, settings | Pass matrix; unchanged |
| Fees list/detail/setup | Pass matrix |
| Account settings, guest-link/automation hubs, locks, first-login, calendar add/error | Not executable here (no seeded fixture in these tests) |

## Evidence
`docs/tasks/0091-evidence/`: stays-{360,390,760,1024,1280,1440,1920}-{en,cs}-{expanded,collapsed}.png (collapsed only where the toggle exists) and measurements.json. Synthetic data.

## Owner steps
1. Review the branch diff.
2. Decide on the dashboard test fix and the Tab-out focus fix above.
3. Check Stays on staging at your sidebar widths.
