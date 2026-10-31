# 0457: Sane scheduler intervals for door_codes, guide_import and push
Status: review
Depends on: none | Base commit: main | Branch: task/0457-job-intervals
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens
## 1. Objective
Stop three jobs from running every minute when their event-driven primaries already do the work. Change only the numbers in `job_intervals()` and the matching admin "late" threshold behaviour that reads it.
## 2. Context
`App/app/scheduler.py:job_intervals()` returns `door_codes: 1`, `push: 1`, `guide_import: 1`. Door codes are issued on booking events; the sweep is a safety net. Guide import is a reconciliation of already-imported guides. Production logs on 2026-10-31 show zero work on almost every run. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) step 1.
## 3. Files
`App/app/scheduler.py` (only `job_intervals()`), `App/tests/test_scheduler*.py` if a test pins the values, `docs/ENVIRONMENT.md` only if an env var is added (do not add one).
## 4. Steps
1. Set `door_codes` to 5 and `guide_import` to 60.
2. `grep -n "_job_push" -A 30 App/app/scheduler.py` and read what the push job sends. If it only retries failed pushes, set `push` to 5. If it delivers first-time guest notifications, leave it at 1 and say so in the report.
3. Run the test-map row for `scheduler.py`.
## 5. Do not touch
Any job function body, cron hours, `config.py`, env vars.
## 6. Commands
`cd App && .venv/bin/python -m pytest tests/test_scheduler*.py -q --tb=short -x 2>&1 | tail -30`
## 7. Acceptance
Tests for the changed row pass. The admin Operations page still marks a job late at twice its interval (it reads `job_intervals()`, so no change needed; confirm by reading, not by running the app).
## 8. Stop and ask
Stop if `push` delivers first-time guest notifications and the owner has not said 5 min is fine; leave it at 1 and report.
## 9. Report
`docs/tasks/0457-report.md`: the three values, what `push` does, test output tail.
