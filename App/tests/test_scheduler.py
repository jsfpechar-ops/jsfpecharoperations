"""The background jobs must actually run, and must not die silently.

``conftest.py`` disables the scheduler for the whole suite, so these tests build
one directly instead of relying on application startup.
"""
import pytest

from app import (
    claim,
    config,
    db,
    icalsync,
    passport_photos,
    reporting,
    retention,
    scheduler,
)


def _private_db(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "scheduler.sqlite3")
    db.init_db()


def _start(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    scheduler.start()
    return scheduler._scheduler


def test_the_ical_job_is_scheduled_with_no_feeds(monkeypatch, tmp_path):
    """A fresh install has no feeds yet; the job must still be armed."""
    _private_db(monkeypatch, tmp_path)
    try:
        running = _start(monkeypatch)
        assert db.query_one("SELECT COUNT(*) AS n FROM ical_feed")["n"] == 0
        assert running.get_job("ical").next_run_time is not None
    finally:
        scheduler.shutdown()


def test_the_ical_job_is_scheduled_with_a_feed(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Scheduler apartment",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/scheduler.ics",
            "active": 1,
            "created_at": now,
        },
    )
    try:
        running = _start(monkeypatch)
        assert running.get_job("ical").next_run_time is not None
    finally:
        scheduler.shutdown()


def test_the_first_run_time_is_timezone_aware():
    soon = scheduler._soon()
    assert soon.tzinfo is not None
    assert str(soon.tzinfo) == config.TIMEZONE


_JOBS = [
    {
        "id": "ical",
        "run": scheduler._job_sync_calendars,
        "target": (icalsync, "sync_all"),
        "level": "warning",
    },
    {
        "id": "submit",
        "run": scheduler._job_submit,
        "target": (reporting, "sweep"),
        "level": "critical",
    },
    {
        "id": "deadlines",
        "run": scheduler._job_deadlines,
        "target": (reporting, "check_deadlines"),
        "level": "critical",
    },
    {
        "id": "mail",
        "run": scheduler._job_mail,
        "target": (claim, "expire_holds"),
        "level": "warning",
    },
    {
        "id": "photo_sweep",
        "run": scheduler._job_photo_sweep,
        "target": (passport_photos, "purge_stale"),
        "level": "warning",
    },
    {
        "id": "retention",
        "run": scheduler._job_retention,
        "target": (retention, "run"),
        "level": "warning",
    },
]


@pytest.mark.parametrize("job", _JOBS, ids=[job["id"] for job in _JOBS])
def test_a_failing_job_alerts_the_host_and_the_next_success_resolves_it(
    job, monkeypatch, tmp_path
):
    _private_db(monkeypatch, tmp_path)
    module, name = job["target"]
    real = getattr(module, name)
    key = f"job_failed:{job['id']}"

    def boom(*_args, **_kwargs):
        raise RuntimeError("job blew up")

    monkeypatch.setattr(module, name, boom)
    job["run"]()

    alert = db.query_one("SELECT * FROM alert WHERE dedupe_key = ?", (key,))
    assert alert is not None
    assert alert["kind"] == "job_failed"
    assert alert["level"] == job["level"]
    assert alert["message"] and alert["detail"]
    assert alert["resolved_at"] is None

    monkeypatch.setattr(module, name, real)
    job["run"]()

    assert db.query_one(
        "SELECT resolved_at FROM alert WHERE dedupe_key = ?", (key,)
    )["resolved_at"]


def test_a_second_failure_refreshes_one_card(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("job blew up")

    monkeypatch.setattr(reporting, "check_deadlines", boom)
    scheduler._job_deadlines()
    scheduler._job_deadlines()

    rows = db.query(
        "SELECT id FROM alert WHERE dedupe_key = ?", ("job_failed:deadlines",)
    )
    assert len(rows) == 1


def test_a_successful_submission_sweep_pings_the_heartbeat(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "HEARTBEAT_URL", "https://heartbeat.example/ping")
    calls = []
    monkeypatch.setattr(
        scheduler.requests, "get", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    monkeypatch.setattr(reporting, "sweep", lambda: {"submitted": 0, "failed": 0})

    scheduler._job_submit()

    assert len(calls) == 1
    assert calls[0][0][0] == "https://heartbeat.example/ping"


def test_a_failed_submission_sweep_does_not_ping_the_heartbeat(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "HEARTBEAT_URL", "https://heartbeat.example/ping")
    calls = []
    monkeypatch.setattr(
        scheduler.requests, "get", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    def boom():
        raise RuntimeError("sweep blew up")

    monkeypatch.setattr(reporting, "sweep", boom)

    scheduler._job_submit()

    assert calls == []
