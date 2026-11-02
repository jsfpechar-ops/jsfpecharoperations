# 0738 brief: the remaining date-sensitive tests use the app's clock

Status: todo
Executor: Haiku 5.5, worktree /tmp/wt0738 (branch task/0738-prague-today-tests, from main).

## 1. Objective
24 tests failed on main (CI run 41364636354, started 2026-11-01 23:57Z) and on every PR run in that hour. Two causes: (a) a test computes "today" with `date.today()` (machine/UTC date) while the app uses the Prague date (`claim.prague_today()` / `deadlines.local_now()`); (b) a test captures `TODAY` at import time, and the run crosses midnight before the app reads its own date. Make the tests read the same clock as the code under test, at the moment they need it.

## 2. Context
Failing files and the lines to change:
- `App/tests/test_endtoend.py`: line 65 (`feed_url` fixture: `check_in = date.today() - timedelta(days=1)`), lines 602 and 620 (`create_manual_stay(host, date.today() - ...)`). The app (calendar import, guest links, deadlines) uses the Prague date. Use `claim.prague_today()`; if that helper is not importable in this file, `deadlines.local_now().date()`. All test_04 to test_29 failures cascade from the fixture.
- `App/tests/test_billing_analytics.py`: line 17 `TODAY = date.today()` at import. `app/billing.py` and `app/billing_analytics.py` use `date.today()` at call time (do NOT change that). Replace the module constant with a value computed when the test runs: a small function `def _today(): return date.today()` called inside each test/fixture (replace every `TODAY` use), so the test and the app read the date at the same moment.
- `App/tests/test_demo_seed.py`: `demo.seed()` returned None. It already uses `claim.prague_today()` (line 71); look for any other `date.today()` / import-time date in this file and in the fixtures it uses, fix the same way. If you find no date in the test itself, note it in the report and stop on this file (do not change `app/demo.py`).

## 3. Files
The three test files above, new `docs/tasks/0738-prague-today-in-remaining-tests-report.md`.

## 4. Steps
1. Create this scratch plugin OUTSIDE the repo (it makes the app's local date differ from the UTC date; it is never committed):
   `mkdir -p /tmp/tzplug && printf 'import os\nfrom app import config\nconfig.TIMEZONE = os.environ.get("SHIFT_TZ", "America/Los_Angeles")\n' > /tmp/tzplug/tzshift.py`
2. Before changing anything, run: `PYTHONPATH=/tmp/tzplug .venv/bin/python -m pytest -p tzshift tests/test_endtoend.py tests/test_billing_analytics.py tests/test_demo_seed.py -q --tb=no 2>&1 | tail -3` (expect 19 failures in test_endtoend). Record the tail.
3. Make the changes in section 2. Remove imports that become unused (ruff F401).
4. Run the step 2 command again (must be 0 failed), then once more with `SHIFT_TZ=Pacific/Kiritimati` added in front, then normally without the plugin.

## 5. Do not touch
App code (`App/app/`), other tests, CI config.

## 6. Commands
From App/: the step 2 and 4 commands; `.venv/bin/python -m ruff check tests/test_endtoend.py tests/test_billing_analytics.py tests/test_demo_seed.py --select E9,F63,F7,F82,F401,F841 | tail -3`. Root: `python3 scripts/context_lint.py | tail -2`.

## 7. Acceptance
- [ ] All three files pass normally, with the plugin (default), and with SHIFT_TZ=Pacific/Kiritimati.
- [ ] No `date.today()` and no import-time `TODAY` left in the three files, except inside the billing `_today()` helper.

## 8. Stop and ask
If a test still fails with the plugin after your change, stop and report the assertion text.

## 9. Report
Report file with Status, files changed, the before/after test tails. Commit "0738: remaining date-sensitive tests use the app's clock" with trailers
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7MiM1A2ZF45zsFsEf9
then `git push -u origin task/0738-prague-today-tests`.
