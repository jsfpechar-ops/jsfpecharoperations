# 1174 report

Status: review

## 1. Files changed (commits 2e13db2, 475170c, d7c5864)

- App/app/jobqueue.py: +58 (import time, STUCK_CHECK_SECONDS, _last_stuck_check, stuck_kinds, watch_stuck, throttled call in drain, docstring sentence)
- App/tests/test_job_queue.py: +57 (5 tests)
- docs/ENVIRONMENT.md: 1 line changed (UBYHOST_JOB_QUEUE_KINDS row)
- docs/tasks/1174-report.md: this file
- docs/tasks/1174-stuck-queue-alert.md is in `git diff 748098d HEAD` only because it was already on the branch; this executor did not edit it.

## 2. Commands

`cd App && .venv/bin/python -c "import app.jobqueue"`: no output, exit 0.

`.venv/bin/python -m pytest tests/test_job_queue.py tests/test_scheduler.py -q --tb=short -x -rs` (no UBYHOST_DATABASE_URL):
```
SKIPPED [1] tests/test_job_queue.py:279: PostgreSQL job queue tests need UBYHOST_DATABASE_URL on a test database
SKIPPED [1] tests/test_job_queue.py:291: PostgreSQL job queue tests need UBYHOST_DATABASE_URL on a test database
22 passed, 14 skipped in 2.66s
```

`UBYHOST_DATABASE_URL=postgresql://postgres:postgres@localhost/ubyhost_test .venv/bin/python -m pytest tests/test_job_queue.py tests/test_scheduler.py -q --tb=short -x -rs`:
```
SKIPPED [1] tests/test_job_queue.py:60: SQLite registration rules
SKIPPED [1] tests/test_job_queue.py:69: SQLite registration rules
SKIPPED [1] tests/test_job_queue.py:78: SQLite registration rules
33 passed, 3 skipped in 12.91s
```

`python3 scripts/context_lint.py` (repo root): last lines
```
next free: task 1175 | migration 0046
context lint: OK
```
Only pre-existing WARN lines; none for jobqueue.py, test_job_queue.py or the ENVIRONMENT.md change.

## 3. §7 acceptance

- [x] `def stuck_kinds` and `def watch_stuck` each found once in App/app/jobqueue.py
- [x] only the four §3 files changed by this work
- [x] §6 pytest ends with no failures (both runs)
- [x] watch_stuck has try/except Exception around its whole body
- [x] ENVIRONMENT.md sentence is on the UBYHOST_JOB_QUEUE_KINDS row only

## 4. Deviations

None from the brief's steps. Commits are split as "1174 step 1-3", "1174 step 4", "1174 step 5" (brief suggested step 4-5 for the last two).

## 5. Questions

- stuck_kinds() calls _require_postgres(); watch_stuck() catches that and logs an exception. drain() is only used with the Postgres queue, so this should not occur in production, but a sqlite run of drain() without the watch_stuck patch would log one exception every 5 minutes. Left as the brief specifies.

## 6. Owner steps left

- Review and merge the draft PR once CI is green (`scripts/merge-pr-on-green.sh`). Not pushed by the executor.
