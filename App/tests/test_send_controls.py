"""Send action rules for stay rows."""
from __future__ import annotations

import base64
import re
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import auth, db, reporting
from app.main import app
from app.ubyport.client import SubmissionResult
from tests.conftest import login_as


SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _seed(mode: str = "manual", token: str = "tok", owner_user_id: int | None = None):
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
            "owner_user_id": owner_user_id,
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


def test_empty_stay_tells_host_to_share_the_guest_link():
    apartment, reservation, guest_id = _seed("manual", "tok-empty")
    db.execute("DELETE FROM guest WHERE id = ?", (guest_id,))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["filled"] == 0
    assert controls["send_hint_key"] == "hint.awaiting_guest"
    assert controls["send_visible"] is False


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


def test_a_reported_stay_is_told_it_is_done_not_that_nothing_was_due():
    """The old hint said "no guest record is subject to the reporting duty".

    On a reported stay the same panel showed "2 reported · 2 subject to the
    duty" right below it, so the two halves of the page disagreed.
    """
    apartment, reservation, guest_id = _seed("manual", "tok-reported")
    db.update("guest", guest_id, {"submit_state": reporting.SENT})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "reported"
    assert progress["reportable"]
    assert controls["send_hint_key"] == "hint.all_reported"


def test_the_incomplete_hint_does_not_demand_a_passport_check():
    """DESIGN.md keeps the document check optional, and hint.ready_id_optional
    says so; the incomplete hint used to contradict both.
    """
    from app import host_i18n

    for lang in ("en", "cs"):
        copy = host_i18n.STRINGS[lang]
        assert "passport" not in copy["hint.not_ready"].lower()
        assert "pas" not in copy["hint.not_ready"].lower()
        assert "hint.all_reported" in copy
        assert "subject to the reporting duty" not in copy["hint.nothing_duty"]
        assert "předmětem hlášení" not in copy["hint.nothing_duty"]


def test_a_stay_short_of_its_guests_is_told_how_many_are_missing():
    """The incomplete hint talked about signatures even when the problem was a
    number: one guest registered where the host expected three.
    """
    apartment, reservation, _guest_id = _seed("manual", "tok-missing")
    db.update("reservation", reservation["id"], {"expected_guests_override": 3})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    progress = reporting.reservation_progress(reservation)
    controls = reporting.send_controls(reservation, apartment, progress)
    assert progress["status"] == "incomplete"
    assert (progress["filled"], progress["expected"]) == (1, 3)
    assert controls["send_hint_key"] == "hint.missing_guests"


def test_the_missing_guests_hint_names_the_counts_and_the_way_out():
    from app import host_i18n

    for lang in ("en", "cs"):
        copy = host_i18n.STRINGS[lang]["hint.missing_guests"]
        assert "%(filled)s" in copy and "%(expected)s" in copy
    rendered = host_i18n.translate("en", "hint.missing_guests", filled=1, expected=3)
    assert rendered.startswith("Guest forms: 1/3.")
    assert "lower the guest count" in rendered


def test_the_missing_guests_hint_offers_the_guest_count_it_talks_about():
    """The hint says "lower the guest count"; the field lives behind a
    collapsed disclosure, so the sentence has to carry a link to it.
    """
    db.init_db()
    username = "missingcount"
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    owner_id = existing["id"] if existing else auth.create_account(f"{username}@example.test", "Missing Count", username=username)
    _apartment, reservation, _guest_id = _seed(
        "manual", "tok-missing-page", owner_user_id=owner_id
    )
    db.update("reservation", reservation["id"], {"expected_guests_override": 3})
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303

    page = client.get(f"/reservations/{reservation['id']}")
    assert page.status_code == 200
    assert "2 guests missing" in page.text
    assert 'href="#stay-quick-edit" data-open-details' in page.text
    assert "Edit count" in page.text


def _bulk_send_button(html: str) -> str:
    match = re.search(r"<button[^>]*send-all.*?</button>", html, re.S)
    assert match, "the send-all button is missing from the reservations list"
    return match.group(0)


def _ready_count_from_page(html: str) -> int | None:
    label = re.search(r"\((\d+)\)", _bulk_send_button(html))
    return int(label.group(1)) if label else None


