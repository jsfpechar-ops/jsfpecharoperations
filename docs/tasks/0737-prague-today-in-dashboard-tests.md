# 0737 brief: dashboard tests use the Prague date, not the UTC date

Status: todo
Executor: Haiku 5.5, worktree /tmp/wt0737 (branch task/0737-prague-today-tests, from main).

## 1. Objective
Seven tests fail every night from 23:00 to 00:00 UTC (CI run 41360292372 on main, 2026-11-01): their fixtures date stays with `date.today()` (the machine's UTC date) while the app reads "today" as `deadlines.local_now().date()` (Prague). Make the fixtures use the app's date.

## 2. Context
`App/app/deadlines.py` `local_now()` returns naive Prague civil time. Failing: `test_0520_overview_today.py::test_today_table_lists_arrivals_and_departures_today_only`, and in `test_dashboard_queue_copy.py`: test_a_reported_stay_says_nothing_is_left_to_do, test_a_stay_of_only_czech_guests_says_nothing_goes_to_the_police, test_a_finished_stay_never_falls_back_to_check_what_is_missing, test_a_czech_host_reads_the_new_next_actions_in_czech, test_dashboard_rows_keep_dates_and_meaningful_task_context, test_task_cards_translate_time_context.

## 3. Files
`App/tests/test_0520_overview_today.py`, `App/tests/test_dashboard_queue_copy.py`, new `docs/tasks/0737-prague-today-in-dashboard-tests-report.md`.

## 4. Steps
1. In both files replace every `date.today()` with `deadlines.local_now().date()`. Add `from app import deadlines` (or add `deadlines` to an existing `from app import ...` line). If `date` is then unused, remove it from its import (ruff F401).
2. Prove the fix: run the two files with the clock pinned to a UTC time that is already the next day in Prague, e.g. `TZ=UTC faketime` is not available, so instead monkeypatch nothing: just run normally, then also run once with `TZ=Pacific/Pago_Pago` (UTC-11; right now its date is a day behind Prague) to show they pass when the machine date and the Prague date differ: `TZ=Pacific/Pago_Pago .venv/bin/python -m pytest tests/test_0520_overview_today.py tests/test_dashboard_queue_copy.py -q 2>&1 | tail -5`. Run the same command on the unmodified files first (`git stash`, run, `git stash pop`) and report whether it failed before.

## 5. Do not touch
App code, other tests.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests/test_0520_overview_today.py tests/test_dashboard_queue_copy.py -q 2>&1 | tail -5`; `.venv/bin/python -m ruff check tests/test_0520_overview_today.py tests/test_dashboard_queue_copy.py --select E9,F63,F7,F82,F401,F841 | tail -3`. Root: `python3 scripts/context_lint.py | tail -2`.

## 7. Acceptance
- [ ] Both files pass normally and with TZ=Pacific/Pago_Pago.

## 8. Stop and ask
If a test still fails with the Prague date, stop and report the assertion.

## 9. Report
Report file with Status, files, both test tails (before/after with TZ). Commit "0737: dashboard tests use the Prague date" with trailers
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7MiM1A2ZF45zsFsEf9
then `git push -u origin task/0737-prague-today-tests`.
