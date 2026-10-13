# 0079 report

Start 34bffcb. Status: review. Dashboard Quiet overview, counts, 30-day window, five-row cap and filter semantics are untouched.

## What changed
- `reservations.html`: every Stay row gets a visible **Open** button (same label key as the dashboard) next to **More**, wrapped in `.row-action-pair` so More never separates from Open. The duplicate "Open stay" menu item is removed (key left in host_i18n, unused).
- `host.css` `/* 0079 */` block (end of file): compact Open (content width, 12px padding) and square action-height More trigger on dashboard and Stays (replaces the 34px/42px mismatch). Stays at lane >= 900 is one subgrid (shared tracks, one continuous header band); Reporting and Deadline tracks are max-content with nowrap pills and deadlines, actions track `minmax(300px, max-content)`; lane < 600: Copy, Open, More share one line, Send takes its own line above.
- `app.js` (menu functions only): a scroll within 400ms of opening a row menu repositions it instead of closing it; Tab out of the menu moves to the next focusable, or keeps focus on the trigger when nothing follows (never drops to body).
- `test_host_quiet_dashboard_browser.py`: unconditional `generated_images/0041-evidence` write gated by `UBYHOST_CAPTURE_0041=1`. No assertion changed.
- New `test_host_list_layouts_browser.py`: dashboard and Stays, EN/CS, 360-1440: same Open/More height, More square and adjacent, no clip, no page overflow.
- Screenshots (`UBYHOST_CAPTURE_0079=1`): `docs/tasks/0079-evidence/{dashboard,stays}-{360,390,1280,1440}-{en,cs}.png`, synthetic data.

## Baseline
`test_dashboard_geometry_locales_and_screenshots` now passes (scroll-closes-menu and Tab-focus-loss both fixed in the app).

## Tests
Focused browser set (dashboard, fit, wide geometry, stay actions, feedback, list layouts): all pass, 0 skipped. 78 other dashboard or /reservations tests: pass (test_overhaul click-target test updated: it asserted no visible Open). In one combined run, test_endtoend and test_admin_funnel failed from cross-test state; both pass alone.

## Deviations / risks
- Stays rows with Send wrap onto a second line in a narrow row lane (about 109px), as before.
- Not captured: widths 1680-2048 beyond the existing fit/wide-geometry matrices.

- Polish pass: where the lane cannot hold Send + Copy + Open + More (rows with Send; CS at 1280 expanded) the actions wrap; the new test exempts those rows from the 72px limit.
