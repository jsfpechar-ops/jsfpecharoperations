"""UX-57 (A-21): the kept-signature reassurance stops looking like an error.

When a save is rejected the form comes back with the guest's signature already
painted, and says so. That sentence was written into the same red, bold, alert
line that carries the "please sign" error, so a reassurance was shouted in the
colour of a problem - and because the line was no longer empty, the wizard
opened on the signature step and stole focus as if something were wrong.
"""
from __future__ import annotations

import base64
import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db, i18n
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "sigkepttok"
ASSETS = Path(__file__).resolve().parents[1] / "app" / "static"
EN = "Your signature is saved. Sign again only if you want to change it."
CS = "Podpis máme uložený. Znovu se podepište, jen pokud ho chcete změnit."
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


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
        ("Signature Kept",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Signature Kept", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Signature flat",
            "uby_name": "Signature Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "signature-kept-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _rejected_page_with_signature(lang: str) -> str:
    """A save that fails on a name, so the form comes back with the pad intact."""
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, lang)
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang=lang)
        response = browser.post(
            f"/l/{TOKEN}/{reservation_id}/save?lang={lang}",
            data={
                "surname": "",
                "first_name": "John Paul",
                "birth_date": "1.1.1990",
                "nationality": "GBR",
                "doc_number": "P1234567",
                "res_street": "Baker Street 221B",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "party_size": "2",
                "signature": SIGNATURE,
                "legal_ack": "1",
            },
        )
        assert response.status_code == 422
        return response.text
    finally:
        _cleanup()


# --- the copy -------------------------------------------------------------


def test_the_english_reassurance_is_the_new_wording():
    assert i18n.translator("en")("signature_kept") == EN


def test_the_czech_reassurance_has_its_comma():
    assert i18n.translator("cs")("signature_kept") == CS
    assert "podepište, jen pokud" in CS


def test_both_languages_still_carry_the_key():
    for lang in i18n.LANGUAGES:
        assert i18n.translator(lang)("signature_kept") != "signature_kept"


def test_the_czech_reassurance_is_not_the_english_one():
    assert CS != EN


# --- the page hands the reassurance to the script -------------------------


def test_the_rejected_form_keeps_the_signature_and_its_reassurance():
    page = _rejected_page_with_signature("en")
    assert f'data-kept="{EN}"' in page
    signature = re.search(r'id="signature"[^>]*value="([^"]*)"', page)
    assert signature, "the signature field is not on the page"
    assert signature.group(1).startswith("data:image/"), (
        "the signature was not carried over, so the kept message never shows"
    )


def test_the_czech_page_carries_the_czech_reassurance():
    page = _rejected_page_with_signature("cs")
    assert f'data-kept="{CS}"' in page


def test_the_error_line_still_starts_as_an_error():
    """The line's first possible message is the "please sign" error."""
    page = _rejected_page_with_signature("en")
    tag = re.search(r'<span id="sig-status"[^>]*>', page)
    assert tag, "the signature status line is missing"
    assert 'class="err"' in tag.group(0)
    assert 'role="alert"' in tag.group(0)
    assert 'data-missing="' in tag.group(0)


# --- and the script dresses the line to match the message -----------------


def test_the_kept_message_is_dressed_as_a_hint_not_an_alert():
    script = (ASSETS / "signature.js").read_text(encoding="utf-8")
    assert "function setSignatureStatus(" in script
    assert 'status.className = hint ? "hint" : "err";' in script
    assert 'status.setAttribute("role", hint ? "status" : "alert");' in script
    assert 'getAttribute("data-kept") || "" : "", "hint"' in script, (
        "the kept reassurance is not written as a hint"
    )


def test_the_missing_message_still_shouts():
    script = (ASSETS / "signature.js").read_text(encoding="utf-8")
    assert script.count('getAttribute("data-missing") || "" : "", "err"') == 2, (
        "both the wizard guard and the submit guard must write an error"
    )


def test_a_hint_in_the_signature_bar_is_not_painted_red():
    css = (ASSETS / "guest.css").read_text(encoding="utf-8")
    match = re.search(r"\.g-sign \.bar \.hint \{([^}]*)\}", css)
    assert match, "the hint state of the signature bar has no styling"
    assert "--g-bad" not in match.group(1)
    assert "font-weight" not in match.group(1)


def test_the_error_state_still_opens_the_signature_step():
    """Only the error class counts as a reason to jump to the step."""
    script = (ASSETS / "signature.js").read_text(encoding="utf-8")
    assert ".g-sign .err:not(:empty)" in script
    assert 'step.querySelector(".bad, .err:not(:empty)")' in script
    assert ".hint:not(:empty)" not in script
