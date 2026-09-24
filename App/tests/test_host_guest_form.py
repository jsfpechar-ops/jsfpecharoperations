"""Hosts can open the guest form from stay menus without the PIN gate."""
from __future__ import annotations

import base64
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, reporting, validation
from app.main import app

PASSWORD = "Secure-Password-123"
TOKEN = "hostform-token"
PIN = "246810"

# A real 1x1 PNG: the save paths check the magic bytes now, not just the prefix.
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
SVG_SIGNATURE = "data:image/svg+xml;base64," + base64.b64encode(
    b"<svg xmlns='http://www.w3.org/2000/svg'/>"
).decode()


@pytest.fixture
def pin_required(monkeypatch):
    monkeypatch.setenv("UBYHOST_GUEST_PIN", "1")
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    # A save that succeeds writes an audit row and can raise an alert, and both
    # point at the owner account, so the account cannot go first.
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (apartment["owner_user_id"],))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (apartment["owner_user_id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    if apartment["legal_entity_id"]:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
    db.execute("DELETE FROM user_account WHERE username = ?", ("host-guest-form",))


def _host_stay():
    db.init_db()
    _cleanup()
    db.execute("DELETE FROM user_account WHERE username = ?", ("host-guest-form",))
    owner_id = auth.create_account(
        "host-guest-form", PASSWORD, role="host", must_change_password=False
    )
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Host Form s.r.o.",
            "seat": "Prague",
            "ico": "12345678",
            "contact_email": "host@example.com",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Host Form Studio",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "host-form-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner_id, stay_id


def _host_client(owner_id: int) -> TestClient:
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )
    return client


def test_guest_still_needs_pin_without_a_host_session(pin_required):
    _owner_id, stay_id = _host_stay()
    try:
        guest = TestClient(app)
        page = guest.get(f"/l/{TOKEN}/{stay_id}", follow_redirects=False)
        assert page.status_code == 200
        assert "PIN" in page.text
    finally:
        _cleanup()


def test_signed_in_host_opens_guest_form_without_pin(pin_required):
    owner_id, stay_id = _host_stay()
    try:
        client = _host_client(owner_id)
        overview = client.get("/")
        assert overview.status_code == 200
        assert f'href="/l/{TOKEN}/{stay_id}"' in overview.text
        assert "Open guest form" in overview.text

        stay = client.get(f"/reservations/{stay_id}")
        assert stay.status_code == 200
        assert "Open guest form" in stay.text

        form = client.get(f"/l/{TOKEN}/{stay_id}", follow_redirects=True)
        assert form.status_code == 200
        assert 'name="pin"' not in form.text
        assert f"/l/{TOKEN}/{stay_id}/save" in form.text
    finally:
        _cleanup()


def _claimed_guest(stay_id: int) -> TestClient:
    """A browser that has followed the guest link and claimed the stay."""
    from tests.conftest import complete_guest_claim

    client = TestClient(app)
    complete_guest_claim(client, TOKEN, stay_id)
    return client


def _save(client: TestClient, stay_id: int, lang: str = "en", files=None, **fields):
    today = claim.prague_today()
    data = {
        "stay_from": today.isoformat(),
        "stay_to": (today + timedelta(days=2)).isoformat(),
        "party_size": "2",
    }
    data.update(fields)
    return client.post(
        f"/l/{TOKEN}/{stay_id}/save",
        params={"lang": lang},
        data=data,
        files=files,
        follow_redirects=False,
    )


def _complete_guest(**overrides) -> dict:
    """A payload the form accepts, so only the signature under test can fail."""
    fields = {
        "surname": "Smith",
        "first_name": "John",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "party_size": "1",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    fields.update(overrides)
    return fields


def _hidden_signature(html: str) -> str:
    """What the hidden signature field would post back."""
    tag = re.search(r'<input type="hidden" id="signature"[^>]*>', html, re.S)
    assert tag, "the form must render its hidden signature field"
    value = re.search(r'value="([^"]*)"', tag.group(0))
    return value.group(1) if value else ""


def _signature_error(html: str) -> str:
    """The message rendered against the signature field, if any.

    The signature pad carries ``signature_missing`` in a ``data-`` attribute for
    its script, so a plain "is this string in the page" check cannot tell the
    rendered error apart from that attribute.
    """
    match = re.search(r'id="signature-error">(.*?)</div>', html, re.S)
    return match.group(1).strip() if match else ""


def _host_guest(stay_id: int, **overrides) -> int:
    """A filed guest row, the way the host entry form leaves one."""
    values = {
        "reservation_id": stay_id,
        "surname": "Smith",
        "first_name": "John",
        "birth_date": "1990-01-01",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "signature_png": SIGNATURE,
        "entered_by": "host",
        "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    }
    values.update(overrides)
    return db.insert("guest", values)


def test_guest_save_refuses_a_stay_outside_the_booking():
    """stay_from/stay_to are hidden fields, so they arrive by hand or stale."""
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        year_ago = claim.prague_today() - timedelta(days=365)
        response = _save(client, stay_id, stay_from=year_ago.isoformat())
        assert response.status_code == 422
        assert "do not match your booking" in response.text

        far_ahead = claim.prague_today() + timedelta(days=365)
        response = _save(client, stay_id, stay_to=far_ahead.isoformat())
        assert response.status_code == 422
        assert "do not match your booking" in response.text
    finally:
        _cleanup()


def test_guest_save_accepts_the_booked_dates():
    """The in-range case must be untouched: the form still renders its own
    errors (an empty form is incomplete), but never the date one."""
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        response = _save(client, stay_id)
        assert response.status_code == 422
        assert "do not match your booking" not in response.text
    finally:
        _cleanup()


def test_the_stay_refusal_is_translated():
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        year_ago = claim.prague_today() - timedelta(days=365)
        response = _save(client, stay_id, lang="cs", stay_from=year_ago.isoformat())
        assert response.status_code == 422
        assert "neodpovídají vaší rezervaci" in response.text
        assert "do not match your booking" not in response.text
    finally:
        _cleanup()


def test_a_complete_guest_form_is_saved_and_locked():
    """The baseline the signature tests below measure against."""
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        response = _save(client, stay_id, **_complete_guest())
        assert response.status_code == 303, response.text

        guest = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,))
        assert guest["signature_png"] == SIGNATURE
        assert reporting.guest_has_signature(guest)
        assert reporting.guest_is_complete(guest, db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (stay_id,)
        ))
    finally:
        _cleanup()


