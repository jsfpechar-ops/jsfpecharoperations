# 0543: Cleaning page in the shared v2 mockup test (320 to 1440 px)
Status: todo
Depends on: 0542 (same branch) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
`/cleaning` passes the shared mockup-match and geometry tests (`App/tests/test_0710_v2_mockup_match_browser.py`) at 320, 390, 768, 1024, 1280 and 1440 px against the mockup view `clean`, and side-by-side screenshots exist for the owner.

## 2. Context
- `App/tests/v2_mockup.py`: `PAGES` list (one entry per page: `name`, `path`, `view`, `selectors`, `missing_ok`), `WIDTHS`, `STYLE_PROPS`, `COLOR_OVERRIDES`. The test compares the computed styles of the first visible match of each selector in the app and in `docs/design/mockup/ubyhost-redesign-v2.html` (view shown with `show_view`), and runs `geometry_findings` (no sideways scroll, nothing overflowing a card, no overlapping text, tap targets, one h1, menus on screen).
- The test logs in with the `dashboard_rich_host` fixture from `App/tests/test_host_quiet_dashboard_browser.py`.
- Mockup `clean` view: lines 204-215 of the mockup (`.head h1`, `.head .sub`, `.head .btn`, `main h2`, `.card`, `table th`, `table td`, `.pill`).
- Page markup: `App/app/templates/cleaning.html`, `_cleaning_table.html`; page CSS: the `/* cleaning (0542) */` block at the end of `App/app/static/app2.css`.
- Known failures that are NOT this brief's (they fail before 0542 too, on the Overview branch): 13 tests in `test_dashboard_calendar_browser.py`, `test_host_language.py::test_the_setup_steps_a_new_czech_host_reads_are_czech`, and Overview (`/`) cases in `test_0252_touch_sweep_browser.py`, `test_design_guardrails_browser.py` and the `overview-*` cases of `test_0710`. Ignore them.

## 3. Files
Edit `App/tests/v2_mockup.py` (one new `PAGES` entry only), `App/tests/test_host_quiet_dashboard_browser.py` (only if step 2 needs cleanings in `dashboard_rich_host`), `App/app/templates/cleaning.html`, `App/app/templates/_cleaning_table.html`, the cleaning block of `App/app/static/app2.css` (+ its `?v=` key in `base.html` and `tests/static_versions.json` via `--write`). Screenshots in `docs/tasks/screenshots-0543/`. Report `docs/tasks/0543-report.md`.

## 4. Steps
1. **PAGES entry.** Add `{"name": "cleaning", "path": "/cleaning", "view": "clean", "selectors": [".side .nav.on", ".head h1", ".head .sub", ".head .btn", "main h2", "main .card", "main table th", "main table td", "main .pill"], "missing_ok": {}}`. Commit `0543 step 1`.
2. **Data.** Run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k cleaning -q --tb=short 2>&1 | tail -40` (without that variable it skips silently). If `main table td` or `main .pill` are "missing in app" because the host has no cleanings, add to `dashboard_rich_host`, after its stays are created, one manual cleaning dated today and one in 3 days with `cleaning.create_event(...)` (find the real helper and its arguments with `grep -n '^def ' App/app/cleaning.py`), then confirm `-k overview` results did not change. Commit `0543 step 2`.
3. **Fix differences.** For each style difference, change the cleaning markup or the cleaning block in `app2.css` so the app matches the mockup (the mockup is right; `COLOR_OVERRIDES` already maps the two accessibility colours). For each geometry finding, fix it in the same files. Do not change shared rules above the cleaning block in `app2.css`, the mockup, or `v2_mockup.py` helpers; if a fix needs one, stop and report. Rerun `-k cleaning` until all 12 cleaning cases pass. Commit `0543 step 3` (more commits are fine).
4. **Screenshots.** Take full-page screenshots of `/cleaning?lang=cs` and of the mockup view `clean` at all six widths into `docs/tasks/screenshots-0543/` as `cleaning-<w>.png` and `mockup-clean-<w>.png` (copy `test_v2_screenshots` from `test_0710` into a throwaway script under `/tmp`, not into the repo). Commit `0543 step 4`.

## 5. Do not touch
Other pages, `dashboard.html`, `_shell_v2.html`, shared `app2.css` rules, the mockup file, the cleaner's shared view, JS, routes. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k cleaning -q --tb=short -rs 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_cleaning.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -20`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
All 12 `cleaning-*` cases pass, the second set passes, 0 skipped, lint OK, 12 screenshots exist.

## 8. Stop and ask
Stop if a fix needs a shared rule, the mockup, or a file outside section 3, or if a cleaning case cannot pass because the mockup's phone layout conflicts with the page (report the exact finding).

## 9. Report
`docs/tasks/0543-report.md`: Status, test and lint tails, every style difference found and how it was fixed, screenshot paths, deviations.
