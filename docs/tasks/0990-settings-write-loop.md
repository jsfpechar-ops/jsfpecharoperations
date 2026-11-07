# 0990: stop the settings write loop (job_last_ok heartbeat)

Status: todo
Depends on: none | Base commit: origin/main at branch creation | Branch: claude/zealous-planck-raxu4v (stay on it)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`scheduler._job_ok` writes one `settings` row (`job_last_ok:<job>`) after every successful run of every background job, so the `settings` table gets about 2,200 UPDATEs a day (production: 13,347 updates in 6 days on 40 rows) and bloats Postgres for no benefit. Write the heartbeat only when the stored one is older than 15 minutes, for jobs that run more often than every 15 minutes, and widen the admin "late" threshold by the same 15 minutes so the Operations page stays correct.

## 2. Context

Culprit (found by grep of every `set_setting` caller; the other callers are user-driven or daily):

`App/app/scheduler.py:106-115`
```python
JOB_LAST_OK_PREFIX = "job_last_ok:"


def _job_ok(job_id: str) -> None:
    alerts.resolve(f"job_failed:{job_id}")
    # Nothing else records a successful run, and a scheduler that silently
    # stopped looks exactly like one with nothing to do (WP10).
    try:
        db.set_setting(f"{JOB_LAST_OK_PREFIX}{job_id}", db.utcnow())
    except Exception:
        log.warning("could not record the last success of job %s", job_id, exc_info=True)
```
`_job_ok` is called at the end of every job (scheduler.py lines ~149-482). Intervals (`job_intervals()`, scheduler.py:82): push 1 min, mail 5, door_codes 5, deadlines 30, meta_capi 10, submit 10 (SUBMIT_SWEEP_MINUTES default), posthog 15, ical 60 (ICAL_POLL_MINUTES default), guide_import 60, others daily. push alone is 1,440 writes/day; mail and door_codes 288 each. Together about 2,200/day, which matches production.

The only reader is `App/app/admin_ops.py:203-232` (`job_health`), which calls a job late when `age > 2 * minutes`:
```python
                "late": age is None or age > 2 * minutes,
```
`last_ical_sync` (icalsync.py:1052) is a different key, written once per ical run (hourly): leave it. `job_queue` (every 15 s) does not call `_job_ok`: leave it. `job_failed` alert resolve stays on every run (it is an UPDATE only while an alert is open).

Why not `WHERE value IS DISTINCT FROM`: the value is a fresh timestamp each time, so it always differs. The write must be throttled by age instead. The throttle reads the stored value first (a cheap index read, stateless, correct across processes and tests); it uses no new SQL, so Postgres portability is unchanged.

Rules that apply: SQL only through db helpers (we use `db.get_setting`); no new dependency; no schema change; never break the health check (the slack below keeps the late rule safe).

If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/scheduler.py | edit | import datetime; add throttle constant and helpers; use them in `_job_ok` |
| App/app/admin_ops.py | edit | late threshold uses `scheduler.late_after_minutes(minutes)` |
| App/tests/test_admin_operations.py | edit | one number (11 -> 30) in the existing late test |
| App/tests/test_job_ok_throttle.py | new | focused tests: no write inside the window, write after it, late slack |
| docs/tasks/0990-report.md | new | the report |

No other file may change. This brief does not touch App/app/db.py, App/migrations_pg/ (0991) or any page Cache-Control code (0992).

## 4. Steps

1. Confirm the branch. Run `cd /home/user/jsfpecharoperations && git branch --show-current | tail -30`. Expected: `claude/zealous-planck-raxu4v`. Set `Status: in-progress` on line 3 of this brief.

2. In `App/app/scheduler.py`, add the import. Find:
```python
import fcntl
import functools
```
Replace with:
```python
import fcntl
import functools
from datetime import datetime, timezone
```
Check: `grep -n "^from datetime" App/app/scheduler.py | tail -30` prints exactly one line. If scheduler.py already imports datetime elsewhere, STOP.

