# 0457 report: scheduler intervals

Branch: task/0457-job-intervals. The brief was missing from this branch; copied from commit 2a8063b (branch claude/project-thread-tmwhek) into docs/tasks/0457-job-intervals.md.

## Files changed
- App/app/scheduler.py (job_intervals() only)
- docs/tasks/0457-job-intervals.md (brief copied in, Status set to review)
- docs/tasks/0457-report.md

## Final values
- door_codes: 1 -> 5 (changed)
- guide_import: 1 -> 60 (changed)
- push: 1 (unchanged, see Questions)

## Step 2: what push does
_job_push() calls push.drain() and logs "urgent alerts that are due". The brief's grep (-A 30 of _job_push) does not show whether drain() sends first-time guest notifications or only retries. push.py is not named in the brief, so I did not open it. Left at 1 as the brief's safe default.

## Commands
- `cd App && .venv/bin/python -m pytest tests/test_scheduler*.py -q --tb=short -x 2>&1 | tail -30` (main checkout venv): `15 passed in 2.99s`
- Acceptance: App/app/admin_ops.py job_health() reads scheduler.job_intervals() (line 207), so no change needed. Confirmed by reading.
- App/tests/test_push.py:313 asserts job_intervals()["push"] == 1. Not in the brief's test row, not run. Still valid because push is unchanged.

## Deviations
Done: steps 1 to 3. Left: none.

## Questions
1. Does push.drain() deliver first-time guest notifications? If not, set push to 5 and update test_push.py:313. Owner decision needed.

## Owner steps left
- Review, then merge with scripts/merge-pr-on-green.sh.
