# 0133 report

Status: blocked (0133-fix-3 stopped at step 3, section 8)

## Commits (branch claude/project-thread-td6fpc, not pushed)

- 9074aac step 0: host2.css row-menu min-height moved into a 767px block (appended at end)
- ec927cc step 1: dashboard.html rewritten on host_page.html (detail kind); compiles
- 9398a67 step 2: catalog.json enforces dashboard.html, hooks added; design_lint OK
- f73b44c step 3: test_host_geometry.py uses .ui-ph-acts / .ui-btn / .ui-stats / .ui-ph; passes (2 passed)
- 1c49480 step 4: App/tests/test_design_dashboard.py created; its 3 tests pass

## Files changed

App/app/static/host2.css, App/app/templates/dashboard.html, docs/design/catalog.json, App/tests/test_host_geometry.py, App/tests/test_design_dashboard.py

## Commands

- design_lint: "design lint: OK"
- ruff (E9,F63,F7,F82,F401,F841): "All checks passed!"
- test_host_geometry.py: "2 passed, 1 warning"
- test_design_dashboard.py + test_signed_in_chrome.py (-x): stopped at test_dashboard_status_counts_use_distinct_colours, 15 passed before it
- test_signed_in_chrome + quiet dashboard + dashboard calendar browser (no -x): "7 failed, 22 passed"

## Failing (not fixed, outside the brief's scope)

- test_signed_in_chrome.py:216 and :~260 (status counts): assert 0 == 3. Old markup `<a class="dashboard-stat action|waiting|ready|overdue">` is gone; new markup is `ui-stat` with no colour kind or is-positive class.
- test_host_quiet_dashboard_browser.py:199 and :287: same stat-selector cause (assert 0 == 3).
- test_host_quiet_dashboard_browser.py:328 (header button count, step 0 item): not updated yet; the count and heights depend on the v2 header (.ui-btn, 44/40 px).
- test_host_quiet_dashboard_browser.py test_dashboard_rich_queue_colors...: Locator inner_text timeout 30 s.
- test_dashboard_calendar_browser.py: a `Cannot read properties of null (getBoundingClientRect)` in geometry test; a 30 s inner_text timeout in creation test; assert False at line 699 in the retry test. Likely selectors in the refresh/calendar hooks.

## Deviations

- Step 1: `t('dashboard.table.task')` was not in any app file, so I used `t('dashboard.stat.action')` (as the brief allows).
- Step 3: geometry height assertion 42 changed to 40 (v2 control height at 1280); aligned-block selectors `.dashboard-stats` and `.host-today-head` mapped to `.ui-stats` and `.ui-ph`.
- Step 4: dropped the `data-skeleton-kind` assertion (the attribute is not in host_page.html or base.html).

## Questions

1. The stat-count tests (test_signed_in_chrome.py, quiet dashboard) assert colour kinds (action/ready/overdue, is-positive) that the brief's markup no longer has. Should the stat tiles keep a semantic class (e.g. is-positive / kind) and the tests be updated, or should those tests be rewritten?
2. Should the dashboard calendar test failures be fixed in this brief, or handed to a follow-up?

## Owner steps left

None. Steps 5 and 6 (browser run, 0 skipped, 390/360/1280 screenshots, acceptance section 7) are not done.

## 0133-cont-1 run (Status: blocked)

Commits (not pushed): step 1 068aa1a, step 2 a23efe5, step 3 f062923, step 4 2199f32, step 5 9109830.
Lint: `design_lint.py` OK. Ruff E9,F63,F7,F82,F401,F841: All checks passed.

Browser run (step 6, `-rfEs`, UBYHOST_REQUIRE_BROWSER=1): 6 failed, 25 passed, 0 skipped. Failing:
- test_host_list_layouts_browser.py::test_stays_pills_and_deadlines_stay_on_one_line: expected (fixed in 0134). `AssertionError: ('en', 1280, {'pill': True, 'deadline': True, 'height': 85, 'name': 23, ...})`
- test_host_quiet_dashboard_browser.py::test_dashboard_geometry_locales_and_screenshots: `assert 'is-overdue' in (('ui-row dashboard-row clickable-row'))` at line 304.
- test_host_quiet_dashboard_browser.py::test_dashboard_rich_queue_colors_cap_and_interaction_screenshots: Locator.click timeout, `.dashboard-row[data-stay-id="1"] .row-menu-trigger` not visible.
- test_dashboard_calendar_browser.py::test_calendar_geometry_locales_and_screenshots: `AssertionError: [{'top': 230.2, 'bottom': 325.2, 'left': 16, 'right': 344, ...}, ...]` at line 315.
- test_dashboard_calendar_browser.py::test_dashboard_committed_stay_refresh_retry_does_not_post_twice: Page.wait_for_function timeout 30000 ms.
- test_host_list_layouts_browser.py::test_dashboard_and_stays_share_compact_row_menu: `AssertionError: (('en', 360), {'dashboard': 0, 'stays': 44})` at line 77.

Not verified whether the five non-named failures predate this brief (no run on the parent commit). Stopped per brief section 8.

Screenshots present (from the test run; not confirmed as rewritten by this run): shots/0133/dashboard-single-en-390.png, shots/0133/dashboard-single-en-1280.png.

Deviations: step 5 changed only line 695 of test_dashboard_calendar_browser.py; the identical text at lines 627 and 710 was left alone (brief names only ~695).
Questions: should the five non-named failures be handled in a new brief?


## 0133-fix-1 (executor run)

Status: blocked. Steps 1 to 3 committed; step 4 has 4 failures outside the brief's named cause (acceptance not met). Nothing pushed, no PR (owner said no push).

