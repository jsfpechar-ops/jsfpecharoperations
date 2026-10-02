"""A guest's data export carries that guest's audit trail and nobody else's."""
from __future__ import annotations

from app import db, dsr


def test_the_export_matches_every_audit_format_for_this_guest_only():
    db.init_db()
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {"username": "dsr-owner", "password_hash": "x", "role": "host", "created_at": now},
    )
    apartment = db.insert(
        "apartment", {"internal_name": "DSR flat", "owner_user_id": owner, "created_at": now}
    )
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": "dsr-1", "date_from": "2026-01-01",
         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
    )
    guest = db.insert(
        "guest",
        {"reservation_id": reservation, "surname": "Export", "first_name": "Me",
         "nationality": "GBR", "created_at": now, "updated_at": now},
    )
    other = guest * 10 + 7  # shares a prefix with this guest's id
    for action, detail, who in (
        ("passport_photo_viewed", f"guest_id={guest}", owner),
        ("guest_updated", f"id={guest} by=host", owner),
        ("guest_form_saved", f"guest={guest} reservation={reservation}", owner),
        ("guest_updated", f"id={other} by=host", owner),
        ("apartment_updated", f"id={guest}", owner),
        ("passport_photo_viewed", f"guest_id={guest}", None),
    ):
        db.audit(action, detail, owner_user_id=who)
    actions = [row["action"] for row in dsr.guest_export(guest)["audit"]]
    assert actions == ["passport_photo_viewed", "guest_updated", "guest_form_saved"]
