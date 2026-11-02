# 0714: last Overview test failures after the v2 rebuild
Status: todo
Depends on: 0711, 0712 | Base commit: claude/project-thread-50hyv5 (cb3671c) | Branch: task/0714-v2-overview-leftovers
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Make the remaining Overview-related tests pass. Most need a test update to the v2 markup; a few need a small app change listed below. Read `docs/tasks/0708-report.md` ("Session 2" list) first.

## 2. Context and decisions (orchestrator, 2026-11-01)
- The v2 Overview (`App/app/templates/dashboard.html`) shows: `.head`, `.todo` cards ("Potřebuje vás", they keep `data-needs-you*` attributes), the `.quiet` month line, the server-side 14-day `.cal` grid, and the "Dnes" table (only stays arriving or departing today). The old JS calendar shows only with any `cal_*` query parameter.
- `test_dashboard_calendar_browser.py`: 3 tests (`test_calendar_geometry_locales_and_screenshots`, `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place`, `test_dashboard_committed_stay_refresh_retry_does_not_post_twice`). After a stay is created from the calendar, `app.js` refreshes parts of `/` in place via `data-dashboard-refresh` hooks. Read how `app.js` finds and swaps them (`grep -n "dashboard-refresh" App/app/static/app.js`). App change allowed: put the same `data-dashboard-refresh="..."` attributes on the matching v2 sections in dashboard.html (todo section, Dnes table) so the refresh still works. Then update the tests' selectors from old classes (`.needs-you-item`, stay lines) to the v2 ones (`.todo .card[data-needs-you-stay]`, `tr.dashboard-row[data-stay-id]`). For the geometry test, open the page with `?cal_view=calendar` if it measures the old calendar.
- `test_dashboard_queue_copy.py` (3 failures: "All guests reported", "Reported"): the Dnes Stav cell now shows a `pill p-ok` with the reported status text. Update the expected strings to what the v2 cell renders for each state; keep the intent (a reported stay says nothing is left to do).
- `test_needs_you_dashboard_0241.py`: the `_host_alerts.html` stack still renders on `/` and duplicates the alert card. App change allowed: do not render the host alerts stack on v2 pages (find where it is included; wrap with `{% if not v2 %}`), because the todo cards already show those alerts. Check no alert type is lost: every alert the stack shows must also produce a todo card (compare the two templates); if one would be lost, stop and report.
- `test_signed_in_chrome.py::test_dashboard_opens_with_the_what_needs_you_card`: update to the v2 todo heading/cards.
- `test_endtoend.py::test_08...`: it expects an awaiting stay on `/`; the v2 Overview lists only today's stays. Assert it on `/reservations` instead.
- `test_host_geometry.py::test_dashboard_actions_share_height_and_gap`: measure the v2 `.head` actions (the `.btn` and the quiet links) or, if it is about the old action row that v2 removed, point it at a non-v2 page that still has that row and note it.
- `test_admin_funnel.py::test_overview_cards_and_bars`: passes alone, fails after other tests. Find the leaked state (run it after `test_dashboard_queue_copy.py` and the other files from the 0708 list); fix the isolation in the test (cleanup or a unique fixture), not in the app.
- `test_query_budget.py::test_batched_pages_render_exactly_as_the_per_stay_path` fails with `['dashboard']`: the v2 dashboard renders differently in the batched and per-stay paths. Read the test to see what it compares, find which v2 value comes from a per-stay call that the batched path does not fill (likely `today_rows`, `month_summary` or `cal_rows` in `App/app/routes/admin.py`), and make both paths produce the same HTML. If the fix is more than ~15 lines in admin.py, stop and report.

## 3. Files
`App/app/templates/dashboard.html` (data hooks only), the template that includes `_host_alerts.html` (v2 guard only), `App/app/routes/admin.py` (batched-path fix only), the test files named above, report `docs/tasks/0714-report.md`.

## 4. Steps
Work file by file, run only that file (`-q --tb=line | tail -15`, with `UBYHOST_REQUIRE_BROWSER=1` for browser files), commit every 2-3 files with explicit paths.

## 5. Do not touch
`App/app/static/*` (brief 0713 is changing app2.css in parallel), `v2_mockup.py`, `app.js`.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
Final: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py tests/test_dashboard_queue_copy.py tests/test_needs_you_dashboard_0241.py tests/test_signed_in_chrome.py tests/test_endtoend.py tests/test_host_geometry.py tests/test_admin_funnel.py tests/test_query_budget.py tests/test_dashboard_order.py -q --tb=line -rs -p no:randomly 2>&1 | tail -40` (0 skipped). Repo root: `python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass, 0 skipped. No skips, xfails or deleted tests; any deleted assertion is named in the report with its reason.

## 8. Stop and ask
Stop on the alert-loss check or the 15-line limit above.

## 9. Report
`docs/tasks/0714-report.md`: status, test tails, change per test, deleted assertions, deviations.
