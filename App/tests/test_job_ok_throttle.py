"""0990: the last-success heartbeat must not rewrite its row on every run."""
from datetime import datetime, timedelta, timezone

from app import config, db, scheduler


def _private_db(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "job_ok.sqlite3")
    db.init_db()


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


def test_a_fresh_heartbeat_is_not_rewritten(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)
    key = scheduler.JOB_LAST_OK_PREFIX + "push"
    db.set_setting(key, _stamp(1))
    writes = _count_writes(monkeypatch)
    for _ in range(5):
        scheduler._job_ok("push")
    assert writes == []
    assert db.get_setting(key)


def test_a_stale_or_missing_heartbeat_is_written_once(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)
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


def test_a_slow_job_always_writes(monkeypatch, tmp_path):
    _private_db(monkeypatch, tmp_path)
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
