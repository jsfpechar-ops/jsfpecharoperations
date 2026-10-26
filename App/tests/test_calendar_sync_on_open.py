from datetime import datetime, timedelta

import pytest

from app import config, db, icalsync


@pytest.fixture
def reads(monkeypatch, tmp_path):
    """Point the DB at a fresh file, turn the feature on, and record reads."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "calendar_sync_on_open.db")
    monkeypatch.setattr(config, "ICAL_OPEN_SYNC_MINUTES", 10)
    db.init_db()
    read = []
    monkeypatch.setattr(icalsync, "sync_feed", lambda feed: read.append(feed["id"]))
    return read


def _owner(owner):
    if db.query_one("SELECT id FROM user_account WHERE id = ?", (owner,)) is None:
        db.insert(
            "user_account",
            {
                "id": owner,
                "username": f"host{owner}@example.test",
                "password_hash": "x",
                "created_at": db.utcnow(),
            },
        )


def _feed(owner, *, checked_minutes_ago=None, index=0):
    now = db.utcnow()
    _owner(owner)
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": f"apartment {owner} {index}",
            "owner_user_id": owner,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    last_checked = None
    if checked_minutes_ago is not None:
        last_checked = (
            datetime.fromisoformat(now) - timedelta(minutes=checked_minutes_ago)
        ).isoformat()
    return db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": f"https://calendar.example/{owner}-{index}.ics",
            "active": 1,
            "created_at": now,
            "last_checked_at": last_checked,
        },
    )


def test_never_checked_feed_is_read_once(reads):
    feed_id = _feed(1)
    assert icalsync.sync_owner_if_stale(1) == 1
    # The claim sets last_checked_at, so a quick second open reads nothing.
    assert icalsync.sync_owner_if_stale(1) == 0
    assert reads == [feed_id]


def test_recently_checked_feed_is_skipped_and_stale_one_is_read(reads):
    _feed(1, checked_minutes_ago=5, index=1)
    stale = _feed(1, checked_minutes_ago=30, index=2)
    assert icalsync.sync_owner_if_stale(1) == 1
    assert reads == [stale]


def test_other_owners_feed_is_not_read(reads):
    _feed(2, index=1)
    assert icalsync.sync_owner_if_stale(1) == 0
    assert reads == []


def test_zero_minutes_reads_nothing(reads, monkeypatch):
    monkeypatch.setattr(config, "ICAL_OPEN_SYNC_MINUTES", 0)
    _feed(1)
    assert icalsync.sync_owner_if_stale(1) == 0
    assert reads == []


def test_failing_feed_is_recorded_and_does_not_raise(reads, monkeypatch):
    def boom(feed):
        raise RuntimeError("calendar host unreachable")

    monkeypatch.setattr(icalsync, "sync_feed", boom)
    feed_id = _feed(1)
    assert icalsync.sync_owner_if_stale(1) == 1
    row = db.query_one("SELECT last_status FROM ical_feed WHERE id = ?", (feed_id,))
    assert row["last_status"] == "error"