def test_the_ready_count_on_the_list_matches_what_the_bulk_action_can_send():
    """count_sendable_stays was deleted; the list derives the same number.

    The helper re-queried the apartment and checked it was active before
    counting a stay as sendable, so the derived count has to keep that guard:
    an archived apartment's otherwise-sendable stay is still not sendable.
    """
    db.init_db()
    username = "readycount"
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    owner_id = existing["id"] if existing else auth.create_account(f"{username}@example.test", "Ready Count", username=username)
    apartment, _reservation, _guest_id = _seed("manual", "tok-count", owner_user_id=owner_id)

    client = TestClient(app)
    login_as(client, username, follow_redirects=False)

    page = client.get("/reservations?range=all")
    assert page.status_code == 200
    assert _ready_count_from_page(page.text) == 1
    assert "disabled" not in _bulk_send_button(page.text)

    db.update("apartment", apartment["id"], {"active": 0})
    archived = client.get("/reservations?range=all")
    assert _ready_count_from_page(archived.text) is None
    assert "disabled" in _bulk_send_button(archived.text)


def test_scheduled_mode_waits_from_registration_completion():
    apartment, reservation, _guest_id = _seed("scheduled", "tok-completion-delay")
    completed = "2026-09-18T12:00:00+00:00"
    reporting.refresh_registration_completed_at(reservation["id"], completed)
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ?", (reservation["id"],)
    )

    assert not reporting.due_for_automatic_send(
        apartment,
        reservation,
        datetime(2026, 9, 19, 11, 59, tzinfo=timezone.utc),
    )
    assert reporting.due_for_automatic_send(
        apartment,
        reservation,
        datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
    )


def test_immediate_mode_sends_only_when_all_declared_forms_are_complete(monkeypatch):
    apartment, reservation, guest_id = _seed("immediate", "tok-completion-now")
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )
    db.update(
        "reservation",
        reservation["id"],
        {"expected_guests_override": 2, "registration_completed_at": None},
    )
    calls = []
    monkeypatch.setattr(
        reporting,
        "submit_for_apartment",
        lambda *args, **kwargs: calls.append((args, kwargs)) or [],
    )

    reporting.submit_stay_if_complete(apartment["id"], reservation["id"])
    assert calls == []
    assert not db.query_one(
        "SELECT registration_completed_at FROM reservation WHERE id = ?",
        (reservation["id"],),
    )["registration_completed_at"]

    db.update(
        "reservation", reservation["id"], {"expected_guests_override": 1}
    )
    reporting.submit_stay_if_complete(apartment["id"], reservation["id"])

    assert len(calls) == 1
    assert calls[0][0] == (apartment["id"],)
    assert calls[0][1]["only_guest_ids"] == [guest_id]
    # The completion trigger skips the wait, not the retry cap: it fires from
    # every save, so it must stop at SUBMISSION_MAX_AUTO_ATTEMPTS like the sweep.
    assert calls[0][1]["ignore_schedule"] is True
    assert calls[0][1].get("ignore_automation", False) is False
    assert db.query_one(
        "SELECT registration_completed_at FROM reservation WHERE id = ?",
        (reservation["id"],),
    )["registration_completed_at"]


def test_completion_timestamp_clears_if_party_becomes_incomplete(monkeypatch):
    _apartment, reservation, _guest_id = _seed(
        "scheduled", "tok-completion-reset"
    )
    reporting.refresh_registration_completed_at(
        reservation["id"], "2026-09-18T12:00:00+00:00"
    )
    # A form on file stops being complete - the guest changed a document number
    # to something the register rejects, say. That is the party being incomplete
    # again, and the stay is no longer ready to file. Editing a field of a form
    # that is still complete does not do this; see test_send_controls.py's
    # sibling case for the completion holding through an unrelated touch.
    monkeypatch.setattr(reporting, "guest_is_complete", lambda guest, res: False)

    assert reporting.refresh_registration_completed_at(reservation["id"]) is None
    assert not db.query_one(
        "SELECT registration_completed_at FROM reservation WHERE id = ?",
        (reservation["id"],),
    )["registration_completed_at"]