3. In `App/app/scheduler.py`, replace the whole `_job_ok` block. Find exactly:
```python
JOB_LAST_OK_PREFIX = "job_last_ok:"


def _job_ok(job_id: str) -> None:
    alerts.resolve(f"job_failed:{job_id}")
    # Nothing else records a successful run, and a scheduler that silently
    # stopped looks exactly like one with nothing to do (WP10).
    try:
        db.set_setting(f"{JOB_LAST_OK_PREFIX}{job_id}", db.utcnow())
    except Exception:
        log.warning("could not record the last success of job %s", job_id, exc_info=True)
```
Replace with:
```python
JOB_LAST_OK_PREFIX = "job_last_ok:"

# A job that runs more often than this records its last success at most once
# per window. Writing every run turned the settings table into a hot table
# (about 2,200 updates a day, 0990). The Operations page adds the same window
# to its late threshold, see ``late_after_minutes``.
LAST_OK_WRITE_MINUTES = 15


def late_after_minutes(interval_minutes: int) -> int:
    """Age in minutes after which a job's last success counts as late."""
    slack = LAST_OK_WRITE_MINUTES if interval_minutes < LAST_OK_WRITE_MINUTES else 0
    return 2 * interval_minutes + slack


def _last_ok_is_fresh(job_id: str, key: str) -> bool:
    """True when the stored success is younger than the write window."""
    minutes = job_intervals().get(job_id)
    if minutes is None or minutes >= LAST_OK_WRITE_MINUTES:
        return False
    stored = db.get_setting(key)
    if not stored:
        return False
    try:
        parsed = datetime.fromisoformat(stored)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - parsed).total_seconds()
    return 0 <= age < LAST_OK_WRITE_MINUTES * 60


def _job_ok(job_id: str) -> None:
    alerts.resolve(f"job_failed:{job_id}")
    # Nothing else records a successful run, and a scheduler that silently
    # stopped looks exactly like one with nothing to do (WP10).
    key = f"{JOB_LAST_OK_PREFIX}{job_id}"
    try:
        if _last_ok_is_fresh(job_id, key):
            return
        db.set_setting(key, db.utcnow())
    except Exception:
        log.warning("could not record the last success of job %s", job_id, exc_info=True)
```
Check: `cd App && .venv/bin/python -c "from app import scheduler; print(scheduler.late_after_minutes(5), scheduler.late_after_minutes(60))" 2>&1 | tail -30`. Expected: `25 120`.

4. In `App/app/admin_ops.py`, find exactly:
```python
                "late": age is None or age > 2 * minutes,
```
Replace with:
```python
                "late": age is None or age > scheduler.late_after_minutes(minutes),
```
Check: `grep -n "late_after_minutes" App/app/admin_ops.py | tail -30` prints one line (`scheduler` is already imported there; it is used at line 205).

5. In `App/tests/test_admin_operations.py`, in `test_job_ok_records_the_last_success_and_late_jobs_show`, find exactly:
```python
    old = (datetime.now(timezone.utc) - timedelta(minutes=11)).replace(microsecond=0).isoformat()
```
Replace with:
```python
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).replace(microsecond=0).isoformat()
```
Find exactly:
```python
    assert rows["mail"]["late"] is True  # 11 min > 2 x 5 min
```
Replace with:
```python
    assert rows["mail"]["late"] is True  # 30 min > 2 x 5 min + 15 min write window
```

