"""Retention: what has to survive six years, and what has to be gone by then.

Two opposite duties meet here. The house book has to be produceable for six
years after the last entry, so nothing may quietly delete a reported guest. A
passport photo has no such basis - it exists only so the host can check the
form against the document - so it has to disappear, and it has to disappear
even when the host never presses Verify.
"""
from __future__ import annotations

import base64
from datetime import date, timedelta

from app import db, housebook, passport_photos, reporting

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)


def _seed_guest(stay_end: date, verified: bool = False) -> int:
    """One guest whose stay ended on ``stay_end``, with a photo on disk."""
    db.init_db()
    now = db.utcnow()
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
            "permalink_token": f"tok-{stay_end.isoformat()}-{verified}",
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
            "source": "manual",
            "uid": f"stay-{stay_end.isoformat()}-{verified}",
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
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "passport_photo_at": now,
            "identity_verified_at": now if verified else None,
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
    assert passport_photos.has_photo(guest_id)
    return guest_id


def test_retention_purge_takes_the_passport_photo_with_the_record():
    """A purge that leaves the photo behind leaves the worst of the data.

    Once six years pass there is no basis for the passport number, so there is
    certainly none for the image of the passport. Worse, the row that pointed
    at the file is gone, so no screen in the app can ever offer to delete it.
    """
    guest_id = _seed_guest(date.today() - timedelta(days=365 * 7))

    assert housebook.purge_expired() == 1

    assert not db.query_one("SELECT 1 AS x FROM guest WHERE id = ?", (guest_id,))
    assert not passport_photos.has_photo(guest_id), (
        "the purge deleted the guest row but left the passport image on disk"
    )


def test_a_photo_the_host_never_verified_does_not_live_forever():
    """The module promises deletion; an unpressed button must not defeat it."""
    guest_id = _seed_guest(date.today() - timedelta(days=120))

    assert passport_photos.purge_stale(owner_user_id=None) >= 1
    assert not passport_photos.has_photo(guest_id)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest is not None, "sweeping the photo must not touch the house book row"
    assert guest["passport_photo_at"] is None, "the row must stop advertising a photo"


def test_sweeping_spares_a_photo_the_host_still_needs():
    """A guest who checked out yesterday may still be waiting on a check."""
    guest_id = _seed_guest(date.today() - timedelta(days=1))

    passport_photos.purge_stale(owner_user_id=None)

    assert passport_photos.has_photo(guest_id), (
        "a photo for a current stay was deleted before the host could look at it"
    )


def test_a_file_with_no_guest_row_is_swept():
    """Orphans are unreachable from the UI, so only a sweep can clear them."""
    db.init_db()
    orphan_id = 987654
    passport_photos.save_photo(orphan_id, PNG_BYTES, "image/png")

    passport_photos.purge_stale(owner_user_id=None)

    assert not passport_photos.has_photo(orphan_id)


def test_a_reported_guest_cannot_be_deleted_before_the_six_years_are_up():
    """The house book has to be produceable on inspection for six years."""
    guest_id = _seed_guest(date.today() - timedelta(days=30))
    db.update("guest", guest_id, {"submit_state": reporting.SENT})

    assert housebook.purge_expired() == 0
    assert db.query_one("SELECT 1 AS x FROM guest WHERE id = ?", (guest_id,))