def test_delayed_automation_does_not_wait_for_identity_verification():
    apartment, reservation, guest_id = _seed(
        "scheduled", "tok-completion-unverified"
    )
    db.update(
        "guest",
        guest_id,
        {"identity_verified_at": None, "identity_verified_by": None},
    )
    completed = datetime.now(timezone.utc) - timedelta(hours=25)
    reporting.refresh_registration_completed_at(
        reservation["id"], completed.replace(microsecond=0).isoformat()
    )

    pairs = reporting.collect_sendable(apartment["id"])

    assert [guest["id"] for guest, _reservation in pairs] == [guest_id]
    assert not db.query_one(
        "SELECT identity_verified_at FROM guest WHERE id = ?", (guest_id,)
    )["identity_verified_at"]


def test_legacy_completed_reservation_is_not_auto_eligible_on_deploy():
    apartment, reservation, guest_id = _seed(
        "immediate", "tok-legacy-complete"
    )
    assert not reservation["registration_completed_at"]

    assert not reporting.due_for_automatic_send(apartment, reservation)
    assert reporting.collect_sendable(apartment["id"]) == []
    assert db.query_one(
        "SELECT submit_state FROM guest WHERE id = ?", (guest_id,)
    )["submit_state"] == reporting.PENDING
    assert not db.query_one(
        "SELECT registration_completed_at FROM reservation WHERE id = ?",
        (reservation["id"],),
    )["registration_completed_at"]


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


def test_accepted_records_are_never_collected_for_resend():
    """Duplicates are uncorrectable and count against the host (since 1 Sep 2025)."""
    apartment, reservation, guest_id = _seed("manual", "tok-sent")
    db.update("guest", guest_id, {"submit_state": reporting.SENT})

    assert reporting.collect_sendable(
        apartment["id"], only_guest_ids=[guest_id], ignore_automation=True
    ) == []
    # Only an explicit allow_resend reaches an already-accepted record.
    assert reporting.collect_sendable(
        apartment["id"],
        only_guest_ids=[guest_id],
        ignore_automation=True,
        allow_resend=True,
    )


def test_archived_guest_is_excluded_from_progress_and_send():
    apartment, reservation, guest_id = _seed("manual", "tok-archived-guest")
    db.update("guest", guest_id, {"archived_at": db.utcnow()})

    progress = reporting.reservation_progress(reservation)

    assert progress["filled"] == 0
    assert progress["status"] == "incomplete"
    assert reporting.collect_sendable(
        apartment["id"], only_guest_ids=[guest_id], ignore_automation=True
    ) == []


def test_archived_stay_is_never_collected_for_send():
    apartment, reservation, guest_id = _seed("manual", "tok-archived-stay")
    db.update("reservation", reservation["id"], {"archived_at": db.utcnow()})

    assert reporting.collect_sendable(
        apartment["id"], only_guest_ids=[guest_id], ignore_automation=True
    ) == []


def test_scheduler_sweep_cannot_resend():
    """The unattended path must never opt into duplicates."""
    import inspect

    signature = inspect.signature(reporting.collect_sendable)
    assert signature.parameters["allow_resend"].default is False
    signature = inspect.signature(reporting.submit_for_apartment)
    assert signature.parameters["allow_resend"].default is False

    source = inspect.getsource(reporting.sweep)
    assert "allow_resend" not in source, "sweep must not pass allow_resend"


def test_stay_submit_route_requires_duplicate_confirmation():
    """Whole-stay submit must not be a cheaper route around the resend gate."""
    import inspect

    from app.routes import admin

    source = inspect.getsource(admin.reservation_submit)
    assert "allow_resend" in source
    assert "confirm_duplicate" in source, (
        "re-sending accepted records from the stay page must be confirmed, "
        "like the single-guest resend route"
    )


def test_a_critical_transmission_error_leaves_the_guest_retryable(monkeypatch):
    """112 means the register never received the batch, so retrying is the fix.

    The police answered this in writing: 112 is a 1xx critical transmission
    error, the batch was not received at all, and the remedy is to correct the
    data and repeat the submission. Parking the guest in ``blocked`` would drop
    them from every future automatic send, so the declaration would never
    happen. This goes through ``submit_batch`` rather than ``classify`` because
    the state the host sees, and the send gate that acts on it, are the parts
    that matter.
    """
    apartment, _reservation, guest_id = _seed("manual", "tok-112")

    class FakeClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            return SubmissionResult(
                endpoint="test",
                request_xml="<request/>",
                response_xml="<response/>",
                record_errors=[";112;"],
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: FakeClient())
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])

    try:
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        assert guest_id in [guest["id"] for guest, _ in pairs]

        result = reporting.submit_batch(apartment, pairs, mode="manual")

        assert result["state"] == "error"
        assert result["blocked"] == 0
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submit_state"] == reporting.ERROR
        assert guest["submit_state"] != reporting.BLOCKED

        # The unattended sweep must pick the record back up: an ``error`` guest
        # is retried without anyone opting into a duplicate resend.
        again = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        assert guest_id in [guest["id"] for guest, _ in again]
    finally:
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))


