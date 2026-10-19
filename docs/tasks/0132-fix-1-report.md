# 0132-fix-1 report

Status: blocked

## Files changed
- App/app/static/host2.css (step 1, commit a1e12e8): added phone `.row-menu-item` min-height rule.
- App/tests/test_host_quiet_dashboard_browser.py (step 2, a63053d): amber selector accepts `.pill.amber` or `[data-tone="amber"]`.
- App/tests/test_host_stay_actions_browser.py (step 3, d02b3f5): reads `[data-tone]` and compares `data-tone`.
- App/tests/test_host_list_layouts_browser.py (step 4, e14050f): reads `[data-tone]` and `[data-deadline]`.

## §6 results
Command: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_quiet_dashboard_browser.py tests/test_host_stay_actions_browser.py tests/test_host_list_layouts_browser.py -q --tb=short -rs`
Last lines:
```
E   AssertionError: touch target is only 40px high in en/360
E   AssertionError: assert 3 == 4
E   AssertionError: ('en', 1280, {'pill': True, 'deadline': True, 'height': 85, 'name': 23, ...})
FAILED tests/test_host_quiet_dashboard_browser.py::test_dashboard_geometry_locales_and_screenshots
FAILED tests/test_host_quiet_dashboard_browser.py::test_dashboard_rich_queue_colors_cap_and_interaction_screenshots
FAILED tests/test_host_list_layouts_browser.py::test_stays_pills_and_deadlines_stay_on_one_line
3 failed, 2 passed, 1 warning in 32.89s
```
Lint: `python3 ../scripts/design_lint.py` -> `design lint: OK`. `ruff check --select E9,F63,F7,F82,F401,F841` -> `All checks passed!`.

## Row-height diagnostic (step 4)
Failing row at 1280 px, en: height 85 (limit 72). Cell heights: stay-col-stay 68, stay-col-dates 39, stay-col-property 39, stay-col-guests 22.25, stay-col-reporting 50, stay-col-actions 42. The stay column is the tallest cell. The temporary print was removed (`git checkout` to step 4 commit).

## Screenshot
Not taken: the browser tests still fail, so the 390 px screenshot step was not run.

## Deviations and questions
1. Touch target (dashboard test, line 232): the step 1 rule does not win. The 0132 rule `.host-workspace .ui-menu-panel .row-menu-item { ... min-height: var(--control-h) }` sits at host2.css line 285, after the 767px media block (line 114-121). Same specificity, later source order, so it still gives 40 px. Question for the owner or orchestrator: move the phone rule after line 286, or raise its specificity? I did not change it.
2. Header action count (dashboard test, line 328): expected 4 `.action-group` buttons, got 3 at en/360. Not named in brief §1, so I stopped. Not investigated.
3. Row height 85 vs 72 at 1280 px: brief says stop and report blocked. Diagnostic above.

## Owner steps left
None until the questions above are answered.
