"""Resending a record UbyPort already refused as a duplicate cannot help.

Since 1 Sep 2025 unjustified duplicates count against the host and can cost
them web-service access. A record parked in ``blocked`` because the register
already holds it is the one thing that must never go back on the wire: the
send cannot succeed, so the only possible outcome is another strike.
"""
from __future__ import annotations

import base64
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pytest

from app import alerts, db, reporting
from app.ubyport import errors as uby_errors
from app.ubyport.client import SubmissionResult, UbyportTransportError

RECEIPT_PDF = "UEsDBAoAAAAAAA=="

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
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM submission WHERE apartment_id = ?", (row["id"],))
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


def _open_alert(apartment_id: int, kind: str):
    return db.query_one(
        "SELECT * FROM alert WHERE apartment_id = ? AND kind = ? AND resolved_at IS NULL",
        (apartment_id, kind),
    )


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

    def fake_submit(
        _apartment,
        pairs,
        mode="auto",
        want_pdf=True,
        env=None,
    ):
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


def test_duplicate_after_lost_success_is_recorded_as_a_duplicate(monkeypatch):
    """A 150 proves the register holds the record, but it is not a fresh accept.

    The response carries no Dorucenka, so the submission must not claim the same
    outcome as a first-time filing that came back with one.
    """
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
    submission = db.query_one(
        "SELECT * FROM submission WHERE id = ?", (result["submission_id"],)
    )

    assert result["state"] == "ok_duplicate"
    assert submission["state"] == "ok_duplicate"
    assert result["submitted"] == 1
    assert guest["submit_state"] == reporting.SENT
    assert guest["submitted_at"]
    assert guest["receipt_submission_id"] is None, (
        "no Dorucenka was ever stored for this guest, so nothing may point at one"
    )


def test_a_duplicate_filing_resolves_the_rejection_alert(monkeypatch):
    """`ok_duplicate` is a success, so the ladder has to treat it as one.

    Filing a record the register already holds proves the guest is declared.
    Raising a critical rejection for it would tell the host the opposite of what
    the register says.
    """
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok8")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    alerts.raise_alert(
        "critical",
        "submission_rejected",
        "an earlier attempt was refused",
        "",
        dedupe_key=f"submission_rejected:{apartment_id}",
        apartment_id=apartment_id,
    )
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

    assert result["state"] == "ok_duplicate"
    assert _open_alert(apartment_id, "submission_rejected") is None, (
        "a duplicate filing must resolve the rejection alert, not raise one"
    )


def test_an_accept_without_a_receipt_request_is_not_a_duplicate(monkeypatch):
    """`want_pdf=False` asks for no Dorucenka. That is not a duplicate.

    Keying the state on the absence of a receipt would label every accepted
    batch that did not request a PDF as "already registered".
    """
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok9")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True
    )
    asked = []

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            asked.append(want_pdf)
            return SubmissionResult(
                endpoint="mock",
                request_xml="<request/>",
                response_xml="<response/>",
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    result = reporting.submit_batch(apartment, pairs, want_pdf=False)

    assert asked == [False]
    assert result["state"] == "ok"


def test_an_accept_with_no_confirmation_raises_a_warning(monkeypatch):
    """The product promises to keep the Dorucenka; nothing noticed when it did not."""
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok10")
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
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    result = reporting.submit_batch(apartment, pairs)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    alert = _open_alert(apartment_id, "receipt_missing")

    assert result["state"] == "ok"
    assert alert is not None, "an accepted record with no confirmation went unnoticed"
    assert alert["level"] == "warning"
    assert guest["receipt_submission_id"] is None


def test_a_receipt_clears_the_missing_confirmation_warning(monkeypatch):
    """The warning has to go away once a confirmation does come back."""
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok11")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    alerts.raise_alert(
        "warning",
        "receipt_missing",
        "an earlier accept kept no confirmation",
        "",
        dedupe_key=f"receipt_missing:{apartment_id}",
        apartment_id=apartment_id,
    )
    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True
    )

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            return SubmissionResult(
                endpoint="mock",
                request_xml="<request/>",
                response_xml="<response/>",
                pseudo_stamp="20260101120000-abc",
                receipt_pdf=RECEIPT_PDF,
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    result = reporting.submit_batch(apartment, pairs)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))

    assert result["state"] == "ok"
    assert _open_alert(apartment_id, "receipt_missing") is None
    assert guest["receipt_submission_id"] == result["submission_id"]


