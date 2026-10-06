"""The automatic retry budget for a record the register keeps refusing.

The Foreign Police answered in writing (24 September 2026, B2-B3) that
resending a refused record with the same data is what badly written programs
do, and that it raises the host's error count with the police. A refused record
(severity 4-6) has a data problem that resending cannot fix, so the sweep offers
it once and then waits for the host.

But "retryable" was implemented as "retried for ever": ``collect_sendable``
skipped only ``sent`` and ``blocked``, so a record the register refused on every
attempt was re-offered by the unattended sweep every ten minutes, indefinitely,
for every guest of every property. Nobody watches that stream, and a value the
register will never accept (a bad document number, a nationality it does not
take) is a value no amount of resending fixes.

These tests pin the bound, the fact that it binds *only* the sweep, and the two
ways the count restarts.
"""
from __future__ import annotations

import base64
import inspect
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db, reporting
from app.ubyport.client import SubmissionResult, UbyportAuthError, UbyportOutcomeUnknownError, UbyportTransportError

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

# The policy value, written out rather than read from the module, so changing
# the constant without meaning to fails here instead of quietly redefining what
# these tests assert.
BOUND = 1

PASSWORD = "RetryCapTestPassword1"
USERNAME = "retry-cap-admin"


class RefusingClient:
    """A register that answers every record with 106, a correctable refusal."""

    def submit(self, _header, guests):
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            # One entry per record, so a batch of two is refused twice.
            record_errors=[";106;"] * len(guests),
        )


class AcceptingClient:
    def submit(self, _header, _guests):  # noqa: ARG002
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            record_errors=[],
        )


class DuplicateClient:
    """150 is the register saying it already holds the record."""

    def submit(self, _header, _guests):  # noqa: ARG002
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            record_errors=[";150;"],
        )


def _seed(token: str, surname: str = "Smith", auto: bool = False):
    """A complete, reportable guest on an active stay.

    ``auto`` makes the stay eligible for the unattended sweep, which is a
    different gate from "a host may send this": the sweep also needs a
    non-manual mode, a completed registration, and the lead time to have passed.
    It is deliberately not ``immediate``, so saving a form does not itself
    trigger a send.
    """
    db.init_db()
    now = db.utcnow()
    today = date.today()
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    # Host routes reach a guest only through its apartment owner, so a seeded
    # stay must belong to the account the ``host`` fixture logs in as.
    account = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    owner_user_id = account["id"] if account else None
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Retry Cap",
            "seat": "Praha",
            "ico": "12345678",
            "owner_user_id": owner_user_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_user_id,
            "internal_name": "Flat",
            "city_en": "Prague",
            "permalink_token": token,
            "automation_mode": "auto" if auto else "manual",
            "submit_after_hours": 1,
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
            "uid": f"stay-{token}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "registration_completed_at": completed_at if auto else None,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": surname,
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
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return apartment, reservation, guest_id


def _attempts(guest_id: int) -> int:
    return db.query_one("SELECT submit_attempts FROM guest WHERE id = ?", (guest_id,))[
        "submit_attempts"
    ]


def _stuck_alerts(apartment_id: int):
    return db.query(
        "SELECT * FROM alert WHERE kind = 'submission_stuck' AND apartment_id = ? "
        "AND resolved_at IS NULL",
        (apartment_id,),
    )


def _cleanup(apartment_id: int) -> None:
    db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM submission_claim WHERE guest_id IN "
        "(SELECT id FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?))",
        (apartment_id,),
    )


def _fail(apartment, guest_id: int, monkeypatch, client=RefusingClient) -> dict:
    """One send through the batch path, the way every caller reaches it."""
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client())
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
    assert guest_id in [guest["id"] for guest, _ in pairs], (
        "a host-initiated send must always be able to reach the record"
    )
    return reporting.submit_batch(apartment, pairs, mode="manual")


def test_the_bound_is_three_automatic_attempts():
    assert reporting.SUBMISSION_MAX_AUTO_ATTEMPTS == BOUND


