"""Send action rules for stay rows."""
from __future__ import annotations

import base64
from datetime import date, timedelta

from app import db, reporting

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


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
            "signature_png": SIGNATURE,
            "passport_photo_at": None,
            "signed_at": now,
            "identity_verified_at": now,
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return apartment, reservation, guest_id


def test_manual_mode_allows_send_when_guest_complete():
    apartment, reservation, _guest_id = _seed("manual", "tok-manual")
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "ready"
    assert controls["send_enabled"] is True
    assert controls["send_visible"] is True


def test_incomplete_stay_hides_send_button():
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
    assert controls["send_visible"] is False
    assert controls["send_enabled"] is False


def test_immediate_mode_disables_manual_send_button():
    apartment, reservation, _guest_id = _seed("immediate", "tok-immediate")
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert controls["send_enabled"] is False
    assert controls["auto_immediate"] is True


def test_czech_guest_explains_nothing_to_send():
    apartment, reservation, guest_id = _seed("manual", "tok-czech")
    db.update("guest", guest_id, {"nationality": "CZE", "submit_state": reporting.NOT_REQUIRED})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "not_required"
    assert controls["send_enabled"] is False
    assert controls["send_hint_key"] == "hint.nothing_duty"


def test_count_sendable_stays_includes_ready_manual_stays():
    apartment, reservation, _guest_id = _seed("manual", "tok-count")
    assert reporting.count_sendable_stays([reservation]) == 1


def test_status_label_reflects_automation():
    assert reporting.status_label("ready", "immediate") == "Verified — auto-send after you confirm"
    assert reporting.status_label("awaiting_guest", "immediate") == "Waiting for guest"
    assert reporting.status_label("ready", "manual") == "Ready — send manually"


def test_unverified_foreign_guest_can_send():
    apartment, reservation, guest_id = _seed("manual", "tok-unverified")
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "awaiting_verification"
    assert controls["send_enabled"] is True
    assert controls["pending_count"] == 1
    assert controls["send_hint_key"] == "hint.ready_id_optional"


def test_foreign_guest_online_checkin_complete_without_passport_photo():
    apartment, reservation, guest_id = _seed("manual", "tok-no-photo")
    db.update(
        "guest",
        guest_id,
        {"entered_by": "guest", "identity_verified_at": None, "identity_verified_by": None},
    )
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert reporting.guest_is_complete(guest, reservation)


def test_ensure_identity_verified_for_send_marks_guest_on_send():
    _apartment, _reservation, guest_id = _seed("manual", "tok-on-send")
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )
    reporting.ensure_identity_verified_for_send([guest_id], verified_by_user_id=None)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["identity_verified_at"]
    assert guest["identity_verified_by"] is None
    audit = db.query_one(
        "SELECT * FROM audit WHERE action = 'guest_identity_verified' ORDER BY id DESC LIMIT 1"
    )
    assert "on_send=1" in (audit["detail"] or "")


def test_unsigned_foreign_guest_blocks_send():
    apartment, reservation, guest_id = _seed("manual", "tok-unsigned")
    db.update("guest", guest_id, {"signature_png": None, "signed_at": None})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "incomplete"
    assert controls["send_enabled"] is False
    assert controls["send_visible"] is False
    assert controls["send_hint_key"] == "hint.need_signature"


def test_demo_apartment_submit_is_noop():
    apartment, reservation, guest_id = _seed("manual", "tok-demo-submit")
    db.update(
        "apartment",
        apartment["id"],
        {"internal_name": "Vinohrady Studio (demo)"},
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment["id"],))
    results = reporting.submit_for_apartment(apartment["id"], only_guest_ids=[guest_id])
    assert results == [
        {
            "state": "noop",
            "error": "Demo data is for preview only and is never sent to the police.",
        }
    ]


def test_record_host_identity_confirmation_is_idempotent():
    _apartment, _reservation, guest_id = _seed("manual", "tok-idempotent")
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )
    reporting.record_host_identity_confirmation(guest_id, verified_by_user_id=None)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    first_at = guest["identity_verified_at"]
    assert guest["identity_verified_by"] is None
    reporting.record_host_identity_confirmation(guest_id, verified_by_user_id=None)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["identity_verified_at"] == first_at
    assert guest["identity_verified_by"] is None


def test_demo_apartment_hides_send_button():
    apartment, reservation, guest_id = _seed("manual", "tok-demo")
    db.update(
        "apartment",
        apartment["id"],
        {"internal_name": "Vinohrady Studio (demo)"},
    )
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment["id"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "awaiting_verification"
    assert controls["send_enabled"] is False
    assert controls["send_visible"] is False
    assert controls["send_hint_key"] == "hint.demo_preview"
