# 0842 report

Status: blocked

Done: steps 1, 2 (with the banner override), 3a to 3c. Step 4 (focused run) run twice. Stopped before §6 (full run), §7 shots and §10 speed checks, because a test failed and the head-gap failure is unexplained.

## Files changed (uncommitted, nothing staged)
- `App/app/static/dashboard-calendar.css`: step 1 (line 729 wrapped in `@media (max-width:767px)`), step 2 `/* 0842 */` block appended. Override: the `body.v2:has(...) .env-banner { display:none; }` line was removed from the block.
- `App/tests/test_cleaning_browser.py`: old 0835 two-row test and `ROW_CONTROLS`/`VISIBLE_BOXES` deleted (anchors 743, 751, 780, 809 matched; count of leftovers = 0). Three 0842 tests appended. The `.env-banner` assertion in the phone test was omitted (override).
- `docs/tasks/0842-report.md` (this file).

## Commands (last lines)
1. Focused, `-k "0835 or 0842 or phone_cleaning or desktop_cleaning" -x`:
   `1 failed, 7 passed, 22 deselected in 12.49s`. Failing: `test_0835_cleaning_range_shot_1280_mouse_drag`, `assert [] == ['2026-10-12', ...]`.
2. Same drag test with the 0842 block temporarily removed (file restored, verified with cmp):
   `1 failed, 38 deselected in 2.47s`. So the drag failure is not caused by 0842.
3. `-k "0842"`:
   `1 failed, 8 passed, 30 deselected in 12.49s`. Failing: `test_0842_cleaning_toolbar_one_row_at_1280`, line 850 (head gap): `assert 0 >= 11`, head boxes `[{x:512.05,w:128.97,y:100,h:40},{x:641.02,w:230.56},{x:1023.56,w:220.44}]`. The one-row, 40 px, 24px/700 title, Gantt and gap≥11 assertions before it passed. Phone 320/390 and overflow 320 to 1440 tests all passed.

## §7 ticked
- [ ] All §6 tests pass: not run (stopped).
- [ ] Shots retaken: no.
- [x] Diff limited to §3 files (`git status` shows the 0835 files already changed plus these two).

## Deviations
- Env-banner sub-step skipped per the owner override (safety warning stays on phone).
- Temporary CSS backup written to `/tmp` for the diagnostic run; removed afterwards.
- Stopped at the second failing test rule, per executor.md: the drag test fails with and without this change; the head gap is a first failure with no confirmed cause.

## Questions
1. `test_0835_cleaning_range_shot_1280_mouse_drag` selects nothing after mouse drag on `.cal-day` (1280). It fails with the 0842 block removed too, so it comes from the uncommitted 0835 work. Please check that before commit.
2. Head buttons at 1280 measure 0 px apart. `.cleaning-actions` is flex with `gap:8px` (`App/app/static/cleaning.css` line 10); the 1024+ rule sets `gap:12px` (`dashboard-calendar.css` ~line 750). No override found in a static grep of `app2.css` and `cleaning.css`. Needs a computed-style check in the browser (e.g. `getComputedStyle(.cleaning-actions).gap`) before a fix.

## §10 speed checks
Not done (stopped).

## Owner steps left
None. After the two questions are answered: bump `?v=` for `dashboard-calendar.css` (`_dashboard_calendar.html` line 2) and commit 0835 and 0842 together.