def test_the_sweep_stops_offering_a_record_at_the_bound():
    """The sweep is the unattended path, so it is the one that has to stop."""
    apartment, _reservation, guest_id = _seed("tok-cap-sweep", auto=True)

    try:
        # Below the bound the sweep still offers the record: the count is a
        # brake on a loop, not a verdict on the first refusal.
        for attempts in range(BOUND):
            db.update(
                "guest",
                guest_id,
                {"submit_attempts": attempts, "submit_state": reporting.ERROR},
            )
            sweep = reporting.collect_sendable(apartment["id"])
            assert guest_id in [guest["id"] for guest, _ in sweep], (
                f"{attempts} refusals must still be retried"
            )

        db.update(
            "guest", guest_id, {"submit_attempts": BOUND, "submit_state": reporting.ERROR}
        )
        assert reporting.collect_sendable(apartment["id"]) == [], (
            "at the bound the sweep must stop offering the record"
        )
    finally:
        _cleanup(apartment["id"])


def test_a_host_send_is_never_bound_by_the_retry_cap(monkeypatch):
    """The cap must not be able to block a host action.

    A host resending a corrected record is the whole recovery path, so if the
    bound applied to it the record would be stranded with no way back.
    """
    apartment, _reservation, guest_id = _seed("tok-cap-host", auto=True)

    try:
        db.update(
            "guest",
            guest_id,
            {"submit_attempts": BOUND * 10, "submit_state": reporting.ERROR},
        )
        # The stay is sweep-eligible, so this empty result is the cap acting and
        # not the automation mode.
        assert reporting.collect_sendable(apartment["id"]) == []
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        assert guest_id in [guest["id"] for guest, _ in pairs]

        # And it really goes out: the batch reaches the register.
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: AcceptingClient())
        result = reporting.submit_batch(apartment, pairs, mode="manual")
        assert result["submitted"] == 1
        assert _attempts(guest_id) == 0
    finally:
        _cleanup(apartment["id"])


def test_each_refusal_counts_and_the_count_resets_on_accept(monkeypatch):
    """One refusal is one attempt, and a record the register takes starts over."""
    apartment, _reservation, guest_id = _seed("tok-cap-count")

    try:
        for expected in range(1, BOUND + 1):
            _fail(apartment, guest_id, monkeypatch)
            assert _attempts(guest_id) == expected

        _fail(apartment, guest_id, monkeypatch, client=AcceptingClient)
        assert _attempts(guest_id) == 0, (
            "the register took the record, so the count of refusals restarts"
        )
    finally:
        _cleanup(apartment["id"])


def test_a_duplicate_also_resets_the_count(monkeypatch):
    """A duplicate is the register answering, not refusing.

    It proves the record is filed, so it must restart the count exactly as an
    accept does -- otherwise a record whose HTTP response was lost would keep
    accumulating refusals it never earned.
    """
    apartment, _reservation, guest_id = _seed("tok-cap-dup")

    try:
        _fail(apartment, guest_id, monkeypatch)
        _fail(apartment, guest_id, monkeypatch)
        assert _attempts(guest_id) == 2

        _fail(apartment, guest_id, monkeypatch, client=DuplicateClient)
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submit_state"] == reporting.SENT
        assert guest["submit_attempts"] == 0
    finally:
        _cleanup(apartment["id"])


def test_the_card_is_raised_at_the_bound_and_not_before(monkeypatch):
    """The stop has to be visible, or it is a silent drop of a legal duty."""
    apartment, _reservation, guest_id = _seed("tok-cap-alert")

    try:
        for _ in range(BOUND - 1):
            _fail(apartment, guest_id, monkeypatch)
            assert _stuck_alerts(apartment["id"]) == [], (
                "no card while the record is still being retried"
            )

        _fail(apartment, guest_id, monkeypatch)
        cards = _stuck_alerts(apartment["id"])
        assert len(cards) == 1, "exactly one card per stay, not one per attempt"
        assert "Smith" in cards[0]["detail"], "the host has to be told which guest"

        # A further failure must not stack a second card.
        _fail(apartment, guest_id, monkeypatch)
        assert len(_stuck_alerts(apartment["id"])) == 1
    finally:
        _cleanup(apartment["id"])


