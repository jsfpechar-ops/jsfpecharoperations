"""BE-2: the retention job computes its row set, and deletes only when enabled.

Dry-run is the default (Rule 7). These tests seed expired and current guests and
assert that a dry run changes nothing, that the autopurge flag scopes deletion
to the requested owner, and that the due-notice fires once per owner per month.
"""
from __future__ import annotations

import base64
import json
from datetime import date, timedelta

import pytest

from app import config, db, housebook, passport_photos, scheduler, retention

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def _cleanup():
    db.init_db()
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'retjob-%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = 'RetJob'")
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'retjob-%'"):
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM alert WHERE dedupe_key LIKE 'retention_due:%'")
    db.execute("DELETE FROM settings WHERE key = 'retention_last_run'")


def _owner(username: str = "retjob-host") -> int:
    db.init_db()
    return db.insert(
        "user_account",
        {
            "username": username,
            "display_name": username,
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )


def _guest(
    owner_user_id: int,
    *,
    stay_end: date,
    token: str,
    photo: bool = False,
    stay_to: str | None = None,
) -> int:
    db.init_db()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "RetJob", "created_at": now, "owner_user_id": owner_user_id},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_user_id,
            "internal_name": "Flat",
            "permalink_token": token,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": f"stay-{token}",
            "date_from": (stay_end - timedelta(days=2)).isoformat(),
            "date_to": stay_end.isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Smith",
            "first_name": "John",
            "stay_from": (stay_end - timedelta(days=2)).isoformat(),
            "stay_to": stay_to if stay_to is not None else stay_end.isoformat(),
            "nationality": "GBR",
            "purpose": "10",
            "entered_by": "guest",
            "created_at": now,
            "updated_at": now,
        },
    )
    if photo:
        passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
        assert passport_photos.has_photo(guest_id)
    return guest_id


def _six_years_ago() -> date:
    return housebook.retention_cutoff(date.today()) - timedelta(days=1)


def test_a_dry_run_counts_the_row_set_and_deletes_nothing(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    owner = _owner()
    expired = _guest(owner, stay_end=_six_years_ago(), token="retjob-old", photo=True)
    fresh = _guest(owner, stay_end=date.today() - timedelta(days=30), token="retjob-new")

    summary = retention.run()

    assert summary["dry_run"] is True
    assert summary["counts"]["guests"] >= 1
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (expired,))
    assert passport_photos.has_photo(expired)
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (fresh,))

    audit = db.query_one(
        "SELECT detail FROM audit WHERE action = 'retention_run' ORDER BY id DESC LIMIT 1"
    )
    assert json.loads(audit["detail"])["dry_run"] is True
    stored = json.loads(db.get_setting("retention_last_run"))
    assert stored["dry_run"] is True


def test_autopurge_deletes_only_the_scoped_owners_expired_guests(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", True)
    owner = _owner("retjob-a")
    other = _owner("retjob-b")
    expired = _guest(owner, stay_end=_six_years_ago(), token="retjob-a-old", photo=True)
    fresh = _guest(owner, stay_end=date.today() - timedelta(days=30), token="retjob-a-new")
    other_expired = _guest(other, stay_end=_six_years_ago(), token="retjob-b-old")

    summary = retention.run(dry_run=False, owner_user_id=owner)

    assert summary["dry_run"] is False
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (expired,)) is None
    assert not passport_photos.has_photo(expired)
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (fresh,)) is not None
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (other_expired,)) is not None


def test_a_malformed_stay_to_falls_back_to_the_reservation_end():
    owner = _owner("retjob-mal")
    old = date.today() - timedelta(days=365 * 7)
    guest_id = _guest(owner, stay_end=old, token="retjob-mal", stay_to="garbage")
    assert guest_id in housebook.expired_guest_ids()


def test_the_due_notice_fires_once_per_owner_per_month(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", False)
    owner = _owner("retjob-due")
    # The six-year clock on this stay ends 15 days from today.
    stay_end = housebook.retention_cutoff(date.today()) + timedelta(days=15)
    _guest(owner, stay_end=stay_end, token="retjob-due")

    retention.run()
    key = f"retention_due:{owner}:{date.today().strftime('%Y-%m')}"
    alert = db.query_one("SELECT * FROM alert WHERE dedupe_key = ?", (key,))
    assert alert is not None
    assert alert["kind"] == "retention_due"
    params = json.loads(alert["params"])
    assert params["days"] == config.RETENTION_NOTICE_DAYS
    assert params["count"] >= 1

    retention.run()
    rows = db.query("SELECT id FROM alert WHERE dedupe_key = ?", (key,))
    assert len(rows) == 1


def test_the_scheduler_registers_the_retention_job(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "retjob.sqlite3")
    monkeypatch.setattr(config, "ENABLE_SCHEDULER", True)
    db.init_db()
    try:
        scheduler.start()
        assert scheduler._scheduler.get_job("retention") is not None
    finally:
        scheduler.shutdown()
