# 0365: Make the push-alerts browser tests pass

Status: review
Depends on: none | Base commit: 5439abe | Branch: task/0365-push-settings-browser
Executor: Sonnet (debugging brief, owner allowed a stronger model 2026-10-24) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

These browser tests have never run in CI (the `test` job has no Playwright, so they skipped). Brief 0361 turns them on, and they fail locally on main. Find for each failure whether the test is stale (the page was changed on purpose later) or the app has a real bug, and fix it the smallest correct way, so the new `browser` CI job can go green.

## 2. Context

- Failing tests (local survey 2026-10-24, Chromium, main at 5439abe):
  - `tests/test_push_settings_browser.py`: 8 failures: `turning_alerts_on_sends_one_test` (3 cases), `the_alerts_row_fits_wide_layouts` (4 cases), `logging_out_turns_alerts_off_on_this_device`. 3 pass. Check first whether headless Chromium needs a granted notification permission or a service-worker setup the test forgot (`context.grant_permissions(["notifications"])`); that is a test fix, not an app fix.
- Local browser setup: `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_SHELL_BROWSERS=chromium`, venv `App/.venv` (installed, Playwright 1.63.0). WebKit is not installed locally.
- Decide stale vs bug from evidence: `git log -L` or `git log -S` on the asserted selector or text, the commit message and brief (`docs/tasks/NNNN-*.md`) that changed it, and the current design rule in `docs/design/MASTER.md` (grep the section only).
- AGENTS.md hard rule 7: a template or CSS change needs the browser and geometry tests of that page passing with 0 skipped, and one 390 px screenshot per changed page in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_push_settings_browser.py` | edit or keep | Stale assertions, if stale |
| `docs/tasks/0365-report.md` | create | Report |

A fix may also touch the template, CSS or Python module that renders the failing page, if and only if the evidence shows an app bug. Name each such file in the report. Any other file: STOP.

## 4. Steps

1. Run each failing file with §6 (a). Read the assertion and its error.
2. For each failure, find the evidence (§2) and write one line: stale test or app bug, with the commit that explains it.
3. Stale test: update the assertion to the intended current behaviour, keeping what the test protects. App bug: fix the app the smallest way. Commit `0365 step 3` per file.
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

Write `docs/tasks/0365-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

Every app file the fix touched.

## Owner steps

1. Merge when CI is green.
