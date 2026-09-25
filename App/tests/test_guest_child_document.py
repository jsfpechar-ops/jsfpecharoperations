"""UX-56 (A-20): the child's missing parent number is caught before the save.

A child travelling on a parent's passport has no document number of its own, so
the form asks for the parent's instead. The box was never required and the
server's answer was keyed ``note`` — a field the guest form does not have, so
the message named a "note" nobody could see and the box it belonged to was left
unmarked. Now the box is required as soon as the child is declared, the message
names the box, and the box is what gets marked.
"""
from __future__ import annotations

import base64
import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db, validation
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "childdoctok"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
ASSETS = Path(__file__).resolve().parents[1] / "app" / "static"
NOTE_MESSAGE = (
    "For a child recorded in a parent's passport the note must contain "
    "the parent's document number."
)


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
        ("Child Document",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Child Document", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Child flat",
            "uby_name": "Child Facility",
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
            "uid": "child-document-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _payload(**overrides):
    data = {
        "surname": "Smith",
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
    }
    data.update(overrides)
    return data


def _page(lang: str, **overrides) -> str:
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, lang)
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang=lang)
        response = browser.post(
            f"/l/{TOKEN}/{reservation_id}/save?lang={lang}", data=_payload(**overrides)
        )
        assert response.status_code == 422
        return response.text
    finally:
        _cleanup()


def _child_without_parent(lang: str) -> str:
    return _page(lang, child_in_passport="1", doc_number="", parent_doc_number="")


# --- the issue is renamed onto the field the guest can see ------------------


def test_the_note_issue_becomes_the_parent_document_issue():
    issues = guest._localize_issues(
        [validation.Issue("note", NOTE_MESSAGE)], "en"
    )
    assert len(issues) == 1
    assert issues[0].field == "parent_doc_number"
    assert issues[0].message == "Enter the parent's passport or ID number."
    assert issues[0].severity == "error"


def test_the_czech_note_issue_says_the_same_thing():
    """The old CS sentence talked about a "poznámka" the guest cannot see."""
    issues = guest._localize_issues([validation.Issue("note", NOTE_MESSAGE)], "cs")
    assert issues[0].field == "parent_doc_number"
    assert issues[0].message == "Zadejte číslo pasu nebo průkazu rodiče."


def test_an_untouched_issue_is_left_alone():
    original = validation.Issue("surname", "Surname is required.", "warning")
    issues = guest._localize_issues([original], "en")
    assert issues[0].field == "surname"
    assert issues[0].message == "Surname is required."
    assert issues[0].severity == "warning"


def test_the_host_form_keeps_its_own_note_field():
    """``validation.py`` still keys it "note": the host column is called that."""
    child = {
        "surname": "Smith",
        "first_name": "Jane",
        "birth_date": "1.1.2015",
        "nationality": "GBR",
        "doc_number": validation.INPASS,
        "note": "",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
    }
    fields = {issue.field for issue in validation.validate_guest(child, None, None)}
    assert "note" in fields
    assert "parent_doc_number" not in fields


# --- the re-rendered form marks the box ------------------------------------


def test_the_rejected_form_marks_the_parent_box_invalid():
    page = _child_without_parent("en")
    tag = re.search(r"<input[^>]*id=\"parent_doc_number\"[^>]*>", page)
    assert tag, "the parent document box is not on the page"
    assert 'aria-invalid="true"' in tag.group(0), (
        "the parent document box was rejected but is not marked invalid"
    )
    assert 'aria-describedby="parent_doc_number-error"' in tag.group(0)
    assert re.search(r'class="[^"]*\bbad\b[^"]*"', tag.group(0)), (
        "the parent document box has no error styling"
    )


def test_the_rejected_form_puts_the_error_under_the_parent_box():
    page = _child_without_parent("en")
    assert 'id="parent_doc_number-error"' in page
    assert "Enter the parent&#39;s passport or ID number." in page or (
        "Enter the parent's passport or ID number." in page
    )
    # The "note" the guest never sees is gone from the page entirely.
    assert "must contain the parent" not in page
    assert 'id="note-error"' not in page


def test_the_czech_rejected_form_says_it_in_czech():
    page = _child_without_parent("cs")
    assert "Zadejte číslo pasu nebo průkazu rodiče." in page
    assert "must contain the parent" not in page


def test_the_summary_links_to_the_parent_box():
    page = _child_without_parent("en")
    match = re.search(r'<div class="g-err">.*?</div>', page, re.S)
    assert match
    assert 'href="#parent_doc_number"' in match.group(0)
    assert "Enter the parent's passport or ID number." in match.group(0) or (
        "Enter the parent&#39;s passport or ID number." in match.group(0)
    )


# --- and the box is required before the save -------------------------------


def test_the_parent_box_is_required_as_soon_as_the_child_is_declared():
    script = (ASSETS / "signature.js").read_text(encoding="utf-8")
    toggle = script.split("function initChildToggle()", 1)[1].split("\n  }", 1)[0]
    assert 'getElementById("parent_doc_number")' in toggle
    assert "parentInput.required = toggle.checked" in toggle