def test_an_svg_signature_is_refused():
    """An SVG is an image type and a script container; nothing here renders one."""
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        response = _save(client, stay_id, **_complete_guest(signature=SVG_SIGNATURE))
        assert response.status_code == 422
        assert _signature_error(response.text) == validation.SIGNATURE_INVALID_MESSAGE
        # Refused, not stored, and not handed back for the next submit.
        assert db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,)) is None
        assert _hidden_signature(response.text) == ""
    finally:
        _cleanup()


def test_a_png_signature_whose_bytes_are_not_a_png_is_refused():
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        not_a_png = "data:image/png;base64," + base64.b64encode(b"<html>hi</html>").decode()
        response = _save(client, stay_id, **_complete_guest(signature=not_a_png))
        assert response.status_code == 422
        assert _signature_error(response.text) == validation.SIGNATURE_INVALID_MESSAGE
        assert db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,)) is None
    finally:
        _cleanup()


def test_an_oversized_signature_is_refused():
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        huge = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * validation.MAX_SIGNATURE_BYTES
        ).decode()
        response = _save(client, stay_id, **_complete_guest(signature=huge))
        assert response.status_code == 422
        assert _signature_error(response.text) == validation.SIGNATURE_INVALID_MESSAGE
        assert db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (stay_id,)) is None
    finally:
        _cleanup()


def test_the_signature_refusal_is_translated():
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        response = _save(
            client, stay_id, lang="cs", **_complete_guest(signature=SVG_SIGNATURE)
        )
        assert response.status_code == 422
        assert _signature_error(response.text) == (
            "Tento podpis se nepodařilo uložit. Podepište se znovu do podpisového pole."
        )
        assert validation.SIGNATURE_INVALID_MESSAGE not in response.text
    finally:
        _cleanup()


