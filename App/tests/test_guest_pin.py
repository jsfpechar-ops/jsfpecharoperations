"""Guest PIN gate must cover every mutating route, not only GET pages."""
from __future__ import annotations

import base64
import re
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, passport_photos, rate_limit
from app.main import app, rotate_weak_permalinks
from tests.conftest import complete_guest_claim

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PNG_BYTES = base64.b64decode(SIGNATURE.split(",", 1)[1])

TOKEN = "pingate-token"
PIN = "432199"
LEGACY_PIN = "4321"


@pytest.fixture
def pin_required(monkeypatch):
    monkeypatch.setenv("UBYHOST_GUEST_PIN", "1")
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    guests = db.query("SELECT id FROM guest WHERE reservation_id IN "
                      "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment["id"],))
    for guest in guests:
        passport_photos.delete_photo(guest["id"])
    db.execute("DELETE FROM guest WHERE reservation_id IN "
               "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment["id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _stay_id() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "PIN gate test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "PIN flat",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "pin-gate-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _with_pin(client: TestClient) -> TestClient:
    response = client.post(
        f"/l/{TOKEN}/pin",
        data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_party_and_another_posts_require_pin(pin_required):
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        blocked = client.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "4"},
            follow_redirects=False,
        )
        assert blocked.status_code == 200
        assert "PIN" in blocked.text
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,)
        )["declared_guests"] is None

        blocked = client.post(f"/l/{TOKEN}/{stay_id}/another", follow_redirects=False)
        assert blocked.status_code == 200
        assert "PIN" in blocked.text

        client = _with_pin(TestClient(app))
        allowed = client.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "4", "guest_email": "guest@example.test"},
            follow_redirects=False,
        )
        assert allowed.status_code == 303
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,)
        )["declared_guests"] == 4
    finally:
        _cleanup()


def test_claim_secret_survives_the_pin_gate(pin_required):
    """The claim secret rides in the fragment, which the browser never sends
    to the server. ``signature.js`` copies it into ``return_to``, and the 303
    must hand it back — otherwise the guest lands on the confirm page with an
    empty secret and is told the link expired."""
    stay_id = _stay_id()
    secret = "A" * 32
    claim_path = f"/l/{TOKEN}/{stay_id}/claim"
    try:
        client = TestClient(app)
        gate = client.get(claim_path, follow_redirects=False)
        assert gate.status_code == 200
        assert "PIN" in gate.text
        assert f'value="{claim_path}"' in gate.text, "the PIN form must offer the claim page back"

        carried = f"{claim_path}#c={secret}"
        response = client.post(
            f"/l/{TOKEN}/pin",
            data={"pin": PIN, "return_to": carried},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == carried
    finally:
        _cleanup()


def test_pin_page_requires_six_digits(pin_required):
    """A 4-digit PIN is no longer a PIN.

    This inverts the assertion that used to live here: the test used to *require*
    that a legacy 4-digit PIN kept working, which is exactly the weakness F26
    names. Four digits is a 10^4 space, and with mail disabled the link plus PIN
    is the only boundary on the whole registration flow, so short PINs are now
    refused at the door, at the input pattern, and at startup (see
    ``test_startup_rotates_a_legacy_four_digit_pin``).
    """
    generated = auth.new_permalink_pin()
    assert len(generated) == 6
    assert auth.normalise_permalink_pin(generated) == generated
    assert auth.normalise_permalink_pin(LEGACY_PIN) is None
    assert auth.normalise_permalink_pin("12345") is None
    assert auth.normalise_permalink_pin("1234567") is None

    _stay_id()
    try:
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            (generated, TOKEN),
        )
        client = TestClient(app)
        page = client.get(f"/l/{TOKEN}", follow_redirects=False)
        assert page.status_code == 200
        field = re.search(r"<input[^>]*name=\"pin\"[^>]*>", page.text, re.S)
        assert field, "the PIN page should render a pin input"
        markup = field.group(0)
        assert 'maxlength="6"' in markup, markup
        assert 'pattern="[0-9]{6}"' in markup, markup
        assert "{4}" not in markup, markup

        accepted = client.post(
            f"/l/{TOKEN}/pin",
            data={"pin": generated, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert accepted.status_code == 303
    finally:
        _cleanup()


def test_startup_rotates_a_legacy_four_digit_pin(pin_required):
    """The normaliser is not on the guest path, so startup has to replace the stored value."""
    _stay_id()
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )["id"]
    try:
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            (LEGACY_PIN, TOKEN),
        )

        assert rotate_weak_permalinks() >= 1
        rotated = db.query_one(
            "SELECT permalink_pin FROM apartment WHERE permalink_token = ?", (TOKEN,)
        )["permalink_pin"]
        assert len(rotated) == 6 and rotated.isdigit()

        alert = db.query_one(
            "SELECT * FROM alert WHERE kind = ? AND apartment_id = ?",
            ("guest_pin_rotated", apartment_id),
        )
        assert alert is not None, "the host has to be told the PIN they sent out changed"

        # Idempotent: the rotated value is six digits, so a second run touches nothing.
        assert rotate_weak_permalinks() == 0
    finally:
        db.execute("DELETE FROM alert WHERE kind = ?", ("guest_pin_rotated",))
        _cleanup()