6. Create `App/tests/test_job_ok_throttle.py` with exactly:
```python
"""0990: the last-success heartbeat must not rewrite its row on every run."""
from datetime import datetime, timedelta, timezone

from app import db, scheduler


def _stamp(minutes_ago: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.replace(microsecond=0).isoformat()


def _count_writes(monkeypatch):
    writes = []
    real = db.set_setting

    def spy(key, value):
        writes.append(key)
        return real(key, value)

    monkeypatch.setattr(db, "set_setting", spy)
    return writes


def test_a_fresh_heartbeat_is_not_rewritten(monkeypatch):
    key = scheduler.JOB_LAST_OK_PREFIX + "push"
    db.set_setting(key, _stamp(1))
    writes = _count_writes(monkeypatch)
    for _ in range(5):
        scheduler._job_ok("push")
    assert writes == []
    assert db.get_setting(key)


def test_a_stale_or_missing_heartbeat_is_written_once(monkeypatch):
    key = scheduler.JOB_LAST_OK_PREFIX + "push"
    db.set_setting(key, _stamp(20))
    writes = _count_writes(monkeypatch)
    scheduler._job_ok("push")
    scheduler._job_ok("push")
    assert writes == [key]
    db.set_setting(key, "")
    writes.clear()
    scheduler._job_ok("push")
    assert writes == [key]


def test_a_slow_job_always_writes(monkeypatch):
    key = scheduler.JOB_LAST_OK_PREFIX + "guide_import"
    db.set_setting(key, _stamp(1))
    writes = _count_writes(monkeypatch)
    scheduler._job_ok("guide_import")
    assert writes == [key]


def test_the_late_threshold_includes_the_write_window():
    assert scheduler.late_after_minutes(1) == 2 + scheduler.LAST_OK_WRITE_MINUTES
    assert scheduler.late_after_minutes(5) == 10 + scheduler.LAST_OK_WRITE_MINUTES
    assert scheduler.late_after_minutes(15) == 30
    assert scheduler.late_after_minutes(60) == 120
```
If the new tests fail because the default test database needs a private path, copy the `_private_db(monkeypatch, tmp_path)` helper from `App/tests/test_scheduler.py` (lines 22-24) into the new file and call it at the start of each test with `tmp_path`; nothing else may change.

7. Run the tests (§6). Expected: all pass.

8. Commit and push (no PR). Run:
```
cd /home/user/jsfpecharoperations && git add App/app/scheduler.py App/app/admin_ops.py App/tests/test_admin_operations.py App/tests/test_job_ok_throttle.py docs/tasks/0990-settings-write-loop.md docs/tasks/0990-report.md && git commit -F - <<'MSG' 2>&1 | tail -30
Throttle the job_last_ok heartbeat writes to the settings table

Fast jobs now record their last success at most every 15 minutes, and the
Operations late threshold grows by the same window.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8K21RfgG5itpXC8Mic
MSG
git push -u origin claude/zealous-planck-raxu4v 2>&1 | tail -30
```
Expected: a commit line, then the branch pushed. If the push is refused, STOP and report (do not force).

9. Write `docs/tasks/0990-report.md` per §9 (do this before step 8's `git add`, then set `Status: review` on this brief's line 3 and amend nothing: do steps 9 and the status edit first, commit once).

## 5. Do not touch

- `App/app/db.py`, `App/migrations_pg/`, anything about Cache-Control (briefs 0991 and 0992 own them).
- `last_ical_sync`, `job_queue`, `alerts.resolve`, `set_setting` itself, the daily jobs.
- Hard rules 3, 4, 5, 8: no secrets, no new dependency, SQL only via db helpers, no PR, never push to main.

## 6. Commands

From `App/`:
`.venv/bin/python -m pytest tests/test_job_ok_throttle.py tests/test_scheduler.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -30`
Expected: all passed, 0 failed, 0 skipped. CI `test-postgres-full` re-runs these on Postgres; nothing here is backend specific.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no new error.

## 7. Acceptance

- [ ] `grep -n "LAST_OK_WRITE_MINUTES" App/app/scheduler.py | tail -30` shows the constant and its uses.
- [ ] The three test files in §6 pass with 0 skipped.
- [ ] `git diff --stat origin/main | tail -30` lists only the §3 files.
- [ ] Branch pushed, no PR opened.

## 8. Stop and ask

Stop, and write the report as `blocked`, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens;
- a file outside §3 needs a change;
- the push is refused.

## 9. Report

Write `docs/tasks/0990-report.md` (600 tokens at most), Status: review: files changed (`git diff --stat`), each command with the last 5 lines of output, §7 ticked, deviations, questions.

## Risk list (for the reviewer)

- `App/app/scheduler.py` `_job_ok` and helpers: a job that fails the read must still not crash (the try/except covers it).
- `App/app/admin_ops.py` late rule: check that fast jobs are late after 2 x interval + 15 min and slow jobs unchanged.

## Owner steps

After merge and deploy: wait a day, then in Postgres check `SELECT n_tup_upd FROM pg_stat_user_tables WHERE relname = 'settings';` twice, 24 h apart. Expected: about 400 or fewer new updates a day (was about 2,200). The Operations page should show no job as late.