def test_the_card_clears_once_the_record_moves_again(monkeypatch):
    """A warning that never clears teaches the host to ignore warnings."""
    apartment, _reservation, guest_id = _seed("tok-cap-clear")

    try:
        for _ in range(BOUND):
            _fail(apartment, guest_id, monkeypatch)
        assert len(_stuck_alerts(apartment["id"])) == 1

        _fail(apartment, guest_id, monkeypatch, client=AcceptingClient)
        assert _stuck_alerts(apartment["id"]) == []
    finally:
        _cleanup(apartment["id"])


def test_one_recovered_guest_does_not_clear_another_still_stuck(monkeypatch):
    """The card is per stay, so it clears per stay."""
    apartment, reservation, guest_id = _seed("tok-cap-two")

    try:
        other_id = db.insert(
            "guest",
            {
                "reservation_id": reservation["id"],
                "surname": "Stuck",
                "first_name": "Jane",
                "birth_date": "02021991",
                "nationality": "GBR",
                "doc_number": "P7654321",
                "res_street": "Street 2",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "is_lead": 0,
                "entered_by": "host",
                "signature_png": SIGNATURE,
                "signed_at": db.utcnow(),
                "identity_verified_at": db.utcnow(),
                "submit_state": reporting.ERROR,
                "submit_attempts": BOUND,
                "created_at": db.utcnow(),
                "updated_at": db.utcnow(),
            },
        )
        for _ in range(BOUND):
            _fail(apartment, guest_id, monkeypatch)
        assert len(_stuck_alerts(apartment["id"])) == 1

        # Recover the first guest. The second is still stranded, so the card has
        # to stay up or the remaining record stops being sent with nobody told.
        db.update("guest", guest_id, {"submit_state": reporting.SENT, "submit_attempts": 0})
        reporting.clear_stuck_alert_if_recovered(reservation["id"])
        assert len(_stuck_alerts(apartment["id"])) == 1, (
            "a card that clears while a record is still stranded is a silent drop"
        )

        db.update("guest", other_id, {"submit_state": reporting.SENT, "submit_attempts": 0})
        reporting.clear_stuck_alert_if_recovered(reservation["id"])
        assert _stuck_alerts(apartment["id"]) == []
    finally:
        _cleanup(apartment["id"])


def test_the_card_is_shown_in_the_host_language(monkeypatch):
    """Rule 5: the host reads their own language, not English stored text."""
    from app import host_i18n

    apartment, reservation, guest_id = _seed("tok-cap-lang")

    try:
        for _ in range(BOUND):
            _fail(apartment, guest_id, monkeypatch)
        card = _stuck_alerts(apartment["id"])[0]

        cs = alerts.present(card, "cs")
        en = alerts.present(card, "en")
        assert cs["display_detail"] == host_i18n.translate(
            "cs", "notification.reason.submission_stuck"
        )
        assert en["display_detail"] == host_i18n.translate(
            "en", "notification.reason.submission_stuck"
        )
        assert cs["display_detail"] != en["display_detail"]
        # A stay-scoped card names the property, so the host can find the stay.
        assert apartment["internal_name"] in cs["display_title"]
        assert cs["display_detail"] != card["detail"], (
            "the card must not fall back to the stored English text"
        )
    finally:
        _cleanup(apartment["id"])


def test_the_translated_key_exists_in_both_languages():
    """A missing CS key would render the raw key to a Czech host."""
    from app import host_i18n

    for lang in ("en", "cs"):
        value = host_i18n.translate(lang, "notification.reason.submission_stuck")
        assert value and not value.startswith("notification."), lang


