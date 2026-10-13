# 0079 report

Start 34bffcb. Status: review. Dashboard Quiet overview, counts, 30-day window, five-row cap and filter semantics are untouched.

## What changed
- `reservations.html`: every Stay row gets a visible **Open** button (same label key as the dashboard) next to **More**, wrapped in `.row-action-pair` so More never separates from Open. The duplicate "Open stay" menu item is removed (key left in host_i18n, unused).
- `host.css` `/* 0079 */` block (end of file): shared Open height/min-width (94px) and square action-height More trigger on dashboard and Stays (replaces the 34px/42px mismatch). Stays row grid: actions column 332px at lane 900-1039, 430px at lane >= 1040 (keeps Send + Copy + Open + More on one line in EN and CS); lane < 600: Copy, Open, More share one line, Send takes its own line above.
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
