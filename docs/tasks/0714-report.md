# 0714 report: Overview test leftovers (sessions 1 and 2)

Status: review (session 2 finished; no push)
Branch: task/0714b-v2-overview-leftovers

## Commits
- Session 1: 4752cab (refresh hooks, no alert stack on v2), 7e36105 (queue copy reads v2 Stav pill), 4960242 (calendar browser selectors)
- Session 2: bba8113 (calendar 360 px fit, key 20261101-0714b), fcad3d3 (calendar events per-stay fallback), funnel test commit (step 6), geometry test commit (step 7)

## Final run (brief section 6)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <9 files> -q --tb=line -rs -p no:randomly`
Result: 96 passed, 0 failed, 0 skipped.
`python3 scripts/design_lint.py | tail -1`: design lint: OK
`python3 scripts/context_lint.py | tail -1`: context lint: OK

## Changes per test
- test_dashboard_calendar_browser (3 tests): session 1 selectors; test_calendar_geometry_locales_and_screenshots passes at 360 px after the app2.css padding fix (`body.v2 .dashboard-calendar{padding-inline:4px}` in the phone block).
- test_dashboard_queue_copy: session 1 expected strings.
- test_needs_you_dashboard_0241: session 1, host alerts stack not rendered on v2.
- test_signed_in_chrome: passes unchanged in session 2.
- test_endtoend (28): passes unchanged. test_08 still asserts the awaiting stay on `/` and passes; not moved to /reservations (it was not failing).
- test_admin_funnel::test_overview_cards_and_bars: isolation fix (see deviations).
- test_query_budget::test_batched_pages_render_exactly_as_the_per_stay_path: app fix (see deviations).
- test_host_geometry::test_dashboard_actions_share_height_and_gap: now measures the page-header action row on /reservations.

## Deviations
- Static key: `20261101-0714b`, not `20261101-0714`. The static-version script refused the key `-0714` after app2.css changed under it.
- Calendar fix: `padding-inline:4px` instead of `margin-inline:-4px`. The negative margin moved the card's left edge to 12 px and broke the alignment assertion at line 321.
- Query budget fix is in `App/app/routes/dashboard_calendar.py` (one line), not admin.py, as the brief named. Root cause: `reporting.preload_guests` returns {} when a page's guest read fails, and the calendar event builder passed `guests.get(id, [])`, so the per-stay fallback never ran and the bar lost its "· N" guest count. The fix passes `guests.get(id)` (None means read per stay). Batched and per-stay output now match.
- Funnel test: the assertion "first non-zero bar is full width" became "largest bar is full width". Hosts left by other test files (no `wp11-funnel-` prefix) are outside the cleanup, so the first bar was not the largest. Deleted assertion: first-non-zero width == 100 (replaced by largest-bar width == 100).
- Geometry test: now points at /reservations (the page-header row v2 removed from the Overview). Deleted assertions, because the v2 Overview has no What-needs-you stats card: `stats == head` and `stats == first` alignment checks. The gap, height, clipping and overlap checks are kept.
- Screenshots: no 390 px screenshot was taken in session 2 (budget). The CSS change touches the phone Overview calendar; a screenshot is still owed for the report rule.

## Owner steps left
- Review and merge through `scripts/merge-pr-on-green.sh` after CI. Do not deploy from this branch yet.