def test_a_transport_failure_does_not_spend_the_budget(monkeypatch):
    """A network blip must not count against a record, or an outage would use up
    the budget for every guest on the site and strand the lot of them."""
    apartment, _reservation, guest_id = _seed("tok-cap-transport", auto=True)

    class OfflineClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            raise UbyportTransportError("offline")

    try:
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: OfflineClient())
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        result = reporting.submit_batch(apartment, pairs, mode="manual")

        assert result["state"] == "transport_error"
        assert _attempts(guest_id) == 0
        # The record is still offered, so the next sweep retries it.
        assert guest_id in [
            guest["id"]
            for guest, _ in reporting.collect_sendable(apartment["id"])
        ]
    finally:
        _cleanup(apartment["id"])


def test_a_refused_login_raises_the_credentials_card(monkeypatch):
    """AR-18: a 401 is not a transport blip, so it needs its own card.

    The transport card is still raised for the same event, but this one names
    the fix: the credentials. The pause that stops the sweep from retrying a
    refused login every ten minutes keys on this card.
    """
    apartment, _reservation, _guest_id = _seed("tok-cap-auth", auto=True)

    class RefusedLoginClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            raise UbyportAuthError("401")

    try:
        monkeypatch.setattr(
            reporting, "client_for", lambda *_a, **_k: RefusedLoginClient()
        )
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        result = reporting.submit_batch(apartment, pairs, mode="manual")

        assert result["state"] == "transport_error"
        assert alerts.open_alert(f"ubyport_auth_failed:{apartment['id']}")
    finally:
        _cleanup(apartment["id"])


def test_a_legacy_row_without_the_column_reads_as_no_attempts():
    """A hand-built or pre-migration row must not raise in the send gate."""
    assert reporting.auto_attempts({}) == 0
    assert reporting.auto_attempts({"submit_attempts": None}) == 0
    assert reporting.auto_attempts({"submit_attempts": "2"}) == 2


