# 0369: Headcount test: one clock, so it passes on the night the clocks change

Status: todo
Depends on: none | Base commit: 2676d06 | Branch: task/0369-dst-midnight-test
Executor: Haiku 5.5 | Fits one session: 10 tool calls, 30k tokens

## 1. Objective

`App/tests/test_guest_navigation.py::test_a_short_party_is_flagged_once_the_stay_has_started` failed on every PR on 2026-10-24 from 22:00 to 23:00 UTC. The stay starts on `claim.prague_today()`, but the test checks deadlines at `datetime.now(timezone.utc) + timedelta(days=1)`. Prague left summer time that night (UTC+2 to UTC+1), so "now + 24 h" was still the same Prague date as the check-in, and `start < now.date()` in `reporting.check_deadlines` was false. The app is right; the test must use Prague dates for "tomorrow".

## 2. Context

- Line 929 on main: `        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)`
- `reporting.check_deadlines(now)` calls `deadlines.local_now(now)`, which returns a naive datetime unchanged (it is read as Czech civil time).
- `datetime` and `claim` are already imported in the file. `time` there is the module, so do not use `datetime.time`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_guest_navigation.py` | edit | line 929 only |
| `docs/tasks/0369-report.md` | create | Report |

No other file may change. No assertion changes.

## 4. Steps

1. Replace line 929 with these two lines (same indentation):
   `        day = claim.prague_today() + timedelta(days=1)`
   `        tomorrow = datetime(day.year, day.month, day.day, 12)  # Prague noon, naive`
   Commit `0369 step 1`.
2. Write the report. Commit `0369 step 2`.

## 5. Not allowed

Changing any other line, any assertion, or any file in `App/app/`.

## 6. Test

From `App/`: `.venv/bin/python -m pytest tests/test_guest_navigation.py -q --tb=short 2>&1 | tail -15`. All pass. Run it with the venv at `/home/claude/wt-0368-browser-test-portability/App/.venv` if `App/.venv` is missing.

## 7. Acceptance

- [ ] §6 passes, 0 failed.
- [ ] `git diff 2676d06 --stat` shows only the two files.

## 8. If blocked

Stop and write the blocker in the report. Do not change other files.

## 9. Report

`docs/tasks/0369-report.md`: status, what changed, §6 tail, acceptance ticks.