def test_pin_lockout_survives_a_fresh_ip(pin_required, monkeypatch):
    """Guessing across many source addresses must still lock the link."""
    _stay_id()
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", AsyncMock())
    try:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        for attempt in range(rate_limit._PIN_TOKEN_MAX_FAILURES):
            client = TestClient(app, client=(f"10.0.0.{attempt}", 50000))
            blocked = client.post(
                f"/l/{TOKEN}/pin",
                data={"pin": "000000", "return_to": f"/l/{TOKEN}"},
                follow_redirects=False,
            )
            assert blocked.status_code == 200

        # Every attempt came from a different address, so no per-IP window ever
        # filled: the only thing that can stop the next one is the token scope.
        assert rate_limit.pin_token_blocked(
            f"{TOKEN}:{auth.pin_fingerprint(TOKEN, PIN)}"
        )

        fresh = TestClient(app, client=("10.0.1.1", 50000))
        refused = fresh.post(
            f"/l/{TOKEN}/pin",
            data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert refused.status_code == 200, "the correct PIN must not open a locked link"
        assert 'name="pin"' in refused.text
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", ("pin_fail_token",))
        _cleanup()


def test_a_new_pin_lifts_the_lockout(pin_required, monkeypatch):
    """The host's regenerate-pin button has to be the remedy for a locked-out guest."""
    _stay_id()
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", AsyncMock())
    try:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        for attempt in range(rate_limit._PIN_TOKEN_MAX_FAILURES):
            TestClient(app, client=(f"10.0.0.{attempt}", 50000)).post(
                f"/l/{TOKEN}/pin",
                data={"pin": "000000", "return_to": f"/l/{TOKEN}"},
                follow_redirects=False,
            )
        assert rate_limit.pin_token_blocked(
            f"{TOKEN}:{auth.pin_fingerprint(TOKEN, PIN)}"
        )

        replacement = auth.new_permalink_pin()
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            (replacement, TOKEN),
        )

        assert not rate_limit.pin_token_blocked(
            f"{TOKEN}:{auth.pin_fingerprint(TOKEN, replacement)}"
        )
        allowed = TestClient(app, client=("10.0.1.1", 50000)).post(
            f"/l/{TOKEN}/pin",
            data={"pin": replacement, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert allowed.status_code == 303
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", ("pin_fail_token",))
        _cleanup()


def test_edit_form_requires_pin_before_owned_cookie(pin_required):
    stay_id = _stay_id()
    try:
        client = _with_pin(TestClient(app))
        complete_guest_claim(client, TOKEN, stay_id, party_size=1)
        saved = client.post(
            f"/l/{TOKEN}/{stay_id}/save",
            data={
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
            },
            files={"passport_photo": ("passport.png", PNG_BYTES, "image/png")},
            follow_redirects=False,
        )
        assert saved.status_code == 303
        guest_id = db.query_one(
            "SELECT id FROM guest WHERE reservation_id = ?", (stay_id,)
        )["id"]

        edit = TestClient(app)
        edit.cookies.update(client.cookies)
        edit.cookies.pop("ubyhost_pin", None)
        page = edit.get(f"/l/{TOKEN}/{stay_id}/edit/{guest_id}", follow_redirects=False)
        assert page.status_code == 200
        assert "PIN" in page.text
    finally:
        _cleanup()


def test_rotating_pin_invalidates_existing_pin_session(pin_required):
    _stay_id()
    try:
        client = _with_pin(TestClient(app))
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            ("654321", TOKEN),
        )

        page = client.get(f"/l/{TOKEN}", follow_redirects=False)

        assert page.status_code == 200
        assert 'name="pin"' in page.text
    finally:
        _cleanup()


def test_wrong_pin_delay_does_not_block_event_loop(pin_required, monkeypatch):
    _stay_id()
    delayed = AsyncMock()
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", delayed)
    try:
        response = TestClient(app).post(
            f"/l/{TOKEN}/pin",
            data={"pin": "9999"},
            follow_redirects=False,
        )

        assert response.status_code == 200
        delayed.assert_awaited_once()
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        _cleanup()


def test_with_turnstile_a_locked_link_is_challenged_not_refused(pin_required, monkeypatch):
    """One person with an old link must not shut every guest out for a day."""
    from app import turnstile

    _stay_id()
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", AsyncMock())
    monkeypatch.setattr(turnstile, "required", lambda: True)
    monkeypatch.setattr(turnstile, "verify", lambda _request, token, _action: token == "human")
    try:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        for attempt in range(rate_limit._PIN_TOKEN_MAX_FAILURES):
            TestClient(app, client=(f"10.0.0.{attempt}", 50000)).post(
                f"/l/{TOKEN}/pin",
                data={"pin": "000000", "cf-turnstile-response": "human", "return_to": f"/l/{TOKEN}"},
                follow_redirects=False,
            )
        assert rate_limit.pin_token_blocked(f"{TOKEN}:{auth.pin_fingerprint(TOKEN, PIN)}")

        guest = TestClient(app, client=("10.0.1.1", 50000))
        unchecked = guest.post(
            f"/l/{TOKEN}/pin", data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert unchecked.status_code == 200, "a locked link still needs the check"
        assert 'name="pin"' in unchecked.text
        checked = guest.post(
            f"/l/{TOKEN}/pin",
            data={"pin": PIN, "cf-turnstile-response": "human", "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert checked.status_code == 303
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", ("pin_fail_token",))
        _cleanup()
