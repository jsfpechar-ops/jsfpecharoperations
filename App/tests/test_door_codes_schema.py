"""Task 0008: door-code schema, config defaults and PIN retention step."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from app import config, db, retention

PREFIX = "dc08-"


@pytest.fixture(autouse=True)
def _cleanup():
    db.init_db()
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    owners = [
        r["id"]
        for r in db.query(
            "SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)
        )
    ]
    for owner in owners:
        for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner,)):
            db.execute("DELETE FROM door_code WHERE apartment_id = ?", (row["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


_counter = 0


def _owner() -> int:
    global _counter
    _counter += 1
    return db.insert(
        "user_account",
        {
            "username": f"{PREFIX}{_counter}",
            "display_name": "Test host",
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )


def _apartment(owner: int) -> tuple[int, int]:
    global _counter
    _counter += 1
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "DC08 Test", "seat": "Praha", "created_at": now, "owner_user_id": owner},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner,
            "internal_name": "Flat",
            "permalink_token": f"{PREFIX}tok-{_counter}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    return entity_id, apartment_id


def _reservation(apartment_id: int) -> int:
    global _counter
    _counter += 1
    now = db.utcnow()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"{PREFIX}stay-{_counter}",
            "date_from": "2026-06-01",
            "date_to": "2026-06-05",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _table_columns(table: str) -> set[str]:
    rows = db.query(f"PRAGMA table_info({table})")
    return {r["name"] for r in rows}


def test_migration_creates_door_code_tables_and_columns():
    db.init_db()
    apt_cols = _table_columns("apartment")
    assert {"lock_provider", "lock_id", "checkin_hour", "checkout_hour"} <= apt_cols
    for table in ("lock_account", "door_code", "lock_api_usage"):
        assert _table_columns(table)


def test_one_door_code_per_reservation():
    owner = _owner()
    _, apartment_id = _apartment(owner)
    reservation_id = _reservation(apartment_id)
    now = db.utcnow()
    db.insert(
        "door_code",
        {
            "reservation_id": reservation_id,
            "apartment_id": apartment_id,
            "lock_id": "lock-1",
            "created_at": now,
            "updated_at": now,
        },
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.insert(
            "door_code",
            {
                "reservation_id": reservation_id,
                "apartment_id": apartment_id,
                "lock_id": "lock-1",
                "created_at": now,
                "updated_at": now,
            },
        )


def test_pin_is_wiped_a_day_after_expiry():
    owner = _owner()
    _, apartment_id = _apartment(owner)
    res_old = _reservation(apartment_id)
    res_new = _reservation(apartment_id)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old_valid_to = (now - timedelta(days=2)).isoformat()
    new_valid_to = (now + timedelta(hours=1)).isoformat()
    ts = db.utcnow()
    old_id = db.insert(
        "door_code",
        {
            "reservation_id": res_old,
            "apartment_id": apartment_id,
            "lock_id": "lock-1",
            "pin_enc": "enc-old",
            "valid_to": old_valid_to,
            "created_at": ts,
            "updated_at": ts,
        },
    )
    new_id = db.insert(
        "door_code",
        {
            "reservation_id": res_new,
            "apartment_id": apartment_id,
            "lock_id": "lock-1",
            "pin_enc": "enc-new",
            "valid_to": new_valid_to,
            "created_at": ts,
            "updated_at": ts,
        },
    )
    today = date.today()
    assert retention._door_code_pin_step(today, dry_run=True, owner_user_id=None) == 1
    assert db.query_one("SELECT pin_enc FROM door_code WHERE id = ?", (old_id,))["pin_enc"] == "enc-old"
    assert retention._door_code_pin_step(today, dry_run=False, owner_user_id=None) == 1
    assert db.query_one("SELECT pin_enc FROM door_code WHERE id = ?", (old_id,))["pin_enc"] is None
    assert db.query_one("SELECT pin_enc FROM door_code WHERE id = ?", (new_id,))["pin_enc"] == "enc-new"


def test_door_codes_are_off_by_default():
    assert config.DOOR_CODES_ENABLED is False