def test_a_duplicate_resend_points_at_the_submission_that_holds_the_receipt(monkeypatch):
    """A duplicate must not claim a Dorucenka that lives on another submission.

    The guest was filed once and the register confirmed it, then the host
    corrected the record and sent it again. The register answered "duplicate",
    so the only receipt on file belongs to the first submission and the guest
    has to point there rather than at this attempt.
    """
    apartment_id, guest_id = _seed(
        reporting.ERROR, "106: Invalid value in a guest field", "duptok12"
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    first_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": db.utcnow(),
            "finished_at": db.utcnow(),
            "mode": "auto",
            "state": "ok",
            "guest_ids": json.dumps([guest_id]),
            "pseudo_stamp": "20260101120000-abc",
            "receipt_pdf": RECEIPT_PDF,
        },
    )
    db.update(
        "guest",
        guest_id,
        {"submission_id": first_id, "receipt_submission_id": first_id},
    )
    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True
    )
    assert _ids(pairs) == [guest_id]

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

    assert result["state"] == "ok_duplicate"
    assert guest["submit_state"] == reporting.SENT
    assert guest["submission_id"] == result["submission_id"], (
        "the current pointer moves to the attempt that just ran"
    )
    assert guest["receipt_submission_id"] == first_id, (
        "the Dorucenka is on the submission that first filed the guest"
    )


def test_an_accept_without_a_receipt_keeps_the_receipt_it_already_had(monkeypatch):
    """Resending without asking for a PDF must not lose the receipt on file."""
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok13")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    first_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": db.utcnow(),
            "finished_at": db.utcnow(),
            "mode": "auto",
            "state": "ok",
            "guest_ids": json.dumps([guest_id]),
            "pseudo_stamp": "20260101120000-abc",
            "receipt_pdf": RECEIPT_PDF,
        },
    )
    db.update(
        "guest",
        guest_id,
        {
            "submit_state": reporting.SENT,
            "submitted_at": db.utcnow(),
            "submission_id": first_id,
            "receipt_submission_id": first_id,
        },
    )
    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True, allow_resend=True
    )

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            return SubmissionResult(
                endpoint="mock",
                request_xml="<request/>",
                response_xml="<response/>",
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    reporting.submit_batch(apartment, pairs, want_pdf=False)
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))

    assert guest["receipt_submission_id"] == first_id


def test_transport_failure_does_not_mark_identity_verified(monkeypatch):
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok7")
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            raise UbyportTransportError("offline")

    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _apartment: [])
    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    result = reporting.submit_for_apartment(
        apartment_id,
        [guest_id],
        mode="manual",
        ignore_automation=True,
    )
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))

    assert result[0]["state"] == "transport_error"
    assert guest["submit_state"] == reporting.PENDING
    assert guest["identity_verified_at"] is None


def test_a_later_send_does_not_erase_the_older_batch(monkeypatch):
    """The two links are not two spellings of one thing.

    ``guest.submission_id`` is a single current pointer that every send moves,
    so a resend would wipe the guest off the batch it was first filed in. The
    submission detail page reads ``submission.guest_ids`` for exactly that
    reason, and collapsing the pair would empty old submissions.
    """
    apartment_id, guest_id = _seed(reporting.SENT, None, "duptok14")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    first_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": db.utcnow(),
            "finished_at": db.utcnow(),
            "mode": "auto",
            "state": "ok",
            "guest_ids": json.dumps([guest_id]),
            "pseudo_stamp": "20260101120000-abc",
        },
    )
    db.update("guest", guest_id, {"submission_id": first_id})

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            return SubmissionResult(
                endpoint="mock",
                request_xml="<request/>",
                response_xml="<response/>",
                pseudo_stamp="20260102120000-def",
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True, allow_resend=True
    )
    second = reporting.submit_batch(apartment, pairs)

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["submission_id"] == second["submission_id"]
    assert guest["submission_id"] != first_id

    first = db.query_one("SELECT * FROM submission WHERE id = ?", (first_id,))
    assert json.loads(first["guest_ids"]) == [guest_id], (
        "the older batch still has to say who was in it"
    )


