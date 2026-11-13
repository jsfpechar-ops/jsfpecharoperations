# 1174b: stuck-queue check review fixes

Status: ready. Tier B. Follow-up to [1174](1174-stuck-queue-alert.md) from the independent review of PR #962.

## 1. Objective
1. No false alarm right after a deploy or worker restart: the first check runs 5 minutes after the process starts, and inside `drain` it runs after the claim loop, so rows Python itself owns are claimed first.
2. Daily cron kinds are flagged after at most 2 hours, not 48.

## 3. Files
- App/app/jobqueue.py
- App/tests/test_job_queue.py
- docs/tasks/1174b-report.md

## 4. Steps
**Step 1.** In App/app/jobqueue.py replace the line `_last_stuck_check = 0.0` with:

```python
STUCK_MAX_MINUTES = 120
# The first check waits one window after start, so a deploy's backlog is
# claimed before anything counts as stuck.
_last_stuck_check = time.monotonic()
```

**Step 2.** In `stuck_kinds`, replace

```python
        limit = _stamp(-timedelta(minutes=scheduler.late_after_minutes(intervals[kind])))
```

with

```python
        minutes = min(scheduler.late_after_minutes(intervals[kind]), STUCK_MAX_MINUTES)
        limit = _stamp(-timedelta(minutes=minutes))
```

and change its docstring to `"""Queued kinds with an open, unleased row older than twice the job interval (at most 2 h)."""`.

**Step 3.** In `drain`, delete these four lines from the top of the function:

```python
    global _last_stuck_check
    if time.monotonic() - _last_stuck_check >= STUCK_CHECK_SECONDS:
        _last_stuck_check = time.monotonic()
        watch_stuck()
```

Then insert, directly before the final `    return ran` of `drain`:

```python
    global _last_stuck_check
    if time.monotonic() - _last_stuck_check >= STUCK_CHECK_SECONDS:
        _last_stuck_check = time.monotonic()
        watch_stuck()
```

Move the `global _last_stuck_check` line to be the first line after the docstring of `drain` if Python reports `SyntaxError: name '_last_stuck_check' is used prior to global declaration` (it will not, since nothing above uses it, but check with the import command).

Run from App/: `.venv/bin/python -c "import app.jobqueue" 2>&1 | tail -30`.

**Step 4.** Append to App/tests/test_job_queue.py:

```python
@needs_postgres
def test_daily_kind_is_stuck_after_the_two_hour_cap(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"stripe_sweep"}))
    _insert("stripe_sweep", run_at=jobqueue._stamp(-timedelta(hours=3)))
    assert jobqueue.stuck_kinds() == ["stripe_sweep"]


@needs_postgres
def test_backoff_row_with_future_run_at_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    _insert("deadlines", run_at=jobqueue._stamp(timedelta(minutes=15)), attempts=2)
    assert jobqueue.stuck_kinds() == []


@needs_postgres
def test_old_row_with_an_expired_lease_is_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    _insert(
        "deadlines",
        run_at=jobqueue._stamp(-timedelta(hours=3)),
        locked_at=jobqueue._stamp(-timedelta(hours=2)),
        locked_by="gone:1",
    )
    assert jobqueue.stuck_kinds() == ["deadlines"]


def test_drain_checks_again_once_the_window_has_passed(monkeypatch):
    calls = []
    monkeypatch.setattr(jobqueue, "watch_stuck", lambda: calls.append(1) or [])
    monkeypatch.setattr(jobqueue, "claim", lambda: None)
    monkeypatch.setattr(jobqueue, "_last_stuck_check", 0.0)
    jobqueue.drain(lambda kind: None, threading.Event())
    monkeypatch.setattr(
        jobqueue, "_last_stuck_check", jobqueue.time.monotonic() - jobqueue.STUCK_CHECK_SECONDS - 1
    )
    jobqueue.drain(lambda kind: None, threading.Event())
    assert calls == [1, 1]


def test_drain_waits_one_window_after_start(monkeypatch):
    calls = []
    monkeypatch.setattr(jobqueue, "watch_stuck", lambda: calls.append(1) or [])
    monkeypatch.setattr(jobqueue, "claim", lambda: None)
    monkeypatch.setattr(jobqueue, "_last_stuck_check", jobqueue.time.monotonic())
    jobqueue.drain(lambda kind: None, threading.Event())
    assert calls == []
```

## 5. Do not touch
Everything outside §3. In particular App/app/scheduler.py, i18n files, go/.

## 6. Commands
From App/, twice (with and without `UBYHOST_DATABASE_URL=postgresql://postgres:postgres@localhost/ubyhost_test` in front):
`.venv/bin/python -m pytest tests/test_job_queue.py tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance
All tests pass in both runs; only §3 files changed. One commit `1174b: stuck check after claims, 2 h cap`.

## 8. Stop and ask
If an existing test fails because the first check now waits a window, stop and report it; do not change the old test.

## 9. Report
docs/tasks/1174b-report.md: what changed, both test counts, deviations.
