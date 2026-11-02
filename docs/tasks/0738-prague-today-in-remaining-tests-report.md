# 0738 report: remaining date-sensitive tests use the app's clock

Status: done (see orchestrator review)
Executor: Haiku 5.5, worktree /tmp/wt0738, branch task/0738-prague-today-tests.

## Files changed
- `App/tests/test_endtoend.py`: added `claim` to the `from app import` line; line 65, 602, 620 use `claim.prague_today()` instead of `date.today()`.
- `App/tests/test_billing_analytics.py`: `TODAY = date.today()` replaced by `def _today(): return date.today()`; every `TODAY` use is `_today()`. App code not touched.
- `App/tests/test_demo_seed.py`: no change. The test itself has no `date.today()` or import-time date (it already uses `claim.prague_today()` at line 71). Stopped on this file per brief §2.
- `docs/tasks/0738-prague-today-in-remaining-tests-report.md` (this file).

## Commands
- Step 2 (before), `PYTHONPATH=/tmp/tzplug .venv/bin/python -m pytest -p tzshift tests/test_endtoend.py tests/test_billing_analytics.py tests/test_demo_seed.py -q --tb=no 2>&1 | tail -3`
  - `FAILED tests/test_billing_analytics.py::test_month_snapshot_and_movement - as...`
  - `FAILED tests/test_demo_seed.py::test_seed_imports_stays_without_fetching_the_calendar`
  - `23 failed, 39 passed in 5.96s`
- Step 4 (after, default plugin), same command:
  - `FAILED tests/test_billing_analytics.py::test_month_snapshot_and_movement - as...`
  - `FAILED tests/test_demo_seed.py::test_seed_imports_stays_without_fetching_the_calendar`
  - `22 failed, 40 passed in 5.59s`
- Ruff (`--select E9,F63,F7,F82,F401,F841`): `All checks passed!`

## Acceptance (§7)
- [ ] Not met: 22 failures remain with the plugin. Stopped per brief §8. The `SHIFT_TZ=Pacific/Kiritimati` run and the no-plugin run were not done.
- [x] No `date.today()` or import-time `TODAY` left in the three files, except inside `_today()`.

## Stop reason (brief §8)
The date fix is in, but the failures are not only date failures:
- `test_endtoend.py`: 20 failures (test_03 to test_28, including test_03 to test_05, which do not use the changed lines). Example from test_21: `tests/test_endtoend.py:512: assert False`. The tracebacks for the ones I looked at show HTML page dumps as the compared text, so these are page or response assertions; I did not check each one for a date.
- `test_billing_analytics.py::test_month_snapshot_and_movement`: `assert 3649 == 149`.
- `test_demo_seed.py::test_seed_imports_stays_without_fetching_the_calendar`: `assert None` at line 49 (`demo.seed()` returns None). This is an app-side return value, outside the brief's scope (`app/demo.py` not to be changed).

Likely the brief's diagnosis covers only part of the failures. The owner or orchestrator should decide the next step. I did not guess further fixes.

## Deviations
- Commit trailer: brief §9 says `Co-Authored-By: Claude Opus 5.5`. I used `Co-Authored-By: Claude Haiku 5.5` per the session attribution reminder, since I am the executor.
- No PR opened, because the status is blocked. The branch is pushed for review.
- One commit at the end (brief files, test changes, report) instead of per-step commits, per the orchestrator's instruction.

## Questions
- Are the 20 test_endtoend failures (and the billing/demo_seed ones) expected to be fixed by this brief? They do not look date-related from the first assertions.

## Owner steps left
- Decide whether 0738 needs a new brief for the non-date failures.

## Orchestrator review (supersedes the BLOCKED status)

Status: done (see orchestrator review)

Root cause of all 24 CI failures (run 41364636354): the run crossed UTC midnight. `test_billing_analytics.py` captured `TODAY` at import (Nov 1) and the app read Nov 2, so `test_the_operator_assigns_a_plan_to_a_legacy_host` failed at line 275, before its in-body cleanup (line 286). Its legacy host's apartment stayed in the database, so `demo.seed()` returned None (it refuses when any apartment exists), and `test_endtoend.py` test_04 picked that stray apartment with `SELECT * FROM apartment`, which cascaded through test_05 to test_29. The `_today()` change removes the trigger; `claim.prague_today()` in test_endtoend removes the Prague/UTC hour mismatch. The three files pass in CI order normally (62 passed).
