# 0961: fix CI ruff errors and the wizard NameError (executor: Haiku 5.5, alone)
Status: todo

## 1. Objective
PR 789 CI `test` job fails on `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` (4 errors). One is a real runtime bug: the setup wizard would raise NameError.

## 2. Context (research done; do not redo)
- `App/app/routes/onboarding_wizard.py:37-41` `_admin_helpers()` imports `stay_fees as stay_fee_routes` inside the function (unused there, F401) while line ~147 uses `stay_fee_routes.guest_pay_operator_context(...)` in another function (F821, NameError at runtime).
- `App/app/routes/stay_fees.py:520` `from .. import db, payments`: `payments` unused (F401).
- `App/tests/test_stay_fee_guest_pay_browser.py:38` `marker = {"n": 0}` assigned, never used (F841).

## 3. Files
`App/app/routes/onboarding_wizard.py`, `App/app/routes/stay_fees.py`, `App/tests/test_stay_fee_guest_pay_browser.py`, `App/tests/test_stay_fee_guest_pay_0897.py` (one new test).

## 4. Steps
1. In `onboarding_wizard.py` remove the unused import from `_admin_helpers()` and import `stay_fees as stay_fee_routes` where it is used (function level import next to the use, as the file does for other routes; check for a circular import).
2. Remove `payments` from the import at `stay_fees.py:520`; delete the unused `marker` line.
3. Add a TestClient test in `test_stay_fee_guest_pay_0897.py` that opens the setup wizard step which renders `guest_pay_operator` (find it with `grep -n guest_pay_operator App/app/routes/onboarding_wizard.py`) and asserts HTTP 200 (no crash) with the flag on.

## 5. Do not touch
Everything else.

## 6. Commands
From App/: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -20` (`pip install ruff` if missing), then `python3 -m pytest tests/test_stay_fee_guest_pay_0897.py -q --tb=short -x -p no:cacheprovider 2>&1 | tail -30`, plus any existing wizard test file (`grep -ln onboarding_wizard tests/*.py`).

## 7. Acceptance
Ruff clean; tests pass with 0 skipped.

## 8. Stop and ask
If the import is circular, stop and report.

## 9. Report
Write `docs/tasks/0961-report.md` (5 lines max) with a Status line; set this brief's Status to review. Commit (message ends with "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" and "Claude-Session: https://claude.ai/code/session_014N5J8MeH3Hk3RVuTWKDVVn"), run `python3 scripts/context_lint.py`, push to `claude/zealous-johnson-kjnz4e` only.