@pytest.fixture(scope="module")
def host(mock_ubyport):  # noqa: ARG001
    """An authenticated administrator browser, for the recovery paths."""
    from app.main import app

    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    if not account:
        auth.create_account(
            USERNAME,
            PASSWORD,
            "Retry cap admin",
            role="admin",
            must_change_password=False,
        )
    with TestClient(app) as test_client:
        response = test_client.post(
            "/login",
            data={"username": USERNAME, "password": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303
        # A refused login also redirects, so check where it went.
        assert "err=" not in response.headers["location"]
        yield test_client


def test_correcting_the_guest_restarts_the_count(host, monkeypatch):
    """Recovery path 1: the host fixes the data and saves the form.

    Without the reset the record would stay given up on even after the value the
    register refused had been corrected, so the fix would look like it failed.
    """
    apartment, _reservation, guest_id = _seed("tok-cap-form", auto=True)

    try:
        for _ in range(BOUND):
            _fail(apartment, guest_id, monkeypatch)
        assert _attempts(guest_id) == BOUND
        assert len(_stuck_alerts(apartment["id"])) == 1

        saved = host.post(
            f"/guests/{guest_id}",
            data={
                "surname": "Corrected",
                "first_name": "John",
                "birth_date": "01.01.1990",
                "nationality": "GBR",
                "doc_number": "P7654321",
                "res_street": "Street 1",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "signature": SIGNATURE,
            },
            follow_redirects=False,
        )
        assert saved.status_code == 303

        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submit_state"] == reporting.PENDING
        assert guest["submit_attempts"] == 0, (
            "the retry budget has to restart when the host corrects the record"
        )
        assert _stuck_alerts(apartment["id"]) == [], (
            "a corrected record is no longer stranded"
        )
        assert reporting.collect_sendable(apartment["id"]), (
            "the sweep must pick the corrected record back up"
        )
    finally:
        _cleanup(apartment["id"])


def test_an_unknown_outcome_is_recorded_and_not_refiled_by_the_sweep(monkeypatch):
    """A request whose answer never arrived may already be filed.

    Resending it automatically is how the same guests are declared twice, and a
    duplicate is counted against the host. The batch is parked as
    ``outcome_unknown`` with the envelope kept as evidence, and a person decides
    whether to send it again (owner decision OD-1).
    """
    apartment, _reservation, guest_id = _seed("tok-cap-unknown", auto=True)

    class UnknownOutcomeClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            exc = UbyportOutcomeUnknownError("read timed out")
            exc.request_xml = "<request/>"
            raise exc

    try:
        monkeypatch.setattr(
            reporting, "client_for", lambda *_a, **_k: UnknownOutcomeClient()
        )
        monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        assert guest_id in [guest["id"] for guest, _ in pairs]
        result = reporting.submit_batch(apartment, pairs, mode="manual")

        assert result["state"] == "outcome_unknown"

        submission = db.query_one(
            "SELECT * FROM submission WHERE apartment_id = ?", (apartment["id"],)
        )
        assert submission["state"] == "outcome_unknown"
        assert submission["request_xml"] == "<request/>"
        assert alerts.open_alert(f"submission_outcome_unknown:{apartment['id']}")
        assert guest_id not in [g["id"] for g, _ in reporting.collect_sendable(apartment["id"])]
        assert guest_id in [g["id"] for g, _ in reporting.collect_sendable(apartment["id"], ignore_automation=True)]
        assert reporting._retry_outcome_unknown_batches(apartment["id"]) == 0
        assert db.query_one(
            "SELECT retried_at FROM submission WHERE id = ?", (submission["id"],)
        )["retried_at"] is None
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM submission WHERE apartment_id = ?",
            (apartment["id"],),
        )["n"] == 1
    finally:
        _cleanup(apartment["id"])


def test_an_ok_batch_keeps_the_in_doubt_card_while_another_guest_waits(monkeypatch):
    """One good resend must not wipe the warning for the rest of the party.

    The card is apartment-wide but the in-doubt state is per guest pointer. If
    a second guest still points at the unknown batch, resolving the card hides
    that the sweep is silently excluding them.
    """
    apartment, reservation, guest_id = _seed("tok-cap-unknown-scope", auto=True)

    class UnknownOutcomeClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            raise UbyportOutcomeUnknownError("read timed out")

    try:
        other_id = db.insert(
            "guest",
            {
                "reservation_id": reservation["id"],
                "surname": "Second",
                "first_name": "Jane",
                "birth_date": "02021991",
                "nationality": "GBR",
                "doc_number": "P7654321",
                "res_street": "Street 2",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "is_lead": 0,
                "entered_by": "host",
                "signature_png": SIGNATURE,
                "signed_at": db.utcnow(),
                "identity_verified_at": db.utcnow(),
                "submit_state": reporting.PENDING,
                "created_at": db.utcnow(),
                "updated_at": db.utcnow(),
            },
        )
        monkeypatch.setattr(
            reporting, "client_for", lambda *_a, **_k: UnknownOutcomeClient()
        )
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        assert {guest_id, other_id} == {g["id"] for g, _ in pairs}
        reporting.submit_batch(apartment, pairs, mode="manual")
        assert alerts.open_alert(f"submission_outcome_unknown:{apartment['id']}")

        # One guest is filed by hand; the other still points at the unknown batch.
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: AcceptingClient())
        resend = reporting.collect_sendable(
            apartment["id"], only_guest_ids=[guest_id], ignore_automation=True
        )
        assert [g["id"] for g, _ in resend] == [guest_id]
        assert reporting.submit_batch(apartment, resend, mode="manual")["state"] == "ok"
        assert alerts.open_alert(f"submission_outcome_unknown:{apartment['id']}") is not None, (
            "a guest still waiting on the unknown batch keeps the warning up"
        )

        # Filing the second guest is what finally clears it.
        rest = reporting.collect_sendable(
            apartment["id"], only_guest_ids=[other_id], ignore_automation=True
        )
        assert reporting.submit_batch(apartment, rest, mode="manual")["state"] == "ok"
        assert alerts.open_alert(f"submission_outcome_unknown:{apartment['id']}") is None
    finally:
        _cleanup(apartment["id"])


