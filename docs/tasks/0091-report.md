# 0091 report

Base: ab0a2f1 (main) plus merge of claude/quirky-lamport-9svmd1 (00e5c4e: 0087/0095 corrections, combined-staging plan). Status: review.

## What changed
- `App/app/static/host.css`: one `/* 0091 */` block. `.stays-view` is a named inline-size container (`stays-list`); labelled cards at lane <= 1100px (2 columns, 1 column <= 600px); row actions wrap as whole controls (Send, Copy, More), no nowrap or percentage widths, More is fixed-size, Copy has natural width and its label may wrap; tap targets 44px at <= 720px. Open row-menu items get min-height 44px at <= 720px (the panel is moved to body, so the rule is unscoped).
- `reservations.html`: `.scroll-x` removed from the stays panel (no sideways scroll, no clipping).
- Tests: `test_host_fit_browser.py` (new: EN/CS x 9 widths x sidebar expanded/collapsed; lane scrollWidth, cell/action bounds inside lane, font >= 11px, no action overlaps, cards iff lane <= 1100). `test_host_wide_geometry_browser.py` and `test_host_stay_actions_browser.py` updated: actions may wrap (same row or distinct rows, never overlapping or clipped; heights still checked). No assertion was removed or skipped.
- Extra item: screenshot writes in `test_host_stay_actions_browser.py` (generated_images/0041-evidence) are now gated by `UBYHOST_CAPTURE_0041=1`.
- Finding: the host lane is capped at 1080px (host.css:41), so stays are cards at every desktop width today; the table only returns if the lane exceeds 1100px.
- Original defect reproduced: at 1280 expanded, Copy/More ended at x=1257/1301 while the panel ended at 1246 (clipped), because the table was chosen by viewport (>=1101) but the lane was about 996.

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
- stay_actions, wide_geometry, fit, feedback, controls browsers: 10 passed, 0 skipped.
- Also passed: test_host_filter_panels_browser, test_host_geometry, test_host_redesign (29 passed, 1 failed = dashboard above).
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
