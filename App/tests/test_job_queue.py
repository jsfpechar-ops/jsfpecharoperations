"""Job queue (0467 part a): SQLite registration rules, then PostgreSQL row lifecycle."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from app import config, db, jobqueue, scheduler

ON_POSTGRES = config.DB_BACKEND == "postgresql"
needs_postgres = pytest.mark.skipif(
    not ON_POSTGRES,
    reason="PostgreSQL job queue tests need UBYHOST_DATABASE_URL on a test database",
)


@pytest.fixture
def job_db():
    """A clean job table on the disposable PostgreSQL test database."""
    if not ON_POSTGRES:
        pytest.skip("PostgreSQL job queue tests need UBYHOST_DATABASE_URL")
    url = os.environ.get("UBYHOST_DATABASE_URL", "")
    if "test" not in url.rsplit("/", 1)[-1]:
        pytest.fail("refusing to clear the job table: the database name has no 'test'")
    db.apply_postgresql_schema()
    db.execute("DELETE FROM job")
    yield
    db.execute("DELETE FROM job")


def _insert(kind, run_at=None, locked_at=None, locked_by=None, done_at=None, attempts=0):
    db.execute(
        "INSERT INTO job (kind, run_at, payload, attempts, locked_at, locked_by, done_at, created_at) "
        "VALUES (?, ?, '{}', ?, ?, ?, ?, ?)",
        (
            kind,
            run_at or jobqueue._stamp(),
            attempts,
            locked_at,
            locked_by,
            done_at,
            jobqueue._stamp(),
        ),
    )


def _rows(kind):
    return [dict(r) for r in db.query("SELECT * FROM job WHERE kind = ? ORDER BY id", (kind,))]


# --- SQLite: registration rules (always run) -----------------------------------


def test_unknown_queue_kind_raises_before_anything_starts(monkeypatch):
    if ON_POSTGRES:
        pytest.skip("SQLite registration rules")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"no_such_job"}))
    with pytest.raises(RuntimeError, match="unknown kinds"):
        scheduler.start()


def test_queue_setting_on_sqlite_raises(monkeypatch):
    if ON_POSTGRES:
        pytest.skip("SQLite registration rules")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"push"}))
    with pytest.raises(RuntimeError, match="needs PostgreSQL"):
        scheduler.start()


def test_unset_setting_registers_the_wrappers_unchanged(monkeypatch, caplog):
    if ON_POSTGRES:
        pytest.skip("SQLite registration rules")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset())
    monkeypatch.setattr(scheduler, "_acquire_single_instance_lock", lambda: True)
    with caplog.at_level("WARNING", logger=scheduler.log.name):
        assert scheduler.start() is True
    try:
        jobs = {j.id: j for j in scheduler._scheduler.get_jobs()}
        assert "job_queue" not in jobs
        # 1200: no Go service on SQLite, so deadlines is not scheduled, and says so.
        assert set(jobs) == set(scheduler.JOB_KINDS) - {"deadlines"}
        assert "no deadline watch runs here" in caplog.text
        for kind, job in jobs.items():
            assert job.func is scheduler.JOB_KINDS[kind]
    finally:
        scheduler.shutdown()


def test_every_scheduled_job_has_a_warning_or_critical_level():
    assert set(scheduler.JOB_KINDS) | {"job_queue"} <= set(scheduler._JOB_LEVELS)


# --- PostgreSQL: row lifecycle --------------------------------------------------


@needs_postgres
def test_enqueue_twice_keeps_one_open_row(job_db):
    assert jobqueue.enqueue("push") is True
    assert jobqueue.enqueue("push") is False
    assert len(_rows("push")) == 1


@needs_postgres
def test_two_claims_at_once_return_one_row(job_db):
    _insert("push")
    barrier = threading.Barrier(2)

    def grab():
        barrier.wait()
        return jobqueue.claim()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: grab(), range(2)))
    assert sum(1 for r in results if r is not None) == 1


@needs_postgres
def test_failures_back_off_then_die_and_alert(job_db, monkeypatch):
    alerts = []
    monkeypatch.setattr(
        scheduler.alerts, "raise_alert", lambda *args, **kwargs: alerts.append(args)
    )
    jobqueue.enqueue("push")

    def boom(kind):
        raise ValueError("nope")

    for attempt in range(1, jobqueue.MAX_ATTEMPTS + 1):
        if attempt > 1:
            db.execute("UPDATE job SET run_at = ? WHERE kind = 'push'", (jobqueue._stamp(-timedelta(minutes=1)),))
        assert jobqueue.drain(boom, threading.Event()) == 1
        row = _rows("push")[0]
        assert row["attempts"] == attempt
        assert row["locked_at"] is None and row["locked_by"] is None
        if attempt == 1:
            assert row["done_at"] is None and row["dead_at"] is None
            assert row["run_at"] > jobqueue._stamp(timedelta(seconds=30))

    row = _rows("push")[0]
    assert row["dead_at"] is not None
    assert any("job_failed" in str(a) for a in alerts)
    assert jobqueue.enqueue("push") is True
    assert len(_rows("push")) == 2


@needs_postgres
def test_expired_lease_is_claimed_by_another_worker(job_db):
    _insert(
        "push",
        locked_at=jobqueue._stamp(-timedelta(minutes=61)),
        locked_by="other-host:1",
        attempts=1,
    )
    row = jobqueue.claim()
    assert row is not None
    assert row["attempts"] == 2
    assert _rows("push")[0]["locked_by"] == jobqueue.WORKER_ID


@needs_postgres
def test_finish_with_a_foreign_lease_changes_nothing(job_db):
    _insert("push", locked_at=jobqueue._stamp(), locked_by="other-host:1", attempts=1)
    job_id = _rows("push")[0]["id"]
    jobqueue.finish(job_id)
    assert _rows("push")[0]["done_at"] is None


@needs_postgres
def test_drain_stops_when_stop_is_set(job_db):
    _insert("push")
    stop = threading.Event()
    stop.set()
    assert jobqueue.drain(lambda kind: None, stop) == 0
    assert _rows("push")[0]["attempts"] == 0


@needs_postgres
def test_purge_removes_only_rows_older_than_seven_days(job_db):
    _insert("push", done_at=jobqueue._stamp(-timedelta(days=8)))
    _insert("mail", done_at=jobqueue._stamp(-timedelta(days=6)))
    assert jobqueue.purge() == 1
    assert _rows("push") == []
    assert len(_rows("mail")) == 1


@needs_postgres
def test_go_kinds_are_left_to_the_go_consumer(job_db, monkeypatch):
    monkeypatch.setattr(config, "GO_JOB_KINDS", frozenset({"billing_snapshot"}))
    _insert("billing_snapshot")
    _insert("push")
    job = jobqueue.claim()
    assert job is not None and job["kind"] == "push"
    assert jobqueue.claim() is None
    assert _rows("billing_snapshot")[0]["locked_at"] is None


def test_go_kind_outside_the_python_queue_refuses_to_start(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"push"}))
    monkeypatch.setattr(config, "GO_JOB_KINDS", frozenset({"billing_snapshot"}))
    with pytest.raises(RuntimeError, match="UBYHOST_GO_JOB_KINDS"):
        scheduler.start()


# --- PostgreSQL: the scheduler lock is skipped only when every kind is queued ---


def _start_with_lock_spy(monkeypatch, kinds):
    calls = []

    def spy():
        calls.append(1)
        return True

    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset(kinds))
    monkeypatch.setattr(scheduler, "_acquire_single_instance_lock", spy)
    return calls


@needs_postgres
def test_all_fifteen_kinds_queued_never_takes_the_scheduler_lock(job_db, monkeypatch):
    def must_not_be_called():
        raise AssertionError("scheduler.lock taken with every kind on the queue")

    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset(scheduler.JOB_KINDS))
    monkeypatch.setattr(scheduler, "_acquire_single_instance_lock", must_not_be_called)
    assert len(scheduler.JOB_KINDS) == 15
    assert scheduler.start() is True
    try:
        ids = {j.id for j in scheduler._scheduler.get_jobs()}
        assert "job_queue" in ids
        assert "deadlines" in ids  # 1200: on PostgreSQL it is still enqueued
    finally:
        scheduler.shutdown()


@needs_postgres
def test_fourteen_kinds_queued_still_takes_the_scheduler_lock_once(job_db, monkeypatch):
    calls = _start_with_lock_spy(monkeypatch, set(scheduler.JOB_KINDS) - {"push"})
    assert scheduler.start() is True
    try:
        assert calls == [1]
    finally:
        scheduler.shutdown()


def _clear_alert(kind):
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (f"job_failed:{kind}",))


@needs_postgres
def test_old_unclaimed_row_is_stuck_and_raises_the_job_failed_alert(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    monkeypatch.setattr(config, "GO_JOB_KINDS", frozenset({"deadlines"}))
    _insert("deadlines", run_at=jobqueue._stamp(-timedelta(hours=3)))
    _clear_alert("deadlines")
    try:
        assert jobqueue.stuck_kinds() == ["deadlines"]
        assert jobqueue.watch_stuck() == ["deadlines"]
        alert = db.query_one(
            "SELECT id FROM alert WHERE dedupe_key = 'job_failed:deadlines' AND resolved_at IS NULL"
        )
        assert alert is not None
    finally:
        _clear_alert("deadlines")


@needs_postgres
def test_fresh_row_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    _insert("deadlines")
    assert jobqueue.stuck_kinds() == []


@needs_postgres
def test_old_row_under_a_live_lease_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"deadlines"}))
    _insert(
        "deadlines",
        run_at=jobqueue._stamp(-timedelta(hours=3)),
        locked_at=jobqueue._stamp(),
        locked_by="other:1",
    )
    assert jobqueue.stuck_kinds() == []


@needs_postgres
def test_old_row_of_a_kind_off_the_queue_is_not_stuck(job_db, monkeypatch):
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset({"posthog"}))
    _insert("deadlines", run_at=jobqueue._stamp(-timedelta(hours=3)))
    assert jobqueue.stuck_kinds() == []


def test_drain_checks_for_stuck_rows_at_most_once_per_window(monkeypatch):
    calls = []
    monkeypatch.setattr(jobqueue, "watch_stuck", lambda: calls.append(1) or [])
    monkeypatch.setattr(jobqueue, "claim", lambda: None)
    monkeypatch.setattr(jobqueue, "_last_stuck_check", 0.0)
    assert jobqueue.drain(lambda kind: None, threading.Event()) == 0
    assert jobqueue.drain(lambda kind: None, threading.Event()) == 0
    assert calls == [1]


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