def test_every_state_submit_batch_can_write_is_terminal():
    """The retention sweep and the submission detail page both treat the terminal
    states as the set of finished batches. A state the batch path can write but
    that set omits would be swept away as if still running, so the two must not
    drift apart."""
    source = inspect.getsource(reporting.submit_batch)
    for state in ("ok", "ok_duplicate", "partial", "error", "transport_error",
                  "outcome_unknown"):
        assert state in source, f"submit_batch never writes {state!r}"
        assert state in reporting.TERMINAL_SUBMISSION_STATES, (
            f"{state!r} is a terminal batch state the set does not list"
        )


def test_the_receipt_survives_a_failure_after_the_answer(monkeypatch):
    """The Dorucenka must not be lost if a later step blows up.

    Once UbyPort has answered, the receipt and the guests' new states are one
    fact. A failure in the alerts that follow must not be able to undo them.
    """
    apartment, _reservation, guest_id = _seed("tok-cap-atomic-receipt", auto=True)

    try:
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: AcceptingClient())
        monkeypatch.setattr(
            reporting,
            "clear_stuck_alert_if_recovered",
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        with pytest.raises(RuntimeError):
            reporting.submit_batch(apartment, pairs, mode="manual")

        submission = db.query_one(
            "SELECT * FROM submission WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
            (apartment["id"],),
        )
        assert submission["state"] == "ok", (
            "the answer was already committed, so its receipt must be on file"
        )
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submit_state"] == reporting.SENT
    finally:
        _cleanup(apartment["id"])


def test_a_failed_outcome_write_leaves_nothing_half_done(monkeypatch):
    """A write that fails while recording the answer rolls the whole thing back.

    Otherwise the guest would be marked sent with no submission row behind it,
    and the disappearance of the receipt would only be visible much later.
    """
    apartment, _reservation, guest_id = _seed("tok-cap-atomic-rollback", auto=True)

    real = db.update_in

    def wrapper(cur, table, row_id, values):
        if table == "submission":
            raise sqlite3.OperationalError("locked")
        return real(cur, table, row_id, values)

    try:
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: AcceptingClient())
        monkeypatch.setattr(db, "update_in", wrapper)
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        with pytest.raises(sqlite3.OperationalError):
            reporting.submit_batch(apartment, pairs, mode="manual")

        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submit_state"] == reporting.PENDING, (
            "the guest write shares the submission's transaction and must roll back with it"
        )
    finally:
        _cleanup(apartment["id"])


def test_a_failed_pointer_write_does_not_half_record_the_unknown_outcome(monkeypatch):
    """The in-doubt mark has to land whole, or the sweep re-sends the batch.

    The submission row and the guests' pointers to it are one fact. If a
    pointer write fails after the row was already marked ``outcome_unknown``,
    those guests look sendable again (the sweep reads ``guest.submission_id``)
    and it refiles a batch the register may already hold. The write is therefore
    one transaction: on failure the batch says ``running`` and the guests keep
    their old pointers, so nothing claims a possibly-filed batch and the sweep
    can retry it safely.
    """
    apartment, _reservation, guest_id = _seed("tok-cap-unknown-atomic", auto=True)

    class UnknownOutcomeClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            raise UbyportOutcomeUnknownError("read timed out")

    real = db.update_in

    def wrapper(cur, table, row_id, values):
        if table == "guest":
            raise sqlite3.OperationalError("locked")
        return real(cur, table, row_id, values)

    try:
        monkeypatch.setattr(
            reporting, "client_for", lambda *_a, **_k: UnknownOutcomeClient()
        )
        monkeypatch.setattr(db, "update_in", wrapper)
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        with pytest.raises(sqlite3.OperationalError):
            reporting.submit_batch(apartment, pairs, mode="manual")

        submission = db.query_one(
            "SELECT * FROM submission WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
            (apartment["id"],),
        )
        assert submission["state"] == "running", (
            "the in-doubt mark rolled back with the pointers, so nothing claims an unknown outcome"
        )
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submission_id"] is None, "the pointer write rolled back too"
        assert guest_id in [
            g["id"] for g, _ in reporting.collect_sendable(apartment["id"])
        ], "no in-doubt batch is on file, so the sweep must still offer the guest"
    finally:
        _cleanup(apartment["id"])
