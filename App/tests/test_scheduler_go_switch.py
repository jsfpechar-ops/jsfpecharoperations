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

from app import alerts, config, db, scheduler

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


def test_the_kill_switch_also_stops_the_watch(monkeypatch):
    # UBYHOST_ENABLE_SCHEDULER=0: start() returns before anything, so no
    # go_watch either; Go refuses the same value (TestKillSwitchStopsTheGoScheduler).
    monkeypatch.setenv("UBYHOST_SCHEDULER", "go")
    _all_queued(monkeypatch)
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", False)
    assert scheduler.start() is False
    assert scheduler._scheduler is None


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
    yield
    db.execute("DELETE FROM job")
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (scheduler.GO_WATCH_ALERT,))


def _stamp(moment):
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _go_row(kind, created, done=True):
    """A row as the Go scheduler writes it (payload '{}'), finished by its consumer."""
    db.execute(
        "INSERT INTO job (kind, run_at, payload, done_at, created_at) VALUES (?, ?, '{}', ?, ?)",
        (kind, created, created if done else None, created),
    )


def _go_fresh(now, skip=()):
    """Go is healthy: every kind has a row a minute old (daily ones too)."""
    for kind in scheduler.JOB_KINDS:
        if kind not in skip:
            _go_row(kind, _stamp(now - timedelta(minutes=1)))


def _finish_all():
    db.execute("UPDATE job SET done_at = created_at WHERE done_at IS NULL")


def _watch_rows(kind=None):
    sql = "SELECT COUNT(*) AS n FROM job WHERE payload = ?"
    args = [scheduler.GO_WATCH_PAYLOAD]
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    return db.query_one(sql, tuple(args))["n"]


def _alert():
    return alerts.open_alert(scheduler.GO_WATCH_ALERT)


def test_watch_with_go_healthy_enqueues_nothing(watch_db):
    now = datetime.now(timezone.utc)
    _go_fresh(now)
    assert scheduler.watch_go_scheduler(now) == []
    assert _watch_rows() == 0
    assert _alert() is None


def test_go_silent_takes_over_on_the_normal_schedule_and_alerts(watch_db):
    now = datetime.now(timezone.utc)
    for kind in scheduler.JOB_KINDS:
        _go_row(kind, _stamp(now - timedelta(days=3)))
    assert sorted(scheduler.watch_go_scheduler(now)) == sorted(scheduler.JOB_KINDS)
    alert = _alert()
    assert alert is not None and alert["level"] == "critical" and alert["kind"] == "job_failed"
    assert alert["message"].startswith(scheduler.GO_WATCH_MESSAGE)
    assert "check that the ubyhost-go container is running" in alert["message"]
    # One open row per kind: the same pass again adds nothing.
    assert scheduler.watch_go_scheduler(now) == []
    # Five minutes on, with the rows run: the 1- and 5-minute kinds again,
    # nothing slower (normal schedule, not twice the interval).
    _finish_all()
    later = datetime.now(timezone.utc) + timedelta(minutes=5, seconds=1)
    assert sorted(scheduler.watch_go_scheduler(later)) == ["door_codes", "mail", "push"]
    assert _alert() is not None


def test_hand_back_to_go_resolves_and_stops_the_takeover(watch_db):
    now = datetime.now(timezone.utc)
    for kind in scheduler.JOB_KINDS:
        _go_row(kind, _stamp(now - timedelta(days=3)))
    scheduler.watch_go_scheduler(now)
    _finish_all()
    later = datetime.now(timezone.utc) + timedelta(minutes=5, seconds=1)
    _go_fresh(later)  # Go writes again
    assert scheduler.watch_go_scheduler(later) == []
    assert _alert() is None


def test_a_worker_restart_does_not_leave_the_alert_open(watch_db):
    # The alert was raised by a worker process that is gone; this one has
    # no memory of it. Go is healthy: the first pass closes the alert.
    alerts.raise_alert("critical", "job_failed", f"{scheduler.GO_WATCH_MESSAGE} any job.", "", dedupe_key=scheduler.GO_WATCH_ALERT)
    now = datetime.now(timezone.utc)
    _go_fresh(now)
    assert scheduler.watch_go_scheduler(now) == []
    assert _alert() is None


def test_a_job_queue_failure_alert_is_left_alone(watch_db):
    # The same card from a failing drain (scheduler._job_failed) is not ours to close.
    alerts.raise_alert("warning", "job_failed", "Background job 'job queue' failed.", "", dedupe_key=scheduler.GO_WATCH_ALERT)
    now = datetime.now(timezone.utc)
    _go_fresh(now)
    assert scheduler.watch_go_scheduler(now) == []
    assert _alert() is not None


def test_go_restart_across_a_daily_time_one_fallback_then_resolved(watch_db):
    now = datetime.now(timezone.utc)
    _go_fresh(now, skip={"billing"})
    due = datetime.fromisoformat(scheduler._go_due_since("billing", now))
    _go_row("billing", _stamp(due - timedelta(days=1)))  # Go was down at the last 06:00
    assert scheduler.watch_go_scheduler(now) == ["billing"]
    assert _watch_rows("billing") == 1 and _alert() is not None
    _finish_all()  # the billing run is done
    assert scheduler.watch_go_scheduler(now + timedelta(minutes=1)) == []
    assert _watch_rows("billing") == 1
    assert _alert() is None


def test_watch_waits_for_open_rows_and_long_runs(watch_db):
    now = datetime.now(timezone.utc)
    _go_fresh(now, skip={"ical", "submit"})
    old = _stamp(now - timedelta(days=3))
    _go_row("ical", old, done=False)  # still open: the queue's own stuck check covers it
    db.execute(
        "INSERT INTO job (kind, run_at, payload, done_at, created_at) VALUES ('submit', ?, '{}', ?, ?)",
        (old, _stamp(now - timedelta(minutes=5)), old),
    )  # a long run that finished 5 minutes ago counts as fresh while Go runs
    assert scheduler.watch_go_scheduler(now) == []


def test_watch_daily_job_waits_for_its_grace(watch_db):
    prague = ZoneInfo(config.TIMEZONE)
    now_local = datetime.now(prague)
    yesterday = (now_local - timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
    today_due = yesterday + timedelta(days=1)  # 06:00 local today (wall clock)
    in_grace = today_due + timedelta(minutes=scheduler.GO_WATCH_CRON_GRACE_MINUTES - 1)
    past_grace = today_due + timedelta(minutes=scheduler.GO_WATCH_CRON_GRACE_MINUTES + 1)
    _go_fresh(past_grace.astimezone(timezone.utc), skip={"billing"})
    _go_row("billing", _stamp(yesterday))
    assert "billing" not in scheduler.watch_go_scheduler(in_grace.astimezone(timezone.utc))
    assert "billing" in scheduler.watch_go_scheduler(past_grace.astimezone(timezone.utc))
