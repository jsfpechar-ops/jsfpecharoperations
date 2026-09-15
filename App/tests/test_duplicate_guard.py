"""Resending a record UbyPort already refused as a duplicate cannot help.

Since 1 Sep 2025 unjustified duplicates count against the host and can cost
them web-service access. A record parked in ``blocked`` because the register
already holds it is the one thing that must never go back on the wire: the
send cannot succeed, so the only possible outcome is another strike.
"""
from __future__ import annotations

import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest

from app import db, reporting
from app.ubyport import errors as uby_errors
from app.ubyport.client import SubmissionResult

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


@pytest.fixture(autouse=True)
def _no_leftovers():
    """Leave the shared database as it was found.

    Tests further down the suite pick "the first apartment in the table", so a
    stray row here surfaces as an unrelated failure somewhere else.
    """
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query("SELECT id FROM apartment WHERE permalink_token LIKE 'duptok%'"):
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM legal_entity WHERE name = 'Dup Test'")


def _seed(state: str, last_errors: str | None, token: str):
    db.init_db()
    now, today = db.utcnow(), date.today()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Dup Test", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": token,
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
            "uid": f"dup-{token}",
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
            "signed_at": now,
            "identity_verified_at": now,
            "submit_state": state,
            "last_errors": last_errors,
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, guest_id


def _ids(pairs):
    return [guest["id"] for guest, _ in pairs]


def test_the_duplicate_detector_recognises_what_ubyport_sends_back():
    assert uby_errors.is_duplicate("150: Duplicate record")
    assert uby_errors.is_duplicate("Duplicitní záznam")
    assert not uby_errors.is_duplicate("106: Invalid value in a guest field")


def test_duplicate_code_is_non_correctable_without_codebook_wording():
    state, _messages = uby_errors.classify("", ";150;", {})
    assert state == "not_correctable"


def test_a_known_duplicate_is_not_resent_even_when_the_host_insists():
    """allow_resend is the host overriding caution, not overriding the law."""
    apartment_id, guest_id = _seed(
        reporting.BLOCKED, "150: Duplicate record", "duptok1"
    )

    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True, allow_resend=True
    )

    assert guest_id not in _ids(pairs), (
        "a record the register already holds was queued for sending again"
    )


def test_a_correctable_rejection_can_still_be_resent_after_a_fix():
    """The whole point of the resend button; it must keep working."""
    apartment_id, guest_id = _seed(
        reporting.ERROR, "106: Invalid value in a guest field", "duptok2"
    )

    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True, allow_resend=True
    )

    assert guest_id in _ids(pairs)


def test_an_accepted_record_can_still_be_resent_deliberately():
    """Resending an accepted record is a judgement call the host may make."""
    apartment_id, guest_id = _seed(reporting.SENT, None, "duptok3")

    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True, allow_resend=True
    )

    assert guest_id in _ids(pairs)


def test_nothing_blocked_is_ever_swept_up_automatically():
    apartment_id, guest_id = _seed(
        reporting.BLOCKED, "150: Duplicate record", "duptok4"
    )

    pairs = reporting.collect_sendable(apartment_id, ignore_automation=True)

    assert guest_id not in _ids(pairs)


def test_concurrent_sends_claim_each_guest_once(monkeypatch):
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok5")
    entered = threading.Event()
    release = threading.Event()
    calls = []

    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _apartment: [])
    monkeypatch.setattr(reporting, "ensure_identity_verified_for_send", lambda *_args: None)

    def fake_submit(_apartment, pairs, mode="auto", want_pdf=True, env=None):
        calls.append([guest["id"] for guest, _reservation in pairs])
        entered.set()
        assert release.wait(timeout=5)
        return {"submitted": len(pairs), "state": "ok"}

    monkeypatch.setattr(reporting, "submit_batch", fake_submit)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            reporting.submit_for_apartment,
            apartment_id,
            [guest_id],
            "manual",
            True,
            False,
        )
        assert entered.wait(timeout=5)
        second = reporting.submit_for_apartment(
            apartment_id,
            [guest_id],
            mode="manual",
            ignore_automation=True,
        )
        release.set()
        first_result = first.result(timeout=5)

    assert first_result == [{"submitted": 1, "state": "ok"}]
    assert second == []
    assert calls == [[guest_id]]


def test_duplicate_after_lost_success_is_recorded_as_sent(monkeypatch):
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok6")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True
    )

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            return SubmissionResult(
                endpoint="mock",
                request_xml="<request/>",
                response_xml="<response/>",
                record_errors=[";150;"],
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    result = reporting.submit_batch(apartment, pairs)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))

    assert result["state"] == "ok"
    assert result["submitted"] == 1
    assert guest["submit_state"] == reporting.SENT
    assert guest["submitted_at"]