def test_resending_an_accepted_record_as_a_duplicate_is_not_a_rejection(monkeypatch):
    """A duplicate on a record we already had as sent is a confirmation.

    The host resends a record the register already holds, and the register says
    so. Nothing was refused, so the submission must not be recorded as an error
    and must not raise the critical rejection alert - which would tell the host
    "guest(s) were rejected" about a filing that succeeded.
    """
    apartment_id, guest_id = _seed(reporting.SENT, None, "duptok15")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    first_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": db.utcnow(),
            "finished_at": db.utcnow(),
            "mode": "manual",
            "state": "ok",
            "guest_ids": json.dumps([guest_id]),
            "pseudo_stamp": "20260101120000-abc",
            "receipt_pdf": RECEIPT_PDF,
        },
    )
    db.update(
        "guest",
        guest_id,
        {"submission_id": first_id, "receipt_submission_id": first_id},
    )
    pairs = reporting.collect_sendable(
        apartment_id, only_guest_ids=[guest_id], ignore_automation=True, allow_resend=True
    )
    assert _ids(pairs) == [guest_id], "the host asked for this resend explicitly"

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
    submission = db.query_one(
        "SELECT * FROM submission WHERE id = ?", (result["submission_id"],)
    )

    assert result["state"] == "ok_duplicate"
    assert submission["state"] == "ok_duplicate"
    assert result["blocked"] == 0, "nothing was refused, so nothing is blocked"
    assert guest["submit_state"] == reporting.SENT
    assert guest["receipt_submission_id"] == first_id, (
        "the Dorucenka still lives on the submission that first filed the guest"
    )
    assert _open_alert(apartment_id, "submission_rejected") is None, (
        "the register confirmed it holds the record; that is not a rejection"
    )


def test_a_batch_that_files_one_record_and_confirms_another_is_a_plain_success(
    monkeypatch,
):
    """A duplicate alongside a first-time accept does not make the batch a duplicate.

    One guest is filed for the first time and one was already sent and comes
    back as a duplicate. Something *was* filed, so the batch is a plain `ok` and
    not `ok_duplicate`, whose whole meaning is that nothing new was filed.
    """
    apartment_id, guest_id = _seed(reporting.PENDING, None, "duptok16")
    reservation_id = db.query_one(
        "SELECT reservation_id FROM guest WHERE id = ?", (guest_id,)
    )["reservation_id"]
    already_sent_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Novak",
            "first_name": "Petr",
            "birth_date": "02021985",
            "nationality": "DEU",
            "doc_number": "P7654321",
            "res_street": "Street 2",
            "res_city": "Brno",
            "res_country": "DEU",
            "purpose": "10",
            "is_lead": 0,
            "entered_by": "host",
            "signature_png": SIGNATURE,
            "signed_at": db.utcnow(),
            "identity_verified_at": db.utcnow(),
            "submit_state": reporting.SENT,
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    pairs = reporting.collect_sendable(
        apartment_id, ignore_automation=True, allow_resend=True
    )
    assert _ids(pairs) == [guest_id, already_sent_id], (
        "both guests go on the wire, in id order"
    )

    class Client:
        def submit(self, _header, _guests, want_pdf=True):
            return SubmissionResult(
                endpoint="mock",
                request_xml="<request/>",
                response_xml="<response/>",
                record_errors=[";", ";150;"],
                receipt_pdf=RECEIPT_PDF,
                pseudo_stamp="20260101120000-abc",
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_args, **_kwargs: Client())

    result = reporting.submit_batch(apartment, pairs)

    assert result["state"] == "ok", (
        "a first-time accept happened, so the batch is not a pure duplicate"
    )
    assert result["blocked"] == 0
    assert _open_alert(apartment_id, "submission_rejected") is None
    assert _open_alert(apartment_id, "receipt_missing") is None