def test_a_stored_junk_signature_is_not_offered_back_to_the_guest():
    """[F33]: the re-render must not hand back a value the save paths reject."""
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        assert _save(client, stay_id, **_complete_guest()).status_code == 303
        guest_id = db.query_one(
            "SELECT id FROM guest WHERE reservation_id = ?", (stay_id,)
        )["id"]
        # A row written before the validator existed: a data:image/ prefix over
        # something that is not a signature. Incomplete, so it is still editable.
        # db.update, not raw SQL: doc_number is encrypted now.
        db.update(
            "guest", guest_id, {"signature_png": SVG_SIGNATURE, "doc_number": ""}
        )
        page = client.get(f"/l/{TOKEN}/{stay_id}/edit/{guest_id}", follow_redirects=False)
        assert page.status_code == 200
        assert _hidden_signature(page.text) == ""
    finally:
        _cleanup()


def test_a_stored_junk_signature_cannot_be_carried_forward():
    """Resubmitting the form must not turn a junk row into a signed one."""
    _owner_id, stay_id = _host_stay()
    try:
        client = _claimed_guest(stay_id)
        assert _save(client, stay_id, **_complete_guest()).status_code == 303
        guest_id = db.query_one(
            "SELECT id FROM guest WHERE reservation_id = ?", (stay_id,)
        )["id"]
        db.update(
            "guest", guest_id, {"signature_png": SVG_SIGNATURE, "doc_number": ""}
        )
        # No signature field at all, as a browser with an empty pad would post.
        response = _save(
            client, stay_id, guest_id=str(guest_id), **_complete_guest(signature="")
        )
        assert response.status_code == 422
        # "Please sign in the box before you continue." - the junk row is not a
        # signature.
        assert (
            _signature_error(response.text)
            == "Please sign in the box before you continue."
        )
        assert validation.SIGNATURE_INVALID_MESSAGE not in response.text
        assert db.query_one(
            "SELECT signature_png FROM guest WHERE id = ?", (guest_id,)
        )["signature_png"] == SVG_SIGNATURE
    finally:
        _cleanup()


