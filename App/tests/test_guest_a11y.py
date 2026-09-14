"""The guest form is a legal duty, so it has to work without sight of it.

A guest using a screen reader or voice control gets the error summary at the
top today, but nothing ties a message to the control it belongs to. These
tests hold the programmatic link in place.
"""
from __future__ import annotations

import base64
import re
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import db
from app.main import app

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PNG_BYTES = base64.b64decode(SIGNATURE.split(",", 1)[1])

TOKEN = "a11ytoken"


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
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))


def _apartment():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert("legal_entity", {"name": "A11y Test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "A11y apartment",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "a11y-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return reservation_id


def _submit_with_errors() -> str:
    """Post a form that fails on two named fields, and return the re-render."""
    reservation_id = _apartment()
    browser = TestClient(app)
    page = browser.post(
        f"/l/{TOKEN}/{reservation_id}/save",
        data={
            "surname": "",
            "first_name": "John",
            "birth_date": "1.1.1990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "res_street": "Baker Street 221B",
            "res_city": "",
            "res_country": "GBR",
            "purpose": "10",
            "signature": SIGNATURE,
            "legal_ack": "1",
        },
        files={"passport_photo": ("passport.png", PNG_BYTES, "image/png")},
        follow_redirects=True,
    )
    # The re-render of a rejected form is a 422, not a redirect.
    assert page.status_code == 422
    return page.text


def test_a_field_that_failed_says_so_to_a_screen_reader():
    try:
        html = _submit_with_errors()
    finally:
        _cleanup()

    for field in ("surname", "res_city"):
        assert re.search(
            rf'id="{field}"[^>]*aria-invalid="true"', html
        ) or re.search(rf'aria-invalid="true"[^>]*id="{field}"', html), (
            f"{field} was rejected but is not marked invalid, so a screen reader "
            "reads it as an ordinary empty box"
        )


def test_the_message_is_tied_to_the_control_it_belongs_to():
    """aria-describedby has to point at an id that is really in the page."""
    try:
        html = _submit_with_errors()
    finally:
        _cleanup()

    described = re.findall(r'aria-describedby="([^"]+)"', html)
    assert described, "no control references its error message"
    ids = set(re.findall(r'id="([^"]+)"', html))
    for value in described:
        for target in value.split():
            assert target in ids, (
                f'aria-describedby points at "{target}", which is not in the page'
            )
    assert "surname-error" in described
    assert "res_city-error" in described


def test_a_field_that_passed_is_not_marked_invalid():
    try:
        html = _submit_with_errors()
    finally:
        _cleanup()

    assert not re.search(r'id="first_name"[^>]*aria-invalid="true"', html)


def test_the_guest_can_skip_straight_to_the_form():
    """Without a skip link every page starts with the language switch."""
    reservation_id = _apartment()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}/{reservation_id}", follow_redirects=True)
        assert page.status_code == 200
        assert 'class="skip-link"' in page.text
        target = re.search(r'class="skip-link" href="#([^"]+)"', page.text)
        assert target, "guest pages have no skip link"
        assert f'id="{target.group(1)}"' in page.text, "the skip link goes nowhere"
    finally:
        _cleanup()
