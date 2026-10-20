# 0186: CI fix, a browser test expects transparent table cells

Status: todo
Depends on: 0185 | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

CI job `guest-browser` fails in `App/tests/test_onboarding_followup_browser.py` line 53: after hovering a Stays row the test asserts every `td` background is `rgba(0, 0, 0, 0)`. Brief 0181 deliberately gives desktop `td` cells their own background (`var(--surface)`, hover `var(--surface-2)`) so each row reads as a bordered box. The test's intent is that the row highlights as one piece with no cell painting a different colour. Change the assertion to that intent.

## 2. Context

Line 49-53: `initial` is the row background before hover, then `row.hover()`, then the row background must differ. With opaque cells the row's own background is no longer what the user sees, so the first check may also need to read the first `td` instead of the `tr`.

## 3. Files

`App/tests/test_onboarding_followup_browser.py`, other browser tests the search in step 2 finds, `docs/tasks/0186-*`.

## 4. Steps

1. Replace lines 49-53 so that the colour compared before and after hover is the first `td` background, and the final assertion is: after hover, all `td` of the row share one background colour (`new Set(cells.map(...)).size === 1`) and it differs from `initial`.
2. From `App/`: `grep -rln "tr\[data-href\|ui-row" tests/*browser*.py | head -20` and check each for assertions that would break with opaque `td` backgrounds or with 8 px gaps between rows (transparent-cell checks, row-to-row adjacency, row height sums). Run each of those files with the browser env; fix only expectations made stale by 0181 (bordered rows with a gap) and list each in the report.
3. From `App/`, foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`: `.venv/bin/python -m pytest tests/test_onboarding_followup_browser.py <the other files from step 2> -q -rs --tb=short 2>&1 | tail -12`. Expected: 0 failed, 0 skipped. A failure that also fails on main (known: `test_list_pages_share_order_edges_and_rhythm`, `test_property_navigation_browser`, `test_host_ux_acceptance`) is named in the report, not fixed.
4. Then `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused) and, from the repo root, `python3 scripts/context_lint.py 2>&1 | tail -3`.
5. Commit "0186: row hover test matches bordered rows" with the trailers given by the orchestrator. Do not push.

## 5. Do not touch

App code, templates, CSS; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] The browser files from step 2 pass with 0 skipped; lint OK.

## 8. Stop and ask

An anchor is missing, or a test fails twice for a reason outside the row styling.

## 9. Report

`docs/tasks/0186-report.md`, short; `Status: review`.
