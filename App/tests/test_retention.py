"""Retention: what has to survive six years, and what has to be gone by then.

Two opposite duties meet here. The house book has to be produceable for six
years after the last entry, so nothing may quietly delete a reported guest. A
passport photo has no such basis - it exists only so the host can check the
form against the document - so it has to disappear, and it has to disappear
even when the host never presses Verify.
"""
from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone

import pytest

from app import db, housebook, passport_photos, reporting


@pytest.fixture(autouse=True)
def _no_leftovers():
    """Leave the shared database as it was found; see test_duplicate_guard."""
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'tok-%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = 'Test'")
    db.execute("DELETE FROM user_account WHERE username LIKE 'retention-%'")

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


SUBMISSION_REQUEST = (
    "<request><guest><cDocN>P1234567</cDocN></guest></request>"
)
SUBMISSION_RESPONSE = "<response><result>OK</result></response>"
RECEIPT_B64 = base64.b64encode(b"%PDF-1.4 Dorucenka").decode()

_tok_counter = 0


def _seed_owner(username: str) -> int:
    """One host account, so a purge can be scoped to it."""
    db.init_db()
    now = db.utcnow()
    return db.insert(
        "user_account",
        {
            "username": username,
            "display_name": username,
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )


def _seed_submission(
    created_days_ago: int,
    state: str = "ok",
    owner_user_id: int | None = None,
    guest_id: int | None = None,
) -> int:
    """A submission row as the app writes one, envelope and receipt included."""
    global _tok_counter
    _tok_counter += 1
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
            "owner_user_id": owner_user_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": f"tok-sub-{_tok_counter}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    created_at = (
        datetime.now(timezone.utc) - timedelta(days=created_days_ago)
    ).replace(microsecond=0).isoformat()
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": created_at,
            "finished_at": created_at,
            "mode": "manual",
            "state": state,
            "guest_ids": "[]",
            "pseudo_stamp": "20260101120000-abc",
            "receipt_pdf": RECEIPT_B64,
            "request_xml": SUBMISSION_REQUEST,
            "response_xml": SUBMISSION_RESPONSE,
        },
    )
    if guest_id is not None:
        db.update("guest", guest_id, {"submission_id": submission_id})
    return submission_id


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


def test_verifying_deletes_the_passport_photo_there_and_then():
    """The photo's whole purpose is the identity check, so it goes with it.

    Leaving it for the retention sweep would keep a passport scan on disk for
    weeks after the app decided it was no longer needed.
    """
    guest_id = _seed_guest(date.today(), verified=False)

    reporting.record_host_identity_confirmation(guest_id, None)

    assert not passport_photos.has_photo(guest_id), (
        "the record was verified but the passport image was kept"
    )
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["identity_verified_at"]
    assert guest["passport_photo_at"] is None


def test_a_reported_guest_cannot_be_deleted_before_the_six_years_are_up():
    """The house book has to be produceable on inspection for six years."""
    guest_id = _seed_guest(date.today() - timedelta(days=30))
    db.update("guest", guest_id, {"submit_state": reporting.SENT})

    assert housebook.purge_expired() == 0
    assert db.query_one("SELECT 1 AS x FROM guest WHERE id = ?", (guest_id,))


# --- submission envelopes ------------------------------------------------
#
# The request envelope holds every reported guest's passport number, and the
# submission row outlives the six-year purge of the guest row it describes.
# Nothing in the application ever deleted it.

def test_an_old_submission_keeps_its_receipt_but_loses_its_envelope():
    """The Dorucenka is evidence; the envelope is only a copy of the data."""
    submission_id = _seed_submission(created_days_ago=200)

    assert reporting.purge_submission_payloads() == 1

    row = db.query_one("SELECT * FROM submission WHERE id = ?", (submission_id,))
    assert row["request_xml"] is None, "the passport numbers are still on disk"
    assert row["request_xml_enc"] is None
    assert row["response_xml"] is None
    assert row["receipt_pdf"] == RECEIPT_B64, (
        "the Dorucenka is the evidence the host must still be able to produce"
    )
    assert row["pseudo_stamp"]


def test_a_recent_submission_keeps_its_envelope():
    """A host disputing last month's filing needs the envelope it was sent in."""
    submission_id = _seed_submission(created_days_ago=10)

    assert reporting.purge_submission_payloads() == 0

    row = db.query_one("SELECT * FROM submission WHERE id = ?", (submission_id,))
    assert row["request_xml"] == SUBMISSION_REQUEST
    assert row["response_xml"] == SUBMISSION_RESPONSE


def test_the_payload_purge_can_be_run_twice_without_touching_anything_else():
    """The sweep runs every 12 hours, so it has to be idempotent."""
    submission_id = _seed_submission(created_days_ago=200)

    assert reporting.purge_submission_payloads() == 1
    assert reporting.purge_submission_payloads() == 0

    row = db.query_one("SELECT * FROM submission WHERE id = ?", (submission_id,))
    assert row["receipt_pdf"] == RECEIPT_B64


def test_a_submission_whose_guests_were_purged_is_deleted():
    """`guest.submission_id` is ON DELETE SET NULL, so the row goes unreachable.

    Once the guests age out, no screen in the app can reach the submission
    again, and it still holds the envelope they were reported in.
    """
    guest_id = _seed_guest(date.today() - timedelta(days=365 * 7))
    submission_id = _seed_submission(created_days_ago=365 * 7, guest_id=guest_id)

    assert housebook.purge_expired() == 1

    assert not db.query_one(
        "SELECT 1 AS x FROM submission WHERE id = ?", (submission_id,)
    ), "the guests are gone but the submission that carried them is still here"


def test_deleting_a_guest_by_hand_does_not_take_a_recent_receipt_with_it():
    """The receipt is proof that something was filed, and it is not the guest's.

    A host who removes a guest entered by mistake must not thereby lose the
    Dorucenka for a filing that really happened.
    """
    guest_id = _seed_guest(date.today() - timedelta(days=30))
    submission_id = _seed_submission(created_days_ago=30, guest_id=guest_id)
    db.execute("DELETE FROM guest WHERE id = ?", (guest_id,))

    housebook.purge_expired()

    assert db.query_one(
        "SELECT 1 AS x FROM submission WHERE id = ?", (submission_id,)
    ), "a recent submission was deleted because its guest row was removed"


def test_purging_one_owner_leaves_another_owners_envelope_alone():
    """One host's purge button must never reach into another host's filings."""
    mine = _seed_owner("retention-a")
    theirs = _seed_owner("retention-b")
    my_submission = _seed_submission(created_days_ago=200, owner_user_id=mine)
    their_submission = _seed_submission(created_days_ago=200, owner_user_id=theirs)

    assert reporting.purge_submission_payloads(owner_user_id=mine) == 1

    assert db.query_one(
        "SELECT request_xml, request_xml_enc FROM submission WHERE id = ?", (my_submission,)
    )["request_xml"] is None
    assert db.query_one(
        "SELECT request_xml, request_xml_enc FROM submission WHERE id = ?", (their_submission,)
    )["request_xml"] == SUBMISSION_REQUEST, (
        "one host's purge blanked another host's submission envelope"
    )
