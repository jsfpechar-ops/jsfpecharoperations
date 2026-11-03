# 0833 report (executor)

Status: blocked
Done: step 2.1 (phone hide rule found and overridden; phone host calendar shows, test passes at 390). Left: steps 2.2 to 2.3 (rewrite the failing tests to the tag UI), 4 (phone long-press range test), 5 (check dashboard look), 6 (year view cleanings only), 7 (screenshots).

## Files changed (not staged, not committed)
- `App/app/static/dashboard-calendar.css`: appended `/* 0833 */` block. One rule: `body.v2 .cleaning-page #calendar.dashboard-calendar[data-readonly="false"] { display:block; }`. Cause: `App/app/static/app2.css` line 1075 has `@media (max-width:767px){body.v2 .cleaning-page .cleaning-legend,body.v2 .cleaning-page #calendar{display:none}}`. The read-only page (`data-readonly="true"`) keeps the hide.
- `docs/tasks/0833-report.md` (this file).
- Not changed: templates, tests, `?v=`, `static_versions.json`.
- `docs/tasks/screenshots-0814/`: the test run with `UBYHOST_TASK_SHOTS=1` rewrote 8 tracked `calendar-*.png` files there (modified in git; restore with `git checkout -- docs/tasks/screenshots-0814/` if not wanted). Three new files exist from the test run: `cleaning-390.png`, `cleaning-768.png`, `cleaning-1280.png`. Missing: `cleaning-range-390.png`, `cleaning-range-1280.png`. Not inspected.

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_TASK_SHOTS=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py -k test_phone_cleaning_calendar_tags_only -q -rs --tb=short`
   Last line: `2 passed in 4.12s`. Skipped: 0.
2. Brief §4 command (all five files), `-q -rs --tb=line`
   Last line: `15 failed, 39 passed in 315.50s (0:05:15)`. Skipped: 0.
   The failures are the tests listed in 0815 (bars, labels, visible list on the host page) plus the 0832 refresh test at the /cleaning step. I did not split the count per file in this run.

## Tests rewritten
None. The 15 failing tests still expect bars, labels or the list. Rewriting them needs reading the test file in full, which did not fit this session's budget.

## Deviations
- Commits were skipped as the owner asked (the executor doc says to commit per step). Nothing staged.
- No PR opened (the report is left for review).

## Questions
- The phone host cleaning page now shows the calendar and hides the list and legend (per 0815 CSS). Confirm this is the intended phone design.

## Owner or next session
- Next session: rewrite the 15 failing tests (brief §2.2, §2.3), add the phone long-press test (§2.4), check year view (§2.6), make the two missing range screenshots (§2.7) and look at the three existing ones.