Commits: `8d37fd1` step 1 (phone rows on one DOM, `is-overdue` hook, catalog), `62972be` step 2 (phone table CSS), `5450456` step 3 (33 px gap, `row.textContent`).

Step 4, `tail -25`: `5 failed, 47 passed, 3 warnings`. Verbatim:
- `test_host_list_layouts_browser.py::test_stays_pills_and_deadlines_stay_on_one_line` (expected, 0134): `E   assert row["height"] <= 72`, `('en', 1280, {... 'height': 85 ...})`
- `test_dashboard_calendar_browser.py::test_calendar_geometry_locales_and_screenshots:315`: `E   assert (369.203125 - 325.203125) <= 33`
- `test_dashboard_calendar_browser.py::test_dashboard_committed_stay_refresh_retry_does_not_post_twice:704`: `playwright._impl._errors.TimeoutError: Page.wait_for_function: Timeout 30000ms exceeded.`
- `test_host_quiet_dashboard_browser.py::test_dashboard_rich_queue_colors_cap_and_interaction_screenshots:318`: `E   assert False` where `is_visible()` on `.dashboard-actions >> a[href="/reservations?new=1"]`
- `test_design_dashboard.py::test_dashboard_with_a_property_has_the_v2_header_one_primary_and_refresh_hooks:11`: `E   assert ('class="ui-stats"' in page and page.count('class="ui-stat"') == 3)`

Baseline check: the same 4 tests (all except list_layouts) fail at `2a477eb`, before any 0133-fix-1 commit. The geometry test also fails at line 315 there with the old limit of 16. So these are pre-existing, not caused by steps 1 to 3. I did not fix them: none is named in the brief, and the 33 px limit does not match the measured 44 px gap.

Lint: `design_lint` OK; ruff `--select E9,F63,F7,F82,F401,F841` "All checks passed!".

Screenshots (scratchpad `shots/0133/`): `dashboard-390.png`, `dashboard-1280.png`. These are copies of `dashboard-single-en-390.png` and `-1280.png`, written by a test run at 08:27. I have not confirmed which test wrote them. Viewed the 390 one: the stay is a card with the row menu (three dots) visible. The bottom tab bar overlaps the calendar in the full-page capture, which is likely a fixed-nav artifact.

Deviations: step 4 acceptance not met; I stopped at the brief's §8 rule instead of fixing the four tests. Untracked `docs/tasks/0102-evidence/*.png` files were already in the tree and are not committed.

Questions:
1. Is the geometry test's 33 px limit right, given the measured 44 px gap?
2. Should the four pre-existing failures get their own brief?

Owner steps left: none. Push and PR wait for the owner's decision.

## 0133-fix-2

Status: blocked (executor hit the 25-call cap; steps 1 to 4 partly done, step 5 not done).

Done (commits 3139e4b, e4d420d, 6b0d299, plus the browser-fix commit below):
- Regression restored: "Finish setup" aside (dashboard.setup.title) wraps the missing-report banner in dashboard.html.
- Regression restored: none other. Finish card line was already present.
- Tests updated: missing banner (v2 ui-banner-attention), queue copy / deadline / host language (td.dashboard-row-task, tr.dashboard-row, section[id=needs-action]), dashboard-row-dates class-contains, design dashboard stats (class-contains, dropped "dashboard-stats" negative check), wp25 and inline controls via property_identity, lock-account test scoped to main.
- property_identity: outer class is the old `property-identity{{ truncate }}`; dot moved to inner empty span.ui-pdot.
- Browser: quiet dashboard selector `.dashboard-actions` -> `.ui-ph-acts`. Calendar gap measured 44 px at every width (360 to 2048, en and cs), limit set to 44. Retry test: the comparison ignores [data-copy] button text (copy feedback "Copied" is transient UI state, not row content).

Not done / remaining:
- test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages fails: selector `.properties-table .row-actions > a.btn` finds nothing (apartments page has no .properties-table). Not in brief section 2; needs a v2 selector decision.
- Quiet dashboard browser test re-run not verified after selector change.
- Browser set not re-run as a whole. Only the allowed 0134 stays test is known to fail.
- design_lint and ruff not run.

## 0133-fix-3

Commits: 413ff4d step 1 (dashboard.html Anchor A to ui_banner with action; _ui_layout.html Anchor B comment).

- Step 2 (`pytest` non-browser set, `--tb=line`): `1 failed, 123 passed, 1 skipped, 1 warning in 23.94s`. The failure is the known local `test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages` (`assert 0 == 3`, `where 0 = len([])`). The one skip was not identified.
- Step 3 (browser set, `-rfs`): `2 failed, 27 passed, 3 warnings in 95.07s (0:01:35)`. Failures:
  - `test_host_list_layouts_browser.py::test_stays_pills_and_deadlines_stay_on_one_line`: `assert 85 <= 72` (expected, 0134).
  - `test_host_quiet_dashboard_browser.py::test_dashboard_rich_queue_colors_cap_and_interaction_screenshots`: `assert False` / `where False = is_visible()` on `locator('.ui-ph-menu')`, test line 330. Failed the same way on two runs. Not in the brief's known list, not touched by this change; blocking per section 8.
- Step 4: `dashboard-390.png` and `dashboard-1280.png` exist in the shots dir, written by the test run (`/?lang=en`, Quiet Dashboard host). Neither shows a "Finish setup" button on the setup banner, though `ui_banner` renders one when `action_href` is set. Open question.
- Step 5: `design_lint.py`: `design lint: OK`. `ruff check --select E9,F63,F7,F82,F401,F841 App/`: `All checks passed!`.

Acceptance: step 2 passes except the known failure; step 3 not passing; screenshots exist.

Owner steps left: decide whether the `.ui-ph-menu` failure is pre-existing (check on the 0133-fix-2 commit d79da3d), and why the setup banner shows no button.

