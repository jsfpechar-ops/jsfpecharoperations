"""UX-61 (A-25): the things a guest taps have to be thumb-sized.

The back link, the signature "Clear", the host's phone and e-mail, and a folded
message summary were all as tall as their own text - 20-odd pixels, which is
half of what a thumb needs. Nothing here changes what the guest has to do; it
only stops the small targets from being small.
"""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db
from app.main import app

TOKEN = "taptargettoken"
CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "guest.css"
PHONE = "+420 777 123 456"
EMAIL = "host@example.test"


def _rule(selector: str) -> str:
    """The body of one CSS rule, so a property can be asserted where it lives."""
    text = CSS.read_text(encoding="utf-8")
    match = re.search(
        r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", text
    )
    assert match, f"{selector} is gone from guest.css"
    return match.group(1)


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
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Tap Target Test",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Tap Target Test",
            "contact_phone": PHONE,
            "contact_email": EMAIL,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Tap apartment",
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
            "uid": "tap-1",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=4)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return reservation_id


def test_the_back_link_is_a_thumb_sized_target():
    assert "min-height: 44px" in _rule(".g-back")


def test_the_signature_clear_button_is_a_thumb_sized_target():
    assert "min-height: 44px" in _rule(".g-sign .bar button")


def test_a_folded_summary_is_a_thumb_sized_target():
    """One rule covers the host message, the explainer and the arrival note."""
    assert "min-height: 44px" in _rule(".g-fold > summary")
    assert "min-height: 44px" in _rule(".g-arrival-message summary")


def test_the_hosts_phone_and_email_are_thumb_sized_targets():
    assert "min-height: 44px" in _rule("#host-contact a")


def test_a_phone_number_is_dialable_as_written():
    """`tel:` may not carry the spaces we show the guest."""
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        page = browser.get(f"/l/{TOKEN}/{reservation_id}/new?lang=en")
        assert page.status_code == 200
        assert f'href="tel:+420777123456"' in page.text
        assert "tel:+420 777" not in page.text
        # The guest still reads the number the way a human writes it.
        assert PHONE in page.text
        assert f'href="mailto:{EMAIL}"' in page.text
    finally:
        _cleanup()
