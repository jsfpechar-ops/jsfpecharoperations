"""A stay cancelled in the calendar after guests filled in forms raises a warning."""
from __future__ import annotations

from app import alerts, db, icalsync


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


def test_guests_the_police_never_expect_raise_nothing():
    db.init_db()
    now = db.utcnow()
    stay = _stay(now, "cwg-2")
    _guest(stay["id"], "not_required", now)
    icalsync._warn_if_guests_registered(stay, stay["apartment_id"], "cancelled")
    assert not alerts.open_alert(f"cancelled_with_guests:{stay['id']}")
