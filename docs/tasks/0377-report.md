# 0377 report: smooth sidebar collapse

Owner allowed direct implementation ("implement it yourself", handoff 2026-10-25).

## Change

- `host2.css`: `body.sidebar-animating` transitions rail width/padding and page `margin-left` (260 ms, `--ease-standard`). Nav icons keep their x during the slide. The toggle icon turns 180° in the rail (desktop collapsed and the 1024-1279 tablet rail). Reduced motion: no transition.
- `app.js`: `animateRail()` sets `.sidebar-animating` for 280 ms, only from a click, Escape or outside tap. Stored collapse on load and breakpoint crossings stay instant.
- `?v=` keys: `host2.css` and `app.js` now `20261025-0377`; `tests/static_versions.json` rewritten.

## Tests

- New in `test_host_wide_geometry_browser.py`: click slide at 1280/2000 (240↔64, margin, toggle inside rail, icon flipped, transitions running), restore + resize 2000→1280→1024→768→390→2000 never animates, tablet overlay slides without moving the page, reduced motion.
- `test_design_shell_browser.py`: waits for the slide to finish before measuring.
- Passed: `test_host_wide_geometry_browser.py`, `test_design_guardrails_browser.py`, `test_design_shell_browser.py`, `test_static_versions.py`, `test_0251_tablet_browser.py`, `test_shell_lane_browser.py`, `test_a11y_guard_browser.py`, `test_host_fit_browser.py`, `test_design_shell.py`, `test_host_ux_acceptance.py`, `test_0252_touch_sweep_browser.py`, `test_dashboard_rows_browser.py` (0 skipped, `UBYHOST_REQUIRE_BROWSER=1`).

## Screenshots

Project files `sidebar-animation-0376/`: dashboard 390 open; 1280 and 2000 open and collapsed; 1280 mid-slide; 1024 tablet overlay.
