"""Guest and host door-code display plus row creation eligibility (task 0009–0016)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import config, db, door_codes

PREFIX = "dc-view-"


@pytest.fixture(autouse=True)
def _cleanup():
    db.init_db()
    _purge()
    yield
    _purge()


def _purge():
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
            "display_name": "Door host",
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )


def _apartment(owner: int, **overrides) -> int:
    global _counter
    _counter += 1
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "DC view", "seat": "Praha", "created_at": now, "owner_user_id": owner},
    )
    base = {
        "legal_entity_id": entity_id,
        "owner_user_id": owner,
        "internal_name": "Flat",
        "permalink_token": f"{PREFIX}tok-{_counter}",
        "automation_mode": "manual",
        "default_purpose": "10",
        "active": 1,
        "created_at": now,
        "lock_provider": "ttlock",
        "lock_id": "lock-99",
        "checkin_hour": 15,
        "checkout_hour": 10,
    }
    base.update(overrides)
    return db.insert("apartment", base)


def _stay(apartment_id: int, **overrides) -> dict:
    global _counter
    _counter += 1
    today = date.today()
    now = db.utcnow()
    base = {
        "apartment_id": apartment_id,
        "source": "manual",
        "uid": f"{PREFIX}stay-{_counter}",
        "date_from": (today - timedelta(days=1)).isoformat(),
        "date_to": (today + timedelta(days=5)).isoformat(),
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    rid = db.insert("reservation", base)
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (rid,))


def _apartment_row(apartment_id: int) -> dict:
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def _door_row(reservation_id: int, apartment_id: int, **overrides) -> dict:
    now = db.utcnow()
    base = {
        "reservation_id": reservation_id,
        "apartment_id": apartment_id,
        "lock_id": "lock-99",
        "state": door_codes.PENDING,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    row_id = db.insert("door_code", base)
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))


def test_view_is_hidden_without_ttlock():
    owner = _owner()
    apartment_id = _apartment(owner, lock_provider=None, lock_id=None)
    reservation = _stay(apartment_id)
    assert door_codes.view(reservation, _apartment_row(apartment_id)) is None


def test_view_hides_ical_stays_until_live(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", False)
    owner = _owner()
    apartment_id = _apartment(owner)
    reservation = _stay(apartment_id, source="ical")
    assert door_codes.view(reservation, _apartment_row(apartment_id)) is None


def test_view_waiting_and_preparing_without_a_row():
    owner = _owner()
    apartment_id = _apartment(owner)
    open_stay = _stay(apartment_id)
    assert door_codes.view(open_stay, _apartment_row(apartment_id)) == {"state": "waiting"}

    done = _stay(apartment_id, registration_completed_at=db.utcnow())
    assert door_codes.view(done, _apartment_row(apartment_id)) == {"state": "preparing"}


@pytest.mark.parametrize(
    "code_state",
    [door_codes.PENDING, door_codes.ISSUING, door_codes.RETRYING],
)
def test_view_maps_in_progress_states(code_state):
    owner = _owner()
    apartment_id = _apartment(owner)
    reservation = _stay(apartment_id, registration_completed_at=db.utcnow())
    _door_row(reservation["id"], apartment_id, state=code_state)
    assert door_codes.view(reservation, _apartment_row(apartment_id)) == {"state": "preparing"}

    waiting = _stay(apartment_id)
    _door_row(waiting["id"], apartment_id, state=code_state)
    assert door_codes.view(waiting, _apartment_row(apartment_id)) == {"state": "waiting"}


def test_view_failed_expired_and_issued():
    owner = _owner()
    apartment_id = _apartment(owner)
    failed = _stay(apartment_id)
    _door_row(failed["id"], apartment_id, state=door_codes.FAILED)
    assert door_codes.view(failed, _apartment_row(apartment_id)) == {"state": "failed"}

    expired = _stay(apartment_id)
    _door_row(expired["id"], apartment_id, state=door_codes.EXPIRED)
    assert door_codes.view(expired, _apartment_row(apartment_id)) is None

    valid_from = "2026-06-01T13:00:00+00:00"
    valid_to = "2026-06-05T08:00:00+00:00"
    issued = _stay(
        apartment_id,
        date_from="2026-06-01",
        date_to="2026-06-05",
        registration_completed_at=db.utcnow(),
    )
    _door_row(
        issued["id"],
        apartment_id,
        state=door_codes.ISSUED,
        pin_enc=db.encrypt_field("4829"),
        valid_from=valid_from,
        valid_to=valid_to,
        provider_code_id="pid-1",
    )
    shown = door_codes.view(issued, _apartment_row(apartment_id))
    assert shown["state"] == "issued"
    assert shown["pin"] == "4829"
    assert shown["works_from"] == "01.06.2026 15:00"
    assert shown["works_until"] == "05.06.2026 10:00"
    # TTLock: first-use deadline is 24 h after the code becomes valid (valid_from).
    assert shown["first_use_by"] == "02.06.2026 15:00"
    assert shown["checkin"] == "01.06.2026 15:00"
    assert shown["checkout"] == "05.06.2026 10:00"


def test_view_issued_without_pin_stays_preparing():
    owner = _owner()
    apartment_id = _apartment(owner)
    reservation = _stay(apartment_id, registration_completed_at=db.utcnow())
    _door_row(reservation["id"], apartment_id, state=door_codes.ISSUED, pin_enc=None)
    assert door_codes.view(reservation, _apartment_row(apartment_id)) == {"state": "preparing"}


def test_mail_idempotency_key_changes_when_the_provider_code_changes():
    row = {
        "valid_from": "2026-06-01T13:00:00+00:00",
        "valid_to": "2026-06-05T08:00:00+00:00",
        "provider_code_id": "a",
    }
    first = door_codes._mail_idempotency_key(42, row)
    row["provider_code_id"] = "b"
    assert door_codes._mail_idempotency_key(42, row) != first
    assert first == "door_code:42:2026-06-01T13:00:00+00:00:2026-06-05T08:00:00+00:00:a"


def test_ensure_row_creates_one_pending_row(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", False)
    owner = _owner()
    apartment_id = _apartment(owner)
    now = db.utcnow()
    db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "username": "tt",
            "password_enc": db.encrypt_field("pw"),
            "status": "ok",
            "created_at": now,
            "updated_at": now,
        },
    )
    monkeypatch.setattr(door_codes.ttlock, "allowed_for", lambda _uid: True)
    reservation = _stay(apartment_id, registration_completed_at=now)
    row_id = door_codes.ensure_row(int(reservation["id"]))
    assert row_id is not None
    again = door_codes.ensure_row(int(reservation["id"]))
    assert again == row_id
    row = db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))
    assert row["state"] == door_codes.PENDING
    assert db.query_one("SELECT COUNT(*) AS n FROM door_code WHERE reservation_id = ?", (reservation["id"],))[
        "n"
    ] == 1


def test_ensure_row_skips_ineligible_stays(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_LIVE", False)
    owner = _owner()
    apartment_id = _apartment(owner)
    monkeypatch.setattr(door_codes.ttlock, "allowed_for", lambda _uid: True)
    ical = _stay(apartment_id, source="ical")
    assert door_codes.ensure_row(int(ical["id"])) is None

    past = _stay(
        apartment_id,
        date_from="2020-01-01",
        date_to="2020-01-05",
    )
    assert door_codes.ensure_row(int(past["id"])) is None
