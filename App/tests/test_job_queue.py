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


def test_unset_setting_registers_the_wrappers_unchanged(monkeypatch):
    if ON_POSTGRES:
        pytest.skip("SQLite registration rules")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset())
    monkeypatch.setattr(scheduler, "_acquire_single_instance_lock", lambda: True)
    assert scheduler.start() is True
    try:
        jobs = {j.id: j for j in scheduler._scheduler.get_jobs()}
        assert "job_queue" not in jobs
        assert set(jobs) == set(scheduler.JOB_KINDS)
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