def test_the_host_entry_form_refuses_a_bogus_signature():
    """The host save path shares the validator: a junk value is neither filed as
    a collected signature nor taken in place of a real one."""
    owner_id, stay_id = _host_stay()
    try:
        client = _host_client(owner_id)
        unsigned_id = _host_guest(stay_id, signature_png=None)
        response = client.post(
            f"/guests/{unsigned_id}",
            data=_complete_guest(signature=SVG_SIGNATURE),
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert validation.SIGNATURE_INVALID_MESSAGE in response.text
        # Refused, not stored, and not handed back for the next submit.
        assert not db.query_one(
            "SELECT signature_png FROM guest WHERE id = ?", (unsigned_id,)
        )["signature_png"]
        assert _hidden_signature(response.text) == ""

        # With a real signature already stored the junk post keeps it, rather
        # than replacing it with something nothing here can render.
        signed_id = _host_guest(stay_id)
        response = client.post(
            f"/guests/{signed_id}",
            data=_complete_guest(signature=SVG_SIGNATURE),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert db.query_one(
            "SELECT signature_png FROM guest WHERE id = ?", (signed_id,)
        )["signature_png"] == SIGNATURE
    finally:
        _cleanup()


def test_a_stored_junk_signature_is_not_offered_back_to_the_host():
    """[F33] on the host form too: an old row's junk value is not re-posted."""
    owner_id, stay_id = _host_stay()
    try:
        guest_id = _host_guest(stay_id, signature_png=SVG_SIGNATURE)
        client = _host_client(owner_id)
        page = client.get(f"/guests/{guest_id}", follow_redirects=False)
        assert page.status_code == 200
        assert _hidden_signature(page.text) == ""

        # A real signature still round-trips into the field.
        db.update("guest", guest_id, {"signature_png": SIGNATURE})
        page = client.get(f"/guests/{guest_id}", follow_redirects=False)
        assert _hidden_signature(page.text) == SIGNATURE
    finally:
        _cleanup()


def test_the_resign_warning_waits_for_every_guest_on_the_stay():
    """[F15] One guest's save must not clear another guest's stale signature.

    The calendar moved the stay, so the sync left a critical
    ``dates_changed_resign`` alert for the host. The guest form resolved that
    key on *any* save, so the first guest to touch the page hid the warning
    while the rest of the party still had the old dates on file.
    """
    from app import alerts

    _owner_id, stay_id = _host_stay()
    try:
        today = claim.prague_today()
        moved_from = (today + timedelta(days=30)).isoformat()
        moved_to = (today + timedelta(days=32)).isoformat()
        stale = {
            "stay_from": moved_from,
            "stay_to": moved_to,
        }
        first = _host_guest(stay_id, birth_date="01011990", **stale)
        second = _host_guest(stay_id, birth_date="01011990", **stale)
        key = f"dates_changed_resign:{stay_id}"
        alerts.raise_alert(
            "critical",
            "dates_changed_resign",
            "The calendar moved this stay.",
            "The signed form names the old dates.",
            dedupe_key=key,
            reservation_id=stay_id,
        )

        client = _claimed_guest(stay_id)
        # Claiming the stay rewrites declared_guests, so the party has to be
        # widened after it: while the party is unfinished a save still reaches
        # the resolve step, and the point here is the resolve, not capacity.
        db.update("reservation", stay_id, {"declared_guests": 5})
        assert _save(client, stay_id, **_complete_guest()).status_code == 303
        assert alerts.open_alert(key) is not None, "one save cannot clear the others"

        db.update("guest", first, {"stay_from": today.isoformat(), "stay_to": None})
        assert _save(client, stay_id, **_complete_guest()).status_code == 303
        assert alerts.open_alert(key) is not None, "the second guest is still stale"

        db.update("guest", second, {"stay_from": today.isoformat(), "stay_to": None})
        assert _save(client, stay_id, **_complete_guest()).status_code == 303
        assert alerts.open_alert(key) is None
    finally:
        _cleanup()


def test_a_stale_signature_is_not_filed_until_the_guest_re_signs():
    """[F15] Nothing blocked filing the old signature, so it reached the register.

    A row whose signed window has fallen outside the booking cannot be filed
    automatically, and neither can any row on a stay the calendar moved. A host
    pressing send is still the override, the same as it is for the retry cap.
    """
    from app import alerts

    _owner_id, stay_id = _host_stay()
    try:
        today = claim.prague_today()
        stay = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))
        apartment_id = stay["apartment_id"]
        # Inside the booking: a late arrival is a normal record.
        inside = _host_guest(
            stay_id,
            birth_date="01011990",
            stay_from=today.isoformat(),
            stay_to=(today + timedelta(days=1)).isoformat(),
        )
        # Outside it: the booking moved out from under this signature.
        outside = _host_guest(
            stay_id,
            birth_date="01011990",
            stay_from=(today + timedelta(days=30)).isoformat(),
            stay_to=(today + timedelta(days=32)).isoformat(),
        )
        db.update("reservation", stay_id, {"declared_guests": 5})

        offered = {
            g["id"]
            for g, _r in reporting.collect_sendable(
                apartment_id, ignore_schedule=True, allow_resend=True
            )
        }
        assert inside in offered
        assert outside not in offered

        key = f"dates_changed_resign:{stay_id}"
        alerts.raise_alert(
            "critical",
            "dates_changed_resign",
            "The calendar moved this stay.",
            "The signed form names the old dates.",
            dedupe_key=key,
            reservation_id=stay_id,
        )
        offered = {
            g["id"]
            for g, _r in reporting.collect_sendable(
                apartment_id, ignore_schedule=True, allow_resend=True
            )
        }
        assert offered == set(), "an open re-sign warning holds the whole stay"

        offered = {
            g["id"]
            for g, _r in reporting.collect_sendable(
                apartment_id,
                ignore_schedule=True,
                allow_resend=True,
                ignore_automation=True,
            )
        }
        assert inside in offered, "the host can still send by hand"
        assert outside not in offered
    finally:
        _cleanup()
