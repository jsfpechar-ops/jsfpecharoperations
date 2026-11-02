# 0704: make the browser suite green after the shared look (0700-0703)
Status: todo
Depends on: 0700-0703 | Base commit: claude/project-thread-50hyv5 | Branch: claude/project-thread-50hyv5 (work directly, do not push)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
CI browser shards fail on PR #657 after the shared look. Make them pass by extending the shared look where a page was missed, and update an assertion only where it encodes the old look on purpose. The look itself (mockup v2) is decided; do not revert it.

## 2. Context (failures from CI on a83ba81; the coral contrast failures in test_a11y_guard_browser are already fixed by 8ccc7f7, re-check only)
1. `tests/test_0285_rows_browser.py:52` test_properties_rows_match_stays_rows at 1280: `table.properties-table tbody tr` still has per-row card edges (radius 12, border-spacing 0 8px) while stays rows are now one card. Fix: add the properties table (and any other list table the test compares) to the 0700 ">= 1024 px rows are one card" override in `App/app/static/host2.css`, so both match.
2. `tests/test_host_list_page_layout_browser.py:157` test_list_pages_share_order_edges_and_rhythm: `('rhythm', 'tabs', [53, 72])` — the gap before the tab strip differs between list pages, likely because 0700/0703 changed header or `.ui-how-toggle` spacing. Make the spacing equal across the list pages in the 0700 block (read the test to see which two elements it measures).
3. `tests/test_onboarding_wizard_browser.py:1173` (1280, en and cs): a wizard button has radius `8px` where `999px` is expected (pills). Add the wizard's button selectors to the 0700 pill rule (check `App/app/static/wizard.css` for the selector it uses; put the override in the 0700 block of host2.css only if the wizard page loads host2.css, otherwise in wizard.css as a clearly marked 0704 rule).
4. `tests/test_shell_lane_browser.py:81`: read the assertion; likely the account card moved to the top of the sidebar (0703) or the canvas. If it encodes the old sidebar order or old background, update it to the new layout; if it shows a real misalignment of the main lane, fix the CSS.
5. `tests/test_0284_states_browser.py` (already updated by 0703 for button alignment) and `tests/test_a11y_guard_browser.py`: re-run; if a11y still has findings, list them.

## 3. Files
`App/app/static/host2.css` (0700 block), `App/app/static/wizard.css` (only if item 3 needs it), their `?v=` keys in `App/app/templates/base.html` (`20261101-0704`), `App/tests/static_versions.json` (via `--write`), and the failing test files only for assertions that encode the old look. Report `docs/tasks/0704-report.md`.

## 4. Steps
For each item: run its test alone, read the assertion, fix, re-run, commit `0704 item N`. `python3 scripts/design_lint.py | tail -1` before each CSS commit.

## 5. Do not touch
Templates, JS, routes, phone styles (< 768 px) unless a phone test in this list fails.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0285_rows_browser.py tests/test_host_list_page_layout_browser.py tests/test_onboarding_wizard_browser.py tests/test_shell_lane_browser.py tests/test_0284_states_browser.py tests/test_a11y_guard_browser.py tests/test_0700_shared_look_browser.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -30` (the 0284 navigation step may fail locally because the mock UbyPort is unreachable here; say so if it is the only failure). Then from the repo root `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py 2>&1 | tail -1`.

## 7. Acceptance
All listed tests pass (or only the known local 0284 UbyPort step fails), 0 skipped.

## 8. Stop and ask
Stop if a fix would need a template change or would change phone layout.

## 9. Report
`docs/tasks/0704-report.md`: per item what was wrong and what changed (CSS fix or assertion update), test tail, diff stat.
