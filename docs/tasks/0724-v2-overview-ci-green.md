# 0724: Overview phone spacing done right, CI green
Status: todo
Depends on: 0723 | Branch: task/0723-v2-overview-polish (worktree /tmp/wt0723, continue there)
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Phone Overview (390 px) spacing matches the phone mockup (`docs/design/mockup/ubyhost-phone-v1.html`, `data-s="dnes"`) without negative margins, and every CI failure on 15df9de is fixed.

## 2. Context and decisions (orchestrator, 19:40)
- Spacing (390 screenshot, docs/tasks/screenshots-0723/overview-390.png): card to card about 26 px, "Show 3 more" to "Today" about 70 px, "Today" heading to the first `.hs` card about 40 px. Cause: `.ui-body:has(> .ov-month)` is a flex column, so child margins add up instead of collapsing; 0723 papered over one gap with `.ov-head{margin-bottom:-22px}`.
- Decision: below 1024 px the vertical rhythm comes from ONE source. Remove the 0723 negative margin. Give the Overview column `gap:0` and let the mockup's own margins do the work (mockup: read `h2.sec` margin, `.card.need` margin, `.hs` margin in the phone mockup CSS and copy them), OR use flex `gap` with all child vertical margins 0. Pick whichever keeps `test_0710_v2_mockup_match_browser` green without overrides; if the only way is an override, add one SELECTOR_OVERRIDES entry in `App/tests/v2_mockup.py` with the reason "spacing comes from the column gap" (allowed).
- Target at 390: date line to "What needs you" heading 20-28 px, card to card 12 px (or the mockup's value), "Show N more" to "Today" 24-28 px, "Today" heading to first card 12-16 px (mockup values win if different). Measure with page.evaluate (each child's top/bottom/margins), before and after; put both in the report.
- CI fixes (test changes only unless stated):
  - G. `App/tests/test_0201_tabbar_safe_area_browser.py` ~line 49: on v2 pages the phone tab bar is `.tabs`, not `.ui-tabbar`. Query `.ui-tabbar, body.v2 .tabs` (the visible one); keep every assertion. If `.tabs` fails a real assertion (bottom flush with innerHeight, safe-area padding), fix app2.css (`--tabbar-safe` exists), not the test.
  - H. `App/tests/test_host_quiet_dashboard_browser.py` ~358-366: phone cap is 2. cap = 2 if width < 1024 else 4; check the visible card count (offsetParent) == min(total, cap) and `str(total - cap)` in the summary text.
  - I. `App/tests/v2_mockup.py`: `.hs .pill` width app=143 vs mockup=139.9 at 320/390 (CI fonts). Pill width follows its label text: add a BOX_OVERRIDES entry for `.hs .pill` width, reason "width follows the status label text".
  - J. `App/tests/test_motion_browser.py` line ~71: `details.ui-how` is null on `/` because v2 uses `details.ov-how` / `[data-how]`. Point the test at the v2 fold-out (`details.ui-how, details[data-how]`). If the fold-out does not animate, add it to the "v2 shared: motion" block in app2.css rather than weakening the test.
  - K. `App/tests/test_dashboard_calendar_browser.py:354`: `.cal-day-number` width 43 vs >= 43.9 at phone widths. Find out whether the v2 main padding (20 px) shrank the calendar; if so, fix the calendar cell sizing in app2.css (phone only) so the number box keeps its old size, otherwise explain in the report and stop on this item.
- Bump app2.css key to `20261101-0724` and `--write` the manifest.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `App/tests/v2_mockup.py`, the five test files above, screenshots `docs/tasks/screenshots-0724/` (overview 390, 768, 1280), report `docs/tasks/0724-report.md`.

## 4. Do not touch
`app.js`, routes, other pages' templates, `dashboard.html` unless a wrapper class is needed for the spacing.

## 5. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0201_tabbar_safe_area_browser.py -k chromium tests/test_host_quiet_dashboard_browser.py tests/test_motion_browser.py tests/test_dashboard_calendar_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_needs_you_0240.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -20` (WebKit is not installed locally; WebKit-only skips/failures are fine, say so). Ruff CI subset. Repo root: design_lint and context_lint.

## 6. Acceptance
No negative margins; 390 gaps within the targets; listed tests pass.

## 7. Report
`docs/tasks/0724-report.md`: gaps before/after in px, each item's change, test tails.
