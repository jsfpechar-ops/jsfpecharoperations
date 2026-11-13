"""UBYHOST_SCHEDULER=go: the Go service enqueues every job, Python none (J7).

``conftest.py`` disables the scheduler for the whole suite, so the start()
tests build one directly, as test_scheduler.py does, and only read the job
list APScheduler holds (no job is due within the test). The watch tests need
PostgreSQL (the job table) and skip without it, as test_job_queue.py does.
"""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app import alerts, config, db, jobqueue, scheduler

ON_POSTGRES = config.DB_BACKEND == "postgresql"


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


def test_with_the_switch_python_only_drains_and_watches(monkeypatch):
    monkeypatch.setenv("UBYHOST_SCHEDULER", "go")
    _all_queued(monkeypatch)
    try:
        assert scheduler.start() is True
        assert _job_ids() == ["go_watch", "job_queue"]
        assert scheduler.running()
    finally:
        scheduler.shutdown()


@pytest.mark.parametrize(
    "kinds, minutes, problem",
    [
        ("all but door_codes", 10, "missing: door_codes"),
        ("all", 0, "UBYHOST_SUBMIT_SWEEP_MINUTES must be a whole number of minutes above 0"),
        ("all", -5, "UBYHOST_SUBMIT_SWEEP_MINUTES must be a whole number of minutes above 0"),
    ],
)
def test_a_switch_go_cannot_use_is_ignored_and_python_enqueues(monkeypatch, caplog, kinds, minutes, problem):
    # go/internal/scheduler Setup refuses the same configurations
    # (TestSetupNeedsEveryKindQueued, TestPlanReadsTheTwoIntervals), so
    # exactly one side enqueues.
    monkeypatch.setenv("UBYHOST_SCHEDULER", "go")
    queued = set(scheduler.JOB_KINDS) - ({"door_codes"} if kinds != "all" else set())
    _all_queued(monkeypatch, queued)
    monkeypatch.setattr(config, "SUBMIT_SWEEP_MINUTES", minutes)
    assert problem in scheduler.go_scheduler_problem()
    assert scheduler.go_enqueues() is False
    if minutes <= 0:
        return  # APScheduler would schedule a 0 or negative interval; only the decision is checked
    try:
        assert scheduler.start() is True
        assert set(scheduler.JOB_KINDS) <= set(_job_ids())
        assert "go_watch" not in _job_ids()
        assert "UBYHOST_SCHEDULER=go is ignored" in caplog.text
    finally:
        scheduler.shutdown()


def test_cron_times_match_start(monkeypatch):
    monkeypatch.delenv("UBYHOST_SCHEDULER", raising=False)
    _all_queued(monkeypatch)
    try:
        scheduler.start()
        for kind, (hour, minute) in scheduler.CRON_TIMES.items():
            fields = {f.name: str(f) for f in scheduler._scheduler.get_job(kind).trigger.fields}
            assert (fields["hour"], fields["minute"]) == (str(hour), str(minute)), kind
    finally:
        scheduler.shutdown()


# --- the watch: PostgreSQL only -------------------------------------------------


@pytest.fixture
def watch_db(monkeypatch):
    if not ON_POSTGRES:
        pytest.skip("the Go scheduler watch needs UBYHOST_DATABASE_URL on a test database")
    url = os.environ.get("UBYHOST_DATABASE_URL", "")
    if "test" not in url.rsplit("/", 1)[-1]:
        pytest.fail("refusing to clear the job table: the database name has no 'test'")
    db.apply_postgresql_schema()
    monkeypatch.setenv("UBYHOST_SCHEDULER", "go")
    _all_queued(monkeypatch)
    db.execute("DELETE FROM job")
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (scheduler.GO_WATCH_ALERT,))
    scheduler._go_fallback.clear()
    yield
    scheduler._go_fallback.clear()
    db.execute("DELETE FROM job")
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (scheduler.GO_WATCH_ALERT,))


