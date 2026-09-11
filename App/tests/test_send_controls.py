"""Send / review action rules for stay rows."""
from __future__ import annotations

from datetime import date, timedelta

from app import db, reporting


def _seed(mode: str = "manual", token: str = "tok"):
    db.init_db()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Test", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": token,
            "automation_mode": mode,
            "submit_after_hours": 24,
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "stay-1",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
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
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return apartment, reservation, guest_id


def test_manual_mode_requires_review_before_send():
    apartment, reservation, _guest_id = _seed("manual", "tok-manual")
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "ready"
    assert controls["review_mode"] == "mark"
    assert controls["send_enabled"] is False
    assert controls["requires_review"] is True

    db.update("reservation", reservation["id"], {"report_reviewed_at": db.utcnow()})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    controls = reporting.send_controls(reservation, apartment, reporting.reservation_progress(reservation))
    assert controls["review_mode"] == "done"
    assert controls["send_enabled"] is True


def test_incomplete_stay_offers_open_review_link():
    apartment, reservation, guest_id = _seed("manual", "tok-incomplete")
    db.update(
        "guest",
        guest_id,
        {"surname": "", "first_name": "", "birth_date": "", "doc_number": ""},
    )
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    controls = reporting.send_controls(
        reservation, apartment, reporting.reservation_progress(reservation)
    )
    assert controls["review_mode"] == "open"
    assert controls["send_visible"] is False


def test_immediate_mode_disables_manual_send_button():
    apartment, reservation, _guest_id = _seed("immediate", "tok-immediate")
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert controls["send_enabled"] is False
    assert controls["auto_immediate"] is True


def test_status_label_reflects_automation():
    assert reporting.status_label("ready", "immediate") == "Ready — auto-send"
    assert reporting.status_label("ready", "manual") == "Ready — send manually"
