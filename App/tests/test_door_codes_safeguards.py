"""A guest who finished registering is never left waiting in silence for a door code."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import alerts, config, db, deadlines, door_codes, ttlock

PREFIX = "dc-safe-"
_counter = 0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    db.init_db()
    _purge()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", False)
    monkeypatch.setattr(door_codes, "check_lock_clocks", lambda: {})
    monkeypatch.setattr(ttlock, "find_code_by_name", lambda *a, **k: None)
    yield
    _purge()


def _purge():
    for owner in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        oid = owner["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM door_code WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _stay(registered_minutes_ago: int) -> tuple[int, int, int]:
    """A registered manual stay on a property with a lock. Returns owner, apartment, stay."""
    global _counter
    _counter += 1
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": f"{PREFIX}{_counter}",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    entity = db.insert(
        "legal_entity",
        {"name": "Safe", "seat": "Praha", "created_at": now, "owner_user_id": owner},
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Flat",
            "permalink_token": f"{PREFIX}tok-{_counter}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
            "lock_provider": "ttlock",
            "lock_id": "35662508",
            "checkin_hour": 10,
            "checkout_hour": 15,
        },
    )
    db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": f"x_{PREFIX}{_counter}",
            "status": "ok",
            "created_at": now,
            "updated_at": now,
        },
    )
    today = deadlines.local_now().date()
    done = (datetime.now(timezone.utc) - timedelta(minutes=registered_minutes_ago)).replace(
        microsecond=0
    )
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "source": "manual",
            "uid": f"{PREFIX}stay-{_counter}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "status": "active",
            "registration_completed_at": done.isoformat(),
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner, apartment, stay


def _view(stay: int, apartment: int):
    return door_codes.view(
        db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,)),
        db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment,)),
    )


def _open_alert(stay: int):
    return db.query_one(
        "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL",
        (f"door_code_delayed:{stay}",),
    )


def _failing_ttlock(monkeypatch):
    def boom(*args, **kwargs):
        raise ttlock.TTLockError("down", kind="transient")

    monkeypatch.setattr(ttlock, "create_period_code", boom)


def test_a_fresh_wait_is_preparing_with_no_alert(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    assert _view(stay, apartment) == {"state": "preparing"}
    assert _open_alert(stay) is None


def test_a_long_wait_tells_the_guest_and_the_host(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    assert _view(stay, apartment) == {"state": "delayed"}
    alert = _open_alert(stay)
    assert alert is not None
    assert "reason=" in alert["detail"]


def test_the_alert_clears_when_the_code_arrives(monkeypatch):
    _failing_ttlock(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=15)
    door_codes.reconcile()
    assert _open_alert(stay) is not None

    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()
    assert _view(stay, apartment)["state"] == "issued"
    assert _open_alert(stay) is None


def test_a_stay_with_no_row_at_all_is_still_reported(monkeypatch):
    """The property is not set up for codes, so no row is ever made."""
    _, apartment, stay = _stay(registered_minutes_ago=15)
    db.execute("UPDATE apartment SET checkin_hour = NULL WHERE id = ?", (apartment,))
    door_codes.reconcile()
    assert db.query_one("SELECT id FROM door_code WHERE reservation_id = ?", (stay,)) is None
    assert _view(stay, apartment) == {"state": "delayed"}
    assert _open_alert(stay) is not None


def test_a_silent_exit_leaves_its_reason(monkeypatch):
    _, apartment, stay = _stay(registered_minutes_ago=1)
    row_id = door_codes.ensure_row(stay)
    db.execute("UPDATE lock_account SET status = 'reauth_needed'")
    assert door_codes.issue(row_id) is False
    row = db.query_one("SELECT state, last_error FROM door_code WHERE id = ?", (row_id,))
    assert row["state"] == door_codes.PENDING
    assert row["last_error"] == "no_account"


def test_a_broken_cancellation_phase_cannot_block_issuing(monkeypatch):
    _, apartment, stay = _stay(registered_minutes_ago=1)
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))

    def broken(_now):
        raise RuntimeError("boom")

    monkeypatch.setattr(door_codes, "_handle_cancellations", broken)
    monkeypatch.setattr(door_codes, "_handle_moves", broken)
    counts = door_codes.reconcile()
    assert counts["issued"] == 1
    assert _view(stay, apartment)["state"] == "issued"
