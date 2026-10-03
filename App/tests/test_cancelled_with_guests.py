"""A stay cancelled in the calendar after guests filled in forms raises a warning."""
from __future__ import annotations

import pytest

from app import alerts, db, icalsync, validation


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for row in db.query("SELECT id FROM apartment WHERE internal_name LIKE 'Flat cwg-%'"):
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (row["id"],))
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))


def _stay(now: str, uid: str) -> dict:
    apartment = db.insert("apartment", {"internal_name": f"Flat {uid}", "created_at": now})
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": uid, "date_from": "2030-05-01",
         "date_to": "2030-05-03", "status": "cancelled", "created_at": now, "updated_at": now},
    )
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation,))


def _guest(reservation_id: int, state: str, now: str) -> None:
    db.insert(
        "guest",
        {"reservation_id": reservation_id, "surname": "Form", "first_name": "Filled",
         "nationality": "GBR", "submit_state": state, "created_at": now, "updated_at": now},
    )


def test_pending_guests_raise_the_warning_and_reactivation_clears_it():
    db.init_db()
    now = db.utcnow()
    stay = _stay(now, "cwg-1")
    _guest(stay["id"], "pending", now)
    icalsync._warn_if_guests_registered(stay, stay["apartment_id"], "cancelled")
    key = f"cancelled_with_guests:{stay['id']}"
    assert alerts.open_alert(key)
    alerts.resolve(key)
    assert not alerts.open_alert(key)


def test_cancelled_stay_mail_uses_its_own_kind_and_czech_dates():
    db.init_db()
    now = db.utcnow()
    entity = db.insert(
        "legal_entity",
        {"name": "CWG entity", "contact_email": "host@example.com", "created_at": now},
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "internal_name": "Flat cwg-mail",
            "created_at": now,
        },
    )
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": "cwg-mail",
            "date_from": "2030-05-01",
            "date_to": "2030-05-03",
            "status": "cancelled",
            "created_at": now,
            "updated_at": now,
        },
    )
    stay = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    _guest(stay["id"], "pending", now)
    icalsync._warn_if_guests_registered(stay, apartment, "cancelled")
    row = db.query_one(
        "SELECT kind, subject FROM email_outbox WHERE idempotency_key = ?",
        (f"cancelled_with_guests:{stay['id']}:cancelled",),
    )
    assert row["kind"] == "cancelled_with_guests"
    assert "Flat cwg-mail" in row["subject"]
    assert validation.fmt_date("2030-05-01") in row["subject"]
    icalsync._warn_if_guests_registered(stay, apartment, "cancelled")
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM email_outbox WHERE idempotency_key = ?",
        (f"cancelled_with_guests:{stay['id']}:cancelled",),
    )["n"] == 1


def test_guests_the_police_never_expect_raise_nothing():
    db.init_db()
    now = db.utcnow()
    stay = _stay(now, "cwg-2")
    _guest(stay["id"], "not_required", now)
    icalsync._warn_if_guests_registered(stay, stay["apartment_id"], "cancelled")
    assert not alerts.open_alert(f"cancelled_with_guests:{stay['id']}")
