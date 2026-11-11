"""Host guest-details mail (task 1121).

The host gets their own mail of who registered. The guest list is rendered at
send time, so the outbox row holds the stay id and no guest value. The document
number shows its last four characters only. The guest receipt is no longer
copied to the host. All guest data here is made up.
"""
from __future__ import annotations

import html
import json

import pytest

from app import claim, config, db, door_codes, guest_mail_pref, mail, mail_notify, validation

PREFIX = "gdh1121-"
HOST = "host@gdh.test"
LEAD = "lead@gdh.test"
MASK = "••••"
_counter = 0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    db.init_db()
    _purge()
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(mail, "drain", lambda limit=8: {})
    yield
    _purge()


def _purge():
    for owner in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        oid = owner["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            for stay in db.query("SELECT id FROM reservation WHERE apartment_id = ?", (apt["id"],)):
                db.execute("DELETE FROM guest WHERE reservation_id = ?", (stay["id"],))
                db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (stay["id"],))
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _seed() -> dict:
    """A claimed stay with two made-up guests typed in through the guest form."""
    global _counter
    _counter += 1
    now = db.utcnow()
    owner = db.insert("user_account", {
        "username": f"{PREFIX}{_counter}", "display_name": "Host",
        "password_hash": "x", "role": "host", "created_at": now,
    })
    entity = db.insert("legal_entity", {
        "name": "Test Host s.r.o.", "seat": "Praha", "created_at": now,
        "owner_user_id": owner, "contact_email": HOST,
    })
    apartment = db.insert("apartment", {
        "legal_entity_id": entity, "owner_user_id": owner, "internal_name": "Test Flat",
        "permalink_token": f"{PREFIX}tok-{_counter}", "automation_mode": "manual",
        "default_purpose": "10", "active": 1, "created_at": now,
    })
    stay = db.insert("reservation", {
        "apartment_id": apartment, "source": "manual", "uid": f"{PREFIX}stay-{_counter}",
        "date_from": "2030-03-01", "date_to": "2030-03-04", "status": "active",
        "created_at": now, "updated_at": now,
    })
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, token_version, "
        "claimed_at, created_at, updated_at) VALUES (?, 'claimed', ?, 'en', 0, ?, ?, ?)",
        (stay, LEAD, now, now, now),
    )
    lead = db.insert("guest", {
        "reservation_id": stay, "first_name": "Jana", "surname": "Testova",
        "birth_date": "1990-02-03", "nationality": "DEU", "doc_type": "P",
        "doc_number": "AB1234567", "visa_number": "V99887766",
        "res_street": "Testgasse 1", "res_city": "Teststadt", "res_country": "DEU",
        "is_lead": 1, "entered_by": "guest", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    other = db.insert("guest", {
        "reservation_id": stay, "first_name": "Petr", "surname": "Ukazka",
        "birth_date": "1985-07-08", "nationality": "AUT", "doc_type": "ID",
        "doc_number": "XY7654321", "res_street": "Musterweg 9", "res_city": "Musterort",
        "res_country": "AUT", "is_lead": 0, "entered_by": "guest",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    return {"owner": owner, "apartment": apartment, "stay": stay, "guests": (lead, other)}


def _rows(stay: int, kind: str):
    return db.query(
        "SELECT * FROM email_outbox WHERE kind = ? AND reservation_id = ? ORDER BY id",
        (kind, stay),
    )


def _queue(seed: dict):
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
    return mail_notify.host_guest_details(apartment, reservation, filled=2, expected=2)


def _delivered(seed: dict):
    (row,) = _rows(seed["stay"], "guest_details_host")
    payload = json.loads(row["payload"])
    return mail.delivery_body(payload), html.unescape(mail.delivery_html(payload))


def test_mask_shows_the_last_four_only():
    assert mail_notify.mask_document_number("AB1234567") == f"{MASK} 4567"
    assert mail_notify.mask_document_number(" AB 123 4567 ") == f"{MASK} 4567"
    assert mail_notify.mask_document_number("12345") == f"{MASK} 2345"
    assert mail_notify.mask_document_number("1234") == MASK
    assert mail_notify.mask_document_number("1") == MASK
    assert mail_notify.mask_document_number("") == ""
    assert mail_notify.mask_document_number(None) == ""


def test_always_content_names_the_guests_and_nothing_more(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    seed = _seed()
    _queue(seed)
    text, page = _delivered(seed)
    for part in (text, page):
        assert "Jana Testova" in part
        assert "Petr Ukazka" in part
        assert "Germany" in part
        assert "Not filed yet" in part
        assert "2 of 2 registered" in part
        for absent in ("4567", "4321", "Testgasse", "Date of birth", MASK):
            assert absent not in part, absent


def test_full_details_add_birth_address_and_a_masked_document(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: True)
    seed = _seed()
    _queue(seed)
    text, page = _delivered(seed)
    born = validation.fmt_date("1990-02-03")
    for part in (text, page):
        assert f"{MASK} 4567" in part
        assert f"{MASK} 4321" in part
        assert born in part
        assert "Testgasse 1, Teststadt, DEU" in part
        for secret in ("AB1234567", "XY7654321", "V99887766"):
            assert secret not in part, secret


def test_the_outbox_row_holds_the_stay_id_and_no_guest_value(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: True)
    seed = _seed()
    _queue(seed)
    (row,) = _rows(seed["stay"], "guest_details_host")
    stored = " ".join([row["subject"] or "", row["payload"] or ""])
    for value in ("Jana", "Testova", "Petr", "Ukazka", "4567", "4321", "AB1234567",
                  "1990", "1985", "Testgasse", "Teststadt", "Musterweg"):
        assert value not in stored, value
    payload = json.loads(row["payload"])
    assert payload[mail.GUEST_DETAILS_KEY] == seed["stay"]
    assert mail.GUEST_DETAILS_MARKER in payload["text"]
    assert mail.GUEST_DETAILS_MARKER in payload["html"]
    assert row["to_email"] == HOST
    assert row["cc_email"] is None


def test_a_second_queue_for_the_same_count_is_the_same_mail():
    seed = _seed()
    assert _queue(seed) == _queue(seed)
    assert len(_rows(seed["stay"], "guest_details_host")) == 1


def test_the_receipt_is_not_copied_to_the_host_and_the_host_gets_their_own(monkeypatch):
    monkeypatch.setattr(guest_mail_pref, "full_details", lambda owner_user_id: False)
    monkeypatch.setattr(
        claim.reporting, "reservation_progress",
        lambda *a, **k: {"expected": 2, "filled": 2, "incomplete": []},
    )
    monkeypatch.setattr(door_codes, "completion_door_code", lambda *a, **k: ("none", None, None))
    seed = _seed()
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (seed["apartment"],))
    for _ in range(2):
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (seed["stay"],))
        claim.maybe_notify_completion(reservation, apartment)
    (receipt,) = _rows(seed["stay"], "completion")
    assert receipt["to_email"] == LEAD
    assert receipt["cc_email"] is None
    payload = json.loads(receipt["payload"])
    assert payload["reply_to"] == HOST
    assert "(host only)" not in payload["text"]
    (host_mail,) = _rows(seed["stay"], "guest_details_host")
    assert host_mail["to_email"] == HOST