def _go_row(kind, created, done=True):
    """A row as the Go scheduler writes it, finished by its consumer."""
    db.execute(
        "INSERT INTO job (kind, run_at, payload, done_at, created_at) VALUES (?, ?, '{}', ?, ?)",
        (kind, created, created if done else None, created),
    )


def _count(kind=None):
    if kind:
        return db.query_one("SELECT COUNT(*) AS n FROM job WHERE kind = ?", (kind,))["n"]
    return db.query_one("SELECT COUNT(*) AS n FROM job")["n"]


def _alert():
    return alerts.open_alert(scheduler.GO_WATCH_ALERT)


def _stamp(moment):
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def test_watch_with_go_healthy_enqueues_nothing(watch_db):
    now = datetime.now(timezone.utc)
    for kind in scheduler.JOB_KINDS:
        if kind in scheduler.CRON_TIMES:
            # the last local cron time, as Go writes it
            due = scheduler._go_due_since(kind, now + timedelta(minutes=scheduler.GO_WATCH_CRON_GRACE_MINUTES))
            _go_row(kind, due)
        else:
            _go_row(kind, _stamp(now - timedelta(minutes=scheduler.job_intervals()[kind])))
    before = _count()
    assert scheduler.watch_go_scheduler(now) == []
    assert _count() == before
    assert _alert() is None


def test_watch_with_go_silent_enqueues_and_alerts_until_go_is_back(watch_db):
    now = datetime.now(timezone.utc)
    old = _stamp(now - timedelta(days=3))
    for kind in scheduler.JOB_KINDS:
        _go_row(kind, old)
    added = scheduler.watch_go_scheduler(now)
    assert sorted(added) == sorted(scheduler.JOB_KINDS)
    assert _count() == 2 * len(scheduler.JOB_KINDS)
    alert = _alert()
    assert alert is not None and alert["level"] == "critical" and alert["kind"] == "job_failed"
    assert "submit" in alert["message"] and "door_codes" in alert["message"]
    # One open row per kind: a second pass adds nothing, the alert stays.
    assert scheduler.watch_go_scheduler(now) == []
    assert _count() == 2 * len(scheduler.JOB_KINDS)
    assert _alert() is not None
    # Go writes again: the consumer finished the Python rows, Go adds newer ones.
    db.execute("UPDATE job SET done_at = created_at WHERE done_at IS NULL")
    later = _stamp(datetime.now(timezone.utc) + timedelta(seconds=5))
    for kind in scheduler.JOB_KINDS:
        _go_row(kind, later)
    assert scheduler.watch_go_scheduler(now) == []
    assert _alert() is None
    assert scheduler._go_fallback == {}


def test_watch_waits_for_open_rows_and_long_runs(watch_db):
    now = datetime.now(timezone.utc)
    old = _stamp(now - timedelta(days=3))
    _go_row("ical", old, done=False)  # still open: the queue's own stuck check covers it
    db.execute(
        "INSERT INTO job (kind, run_at, payload, done_at, created_at) VALUES ('submit', ?, '{}', ?, ?)",
        (old, _stamp(now - timedelta(minutes=5)), old),
    )  # a long run that finished 5 minutes ago counts as fresh
    added = scheduler.watch_go_scheduler(now)
    assert "ical" not in added and "submit" not in added
    assert _count("ical") == 1 and _count("submit") == 1


def test_watch_daily_job_waits_for_its_grace(watch_db):
    prague = ZoneInfo(config.TIMEZONE)
    now_local = datetime.now(prague)
    yesterday = (now_local - timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
    today_due = yesterday + timedelta(days=1)  # 06:00 local today (wall clock)
    _go_row("billing", _stamp(yesterday))
    in_grace = today_due + timedelta(minutes=scheduler.GO_WATCH_CRON_GRACE_MINUTES - 1)
    assert "billing" not in scheduler.watch_go_scheduler(in_grace.astimezone(timezone.utc))
    assert _count("billing") == 1
    past_grace = today_due + timedelta(minutes=scheduler.GO_WATCH_CRON_GRACE_MINUTES + 1)
    assert "billing" in scheduler.watch_go_scheduler(past_grace.astimezone(timezone.utc))
    assert _count("billing") == 2
