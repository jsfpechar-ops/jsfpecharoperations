"""UBYHOST_SCHEDULER=go: the Go service enqueues every job, Python none (J7).

``conftest.py`` disables the scheduler for the whole suite, so these tests
start one directly, as test_scheduler.py does. They only read the job list
APScheduler holds; the drain job's first run is 20 s away, so nothing runs
and no PostgreSQL is needed.
"""
import pytest

from app import config, scheduler


def _all_queued(monkeypatch, kinds=None):
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    monkeypatch.setattr(config, "DB_BACKEND", "postgresql")
    monkeypatch.setattr(config, "JOB_QUEUE_KINDS", frozenset(kinds if kinds is not None else scheduler.JOB_KINDS))
    monkeypatch.setattr(config, "GO_JOB_KINDS", frozenset({"deadlines"}))


def _job_ids():
    return sorted(job.id for job in scheduler._scheduler.get_jobs())


def test_go_scheduler_reads_the_switch(monkeypatch):
    # The same values as go/internal/scheduler TestEnabled.
    for value, want in {"go": True, " Go ": True, "GO": True, "": False, "python": False, "1": False, "go,python": False}.items():
        monkeypatch.setenv("UBYHOST_SCHEDULER", value)
        assert scheduler.go_scheduler() is want, value
    monkeypatch.delenv("UBYHOST_SCHEDULER")
    assert scheduler.go_scheduler() is False


def test_without_the_switch_python_enqueues_every_kind(monkeypatch):
    monkeypatch.delenv("UBYHOST_SCHEDULER", raising=False)
    _all_queued(monkeypatch)
    try:
        assert scheduler.start() is True
        assert _job_ids() == sorted([*scheduler.JOB_KINDS, "job_queue"])
    finally:
        scheduler.shutdown()


def test_with_the_switch_python_only_drains_the_queue(monkeypatch):
    monkeypatch.setenv("UBYHOST_SCHEDULER", "go")
    _all_queued(monkeypatch)
    try:
        assert scheduler.start() is True
        assert _job_ids() == ["job_queue"]
        assert scheduler.running()
    finally:
        scheduler.shutdown()


def test_the_switch_needs_every_kind_on_the_queue(monkeypatch):
    monkeypatch.setenv("UBYHOST_SCHEDULER", "go")
    _all_queued(monkeypatch, set(scheduler.JOB_KINDS) - {"door_codes"})
    with pytest.raises(RuntimeError, match="missing: door_codes"):
        scheduler.start()
    assert scheduler._scheduler is None
