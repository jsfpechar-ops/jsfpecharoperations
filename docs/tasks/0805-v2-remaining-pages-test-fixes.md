# 0805 brief: test fixes after 0800-0804 (v2 remaining pages)

Status: blocked
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective

The four test failures below pass without changing any page other than those moved in 0800-0804.

## 2. Context
Commit 9664ef2 moved these pages to the v2 shell (reports: docs/tasks/0800-report.md … 0804-report.md): /apartments/new, /onboarding, setup wizard, host guest guide, /guide, /havel, /cleaning/new|shares|properties. v2 pages load only tokens.css + app2.css. Shared rules: docs/tasks/0800-new-property-onboarding-v2.md section "Shared rules". Do not change other pages.

## 3. Files

The templates and app2.css blocks from 0800-0804, and the four test files named below.

## 4. Steps

Fix these failing tests (fix the app first; change an assertion only if it checks old pre-v2 markup of these pages, and say so in the report):
1. `tests/test_onboarding.py::test_the_calendar_step_offers_adding_a_stay_by_hand`: "Add a stay by hand" disappeared from /onboarding in the v2 `onboarding_welcome` macro (`App/app/templates/_components.html`). Restore that link in the calendar step (restyle only: nothing that was offered before may vanish).
2. `tests/test_quick_answers_browser.py::test_the_chips_are_big_full_width_and_show_their_state`: at 390 px the chip row must span the form width (formWidth 316, chips 50-340). Fix the `/* 0802 guest guide (v2) */` block in app2.css so chips fill the form width (e.g. grid columns 1fr and no extra side offset).
3. `tests/test_design_shell_browser.py::test_more_preserves_each_page_kind_and_sheet_links_work[/apartments/new…-390]` and `[-820]`: a click times out on /apartments/new. Read the test to see which control it clicks (old shell "More" sheet?). If the test lists v2 pages separately (look how `/apartments`, `/cleaning`, `/reservations` are handled in that file), treat /apartments/new the same way; otherwise fix the page.
4. Run `tests/test_onboarding_wizard_browser.py` (setup wizard, restyled in 0801). For each failure decide: app bug from the v2 restyle (fix in the `/* 0801 setup wizard (v2) */` block or setup_wizard templates) or an assertion on old-shell styling (e.g. a colour from wizard.css): update to the v2 value. List each in the report.

## 6. Commands

From App/:
`export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`
- `.venv/bin/python -m pytest tests/test_onboarding.py tests/test_quick_answers_browser.py tests/test_design_shell_browser.py tests/test_onboarding_wizard_browser.py -q --tb=line 2>&1 | grep -v "^  " | tail -30`
- Finally: `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q --tb=line 2>&1 | tail -5` must stay 90 passed.
- From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5`.
- Tests write PNGs into docs/tasks/0102-evidence and other screenshot folders: leave them, do not stage or restore them.

Write docs/tasks/0805-report.md (changed files, each failure and its fix, final tails). Stop at 30 tool calls and report.

## 5. Do not touch

Other pages, existing app2.css lines, wizard.css, cleaning.css, the guest-facing pages, static cache key, screenshot folders other than screenshots-0800.

## 7. Acceptance

`tests/test_0800_v2_remaining_pages_browser.py` 0 failed for the brief's routes; the existing tests of the pages pass; design_lint passes.

## 8. Stop and ask

Stop and report if a route redirects away from the page, a fix would need a change to another page, or you reach 30 tool calls.

## 9. Report

`docs/tasks/<number>-report.md`: changed files, test tails, screenshot paths, deviations.
