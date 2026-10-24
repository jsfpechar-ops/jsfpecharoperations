# 0366: Make the property create and navigation browser tests pass

Status: todo
Depends on: none | Base commit: 5439abe | Branch: task/0366-property-pages-browser
Executor: Sonnet (debugging brief, owner allowed a stronger model 2026-10-24) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

These browser tests have never run in CI (the `test` job has no Playwright, so they skipped). Brief 0361 turns them on, and they fail locally on main. Find for each failure whether the test is stale (the page was changed on purpose later) or the app has a real bug, and fix it the smallest correct way, so the new `browser` CI job can go green.

## 2. Context

- Failing tests (local survey 2026-10-24, Chromium, main at 5439abe):
  - `tests/test_property_create_browser.py::test_create_page_is_short_and_has_each_field_once`
  - `tests/test_property_navigation_browser.py::test_three_views_four_groups_one_editor_and_unique_ids` (CI ran only one other test of this file, `test_shared_timing_pair_is_owned_by_properties`, which passes)
- Local browser setup: `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_SHELL_BROWSERS=chromium`, venv `App/.venv` (installed, Playwright 1.63.0). WebKit is not installed locally.
- Decide stale vs bug from evidence: `git log -L` or `git log -S` on the asserted selector or text, the commit message and brief (`docs/tasks/NNNN-*.md`) that changed it, and the current design rule in `docs/design/MASTER.md` (grep the section only).
- AGENTS.md hard rule 7: a template or CSS change needs the browser and geometry tests of that page passing with 0 skipped, and one 390 px screenshot per changed page in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_property_create_browser.py` | edit or keep | Stale assertions, if stale |
| `App/tests/test_property_navigation_browser.py` | edit or keep | Stale assertions, if stale |
| `docs/tasks/0366-report.md` | create | Report |

A fix may also touch the template, CSS or Python module that renders the failing page, if and only if the evidence shows an app bug. Name each such file in the report. Any other file: STOP.

## 4. Steps

1. Run each failing file with §6 (a). Read the assertion and its error.
2. For each failure, find the evidence (§2) and write one line: stale test or app bug, with the commit that explains it.
3. Stale test: update the assertion to the intended current behaviour, keeping what the test protects. App bug: fix the app the smallest way. Commit `0366 step 3` per file.
4. Run §6 (a) for every file in §3 twice, plus §6 (b). All pass, 0 skipped.
5. Write the report.

## 5. Do not touch

`.github/`, UbyPort filing code (`App/app/ubyport*`, `App/app/claim.py`, submission logic), migrations, auth. Never skip, xfail, delete or loosen a test to green it: a changed assertion must still catch the bug the test was written for. Never push or merge.

## 6. Commands

From `App/`, env from §2:

(a) `.venv/bin/python -m pytest <file> -q -rs --tb=short -p no:cacheprovider 2>&1 | tail -30`

(b) `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -10` (guardrails stay green)

## 7. Acceptance

- [ ] Every test in §2 passes twice in a row, 0 skipped; §6 (b) passes.
- [ ] The report has one line per failure: stale or bug, evidence commit, what changed.
- [ ] No test was skipped, deleted or loosened.

## 8. Stop and ask

Stop, and write the report, if: the fix touches UbyPort filing, auth, migrations or guest data; the intended behaviour is unclear from the evidence (two readings possible); a test fails twice after your fix; you reach 25 tool calls or about 50k tokens; you would need push, merge or secrets.

## 9. Report

Write `docs/tasks/0366-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

Every app file the fix touched.

## Owner steps

1. Merge when CI is green.
