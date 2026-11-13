"""Children on the guest form enter their own document (owner, 2026-11-13).

UbyPort refused a child filed as INPASS ("Nekorektní číslo cestovního
dokladu") and the police helpdesk did not know INPASS, so the "child on a
parent's passport" box is gone. Every guest types their own passport or ID
card number; only a Czech child under 15, who is never reported and need not
hold an ID card, may leave it empty.
"""
from __future__ import annotations

import base64
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


# --- the box is gone ----------------------------------------------------------


def test_the_form_has_no_parent_passport_box():
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang="en")
        page = browser.get(f"/l/{TOKEN}/{reservation_id}?lang=en").text
    finally:
        _cleanup()
    assert 'id="doc_number"' in page
    assert "child_in_passport" not in page and "parent_doc_number" not in page
    script = (ASSETS / "signature.js").read_text(encoding="utf-8")
    assert "child_in_passport" not in script and "parent_doc_number" not in script


def test_a_typed_inpass_is_refused_under_the_document_box():
    """INPASS is left to the host form; a guest has no note box for the parent's number."""
    page = _page("en", nationality="POL", res_country="POL", birth_date="22.10.2009", doc_number="inpass")
    assert 'id="doc_number-error"' in page
    assert "Enter this person&#39;s own passport or ID card number." in page or (
        "Enter this person's own passport or ID card number." in page
    )


def test_the_refusal_is_in_the_guests_language():
    page = _page("cs", nationality="POL", res_country="POL", birth_date="22.10.2009", doc_number="INPASS")
    assert "Zadejte číslo vlastního pasu nebo občanského průkazu této osoby." in page


def test_the_note_issue_is_shown_under_the_document_box():
    issues = guest._localize_issues([validation.Issue("note", NOTE_MESSAGE)], "en")
    assert [(i.field, i.message) for i in issues] == [
        ("doc_number", "Enter this person's own passport or ID card number.")
    ]


def test_a_foreign_child_without_a_document_is_refused():
    page = _page("en", nationality="POL", res_country="POL", birth_date="22.10.2019", doc_number="")
    assert 'id="doc_number-error"' in page


def test_a_czech_child_under_15_without_a_document_is_saved():
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang="en")
        response = browser.post(
            f"/l/{TOKEN}/{reservation_id}/save?lang=en",
            data=_payload(
                nationality="CZE", res_country="CZE", res_street="Dlouha 1", res_city="Praha",
                birth_date="15.6.2019", doc_number="",
            ),
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text[:300]
        row = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (reservation_id,))
        assert row["doc_number"] in ("", None)
    finally:
        _cleanup()


def test_a_polish_passport_typed_with_spaces_and_lowercase_is_saved():
    """FC 4296103 as the guest's father typed it on 2026-11-13."""
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang="en")
        response = browser.post(
            f"/l/{TOKEN}/{reservation_id}/save?lang=en",
            data=_payload(
                nationality="POL", res_country="POL", birth_date="22.10.2009", doc_number="fc 4296-103",
            ),
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text[:300]
        row = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (reservation_id,))
        assert row["doc_number"] == "FC4296103"
    finally:
        _cleanup()


def test_a_refused_guest_save_logs_the_field_names_and_nothing_else(caplog):
    """Owner 2026-11-13: a refusal must be traceable without logging guest data."""
    with caplog.at_level("INFO", logger="ubyhost.guest"):
        _page("en", nationality="POL", res_country="POL", doc_number="INPASS")
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("guest_form_refused")]
    assert lines == ["guest_form_refused fields=doc_number"]
    assert TOKEN not in lines[0]


def test_a_missing_document_logs_doc_number_not_the_typed_value(caplog):
    with caplog.at_level("INFO", logger="ubyhost.guest"):
        _page(
            "en",
            nationality="POL",
            res_country="POL",
            birth_date="22.10.2019",
            doc_number="",
        )
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("guest_form_refused")]
    assert lines == ["guest_form_refused fields=doc_number"]
    assert "Smith" not in "\n".join(lines)
    assert "Pol" not in "\n".join(lines).lower()


def test_several_refused_fields_log_sorted_names_only(caplog):
    with caplog.at_level("INFO", logger="ubyhost.guest"):
        _page("en", surname="", doc_number="")
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("guest_form_refused")]
    assert len(lines) == 1
    assert lines[0] == "guest_form_refused fields=doc_number,surname"