def test_the_send_path_takes_no_actor():
    """Identity verification is a host attestation, so sending cannot make it.

    The parameter existed but was never read, and wiring it up would have let
    the unattended sweep stamp a verification, with the apartment owner's id,
    for a guest nobody had looked at.
    """
    import inspect

    for function in (reporting.submit_batch, reporting.submit_for_apartment):
        assert "verified_by_user_id" not in inspect.signature(function).parameters

    for phantom in (
        "maybe_submit_after_verify",
        "maybe_submit_after_host_save",
        "try_immediate_submit",
    ):
        assert not hasattr(reporting, phantom), (
            f"{phantom} should have been collapsed into submit_stay_if_complete"
        )


def test_the_verify_route_does_not_claim_to_trigger_a_submission():
    """The route used to call a function whose whole body was `return None`."""
    import inspect

    from app.routes import admin

    source = inspect.getsource(admin.guest_verify_identity)
    assert "submit_stay_if_complete" not in source
    assert "submit_for_apartment" not in source


def test_sending_does_not_stamp_identity_verification(monkeypatch):
    """A successful send is not an identity check.

    ``identity_verified_at`` records that a human compared the record with the
    guest's travel document. The scheduler sends without anyone doing that, so
    the field has to stay empty until the host presses Verify.
    """
    apartment, _reservation, guest_id = _seed("manual", "tok-no-actor")
    db.update("guest", guest_id, {"identity_verified_at": None, "identity_verified_by": None})

    class FakeClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            return SubmissionResult(
                endpoint="test",
                request_xml="<request/>",
                response_xml="<response/>",
                receipt_pdf="UEsDBAoAAAAAAA==",
                pseudo_stamp="20260101120000-abc",
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: FakeClient())
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])

    try:
        pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
        result = reporting.submit_batch(apartment, pairs, mode="manual")

        assert result["state"] == "ok"
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["submit_state"] == reporting.SENT
        assert guest["identity_verified_at"] is None
        assert guest["identity_verified_by"] is None
    finally:
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))


REFUSED_AT = "2026-09-20T10:00:00+00:00"


def _refuse_the_guest(
    apartment, guest_id, refused_at=REFUSED_AT, edited_at=None, state=reporting.ERROR
):
    """Park a stay's guest in the state UbyPort leaves behind after a refusal.

    A refusal stamps the guest and the submission with the same instant, so
    ``edited_at`` is what tells "nothing has changed" apart from "the host has
    fixed something since".
    """
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment["id"],
            "created_at": refused_at,
            "finished_at": refused_at,
            "mode": "manual",
            "state": "error",
        },
    )
    db.update(
        "guest",
        guest_id,
        {
            "submit_state": state,
            "last_errors": "106: Invalid value in a guest field",
            "submission_id": submission_id,
            "updated_at": edited_at or refused_at,
        },
    )
    return submission_id


def _controls_for(apartment, reservation):
    return reporting.send_controls(
        reservation, apartment, reporting.reservation_progress(reservation)
    )


def test_a_refused_stay_is_told_to_fix_first_not_that_it_is_ready():
    """A refusal is not "ready to report": the record has to be corrected first.

    ``failed`` is in ``sendable_statuses``, so the stay kept offering a coral
    "Send to UbyPort" beside a Rejected pill and the note still counted the
    guest as ready. The copy has to send the host to the fix instead.
    """
    apartment, reservation, guest_id = _seed("manual", "tok-refused")
    _refuse_the_guest(apartment, guest_id)

    controls = _controls_for(apartment, reservation)

    assert reporting.reservation_progress(reservation)["status"] == "failed"
    assert controls["send_enabled"] is True
    assert controls["send_hint_key"] == "hint.failed"
    assert controls["rejected_edited"] is False


def test_a_refusal_outranks_the_automation_note():
    """"Sends automatically" reads as "nothing for you to do" on a refusal."""
    apartment, reservation, guest_id = _seed("immediate", "tok-refused-auto")
    _refuse_the_guest(apartment, guest_id)

    controls = _controls_for(apartment, reservation)

    assert controls["send_hint_key"] == "hint.failed"
    assert controls["rejected_edited"] is False


def test_editing_a_refused_guest_makes_resending_worth_the_coral():
    """Only a fix post-dating the refusal promotes "Send again" to primary."""
    apartment, reservation, guest_id = _seed("manual", "tok-refused-edited")
    _refuse_the_guest(apartment, guest_id, edited_at="2026-09-20T11:30:00+00:00")

    controls = _controls_for(apartment, reservation)

    assert controls["rejected_edited"] is True


def test_a_blocked_guest_counts_as_a_refusal_too():
    """Duplicate and malformed records are parked in ``blocked``, not ``error``."""
    apartment, reservation, guest_id = _seed("manual", "tok-refused-blocked")
    _refuse_the_guest(apartment, guest_id, state=reporting.BLOCKED)

    controls = _controls_for(apartment, reservation)

    assert controls["send_hint_key"] == "hint.failed"
    assert controls["rejected_edited"] is False


def test_the_refused_stay_page_leads_with_the_fix_and_keeps_send_secondary():
    """The page, not just the controls: Fix first, "Send again" not coral yet."""
    db.init_db()
    username = "refusedpage"
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    owner_id = existing["id"] if existing else auth.create_account(f"{username}@example.test", "Refused Page", username=username)
    apartment, reservation, guest_id = _seed(
        "manual", "tok-refused-page", owner_user_id=owner_id
    )
    _refuse_the_guest(apartment, guest_id)

    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)

    body = client.get(f"/reservations/{reservation['id']}").text

    assert "UbyPort rejected a guest record." in body
    assert 'class="btn accent primary" href="#guests"' in body
    assert "Fix rejection" in body
    assert "Send again" in body
    assert body.index("Fix rejection") < body.index("Send again")
    # Nothing has been changed since the refusal, so the resend is not primary.
    assert 'class="btn accent primary" type="submit"' not in body
    assert "Send to UbyPort" not in body

    db.update("guest", guest_id, {"updated_at": "2026-09-20T12:00:00+00:00"})
    fixed = client.get(f"/reservations/{reservation['id']}").text

    assert 'class="btn accent primary" type="submit"' in fixed
    assert "Fix rejection" in fixed


def test_the_refusal_copy_ships_in_both_languages():
    """Read the catalogues directly: ``lookup`` returns raw text on a mismatch."""
    from app import host_i18n

    assert host_i18n.STRINGS["en"]["hint.failed"] == (
        "UbyPort rejected a guest record. Fix the details marked in red below, "
        "then send again."
    )
    assert host_i18n.STRINGS["cs"]["hint.failed"] == (
        "UbyPort odmítl záznam hosta. Opravte údaje označené červeně níže a "
        "odešlete znovu."
    )
    assert host_i18n.STRINGS["en"]["stay.detail.cta.send_again"] == "Send again"
    assert host_i18n.STRINGS["cs"]["stay.detail.cta.send_again"] == "Odeslat znovu"


def test_a_filed_czech_guest_is_not_flipped_to_not_required_by_the_sweep():
    """AR-19: a filed record keeps its state, which is the proof pointer.

    A guest's nationality can be corrected to CZE after the record has already
    reached the register. The sweep looked only at the nationality and
    overwrote ``sent`` with ``not_required``, losing both the fact and the
    proof pointer that the record had been filed.
    """
    apartment, _reservation, guest_id = _seed("manual", "tok-czech-filed")
    db.update(
        "guest",
        guest_id,
        {"nationality": "CZE", "submit_state": reporting.SENT},
    )

    reporting.collect_sendable(apartment["id"])

    assert db.query_one(
        "SELECT submit_state FROM guest WHERE id = ?", (guest_id,)
    )["submit_state"] == reporting.SENT
