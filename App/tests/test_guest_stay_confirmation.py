"""Guest stay flow after saving: confirmation, locked-form exits, soft duplicate warning.

QA findings guest-form-b-01, -02, -03 (back button and host contact only) and
-05. Editing or deleting a saved person is a separate owner decision and is not
covered here.
"""
from __future__ import annotations

import base64
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import claim, db, mail, reporting
from app.main import app
from app.routes import guest

TOKEN = "staycfmtok"
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
        ("Stay Confirm",),
    )


def _stay(apartment_id: int, uid: str, declared: int) -> int:
    today = claim.prague_today()
    now = db.utcnow()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": uid,
            "date_from": (today - timedelta(days=2)).isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "declared_guests": declared,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _seed(declared: int = 1) -> int:
    """A stay that began two days ago: outside the picker's lead window."""
    db.init_db()
    _cleanup()
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {"name": "Stay Confirm", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Confirm flat",
            "uby_name": "Confirm Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return _stay(apartment_id, "stay-confirm", declared)


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
        "party_size": "1",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _no_mail(monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    yield
    _cleanup()


def _client():
    client = TestClient(app)
    client.cookies.set(guest.LANG_COOKIE, "en")
    return client


def _save(client, rid, **overrides):
    return client.post(
        f"/l/{TOKEN}/{rid}/save?lang=en",
        data=_payload(**overrides),
        follow_redirects=True,
    )


def test_last_person_saved_shows_confirmation_not_404():
    rid = _seed(declared=1)
    client = _client()
    saved = _save(client, rid)
    assert saved.status_code == 200
    assert "no longer open" not in saved.text
    assert "data-dup-warning" not in saved.text
    # The same device can open the stay again; it is not a one-shot page.
    again = client.get(f"/l/{TOKEN}/{rid}?lang=en")
    assert again.status_code == 200


def test_another_device_still_gets_the_closed_page():
    rid = _seed(declared=1)
    _save(_client(), rid)
    assert _client().get(f"/l/{TOKEN}/{rid}?lang=en").status_code == 404


def test_same_document_number_warns_but_still_saves():
    rid = _seed(declared=2)
    client = _client()
    _save(client, rid, party_size="2")
    second = _save(client, rid, party_size="2", first_name="Mary", birth_date="2.2.1991")
    assert second.status_code == 200
    assert "data-dup-warning" in second.text
    assert "document number" in second.text
    rows = db.query("SELECT * FROM guest WHERE reservation_id = ?", (rid,))
    assert [r["doc_number"] for r in rows] == ["P1234567", "P1234567"]


def test_same_name_and_birth_date_warns():
    rid = _seed(declared=2)
    client = _client()
    _save(client, rid, party_size="2")
    second = _save(client, rid, party_size="2", doc_number="Q7654321")
    assert "data-dup-warning" in second.text
    assert "name and date of birth" in second.text


def test_different_people_get_no_warning():
    rid = _seed(declared=2)
    client = _client()
    _save(client, rid, party_size="2")
    second = _save(
        client, rid, party_size="2", first_name="Mary", birth_date="2.2.1991", doc_number="Q7654321"
    )
    assert "data-dup-warning" not in second.text


def test_warning_never_names_another_guest():
    rid = _seed(declared=2)
    _save(_client(), rid, party_size="2")
    page = _save(
        _client(), rid, party_size="2", first_name="Zed", surname="Other", birth_date="3.3.1980"
    )
    assert "data-dup-warning" in page.text
    warning = page.text.split("data-dup-warning", 1)[1].split("</div>", 1)[0]
    assert "Zed" in warning
    assert "John" not in warning and "Smith" not in warning


def test_locked_form_page_has_back_to_stay_and_host_contact(monkeypatch):
    rid = _seed(declared=2)
    client = _client()
    _save(client, rid, party_size="2")
    gid = db.query_one("SELECT id FROM guest WHERE reservation_id = ?", (rid,))["id"]
    monkeypatch.setattr(reporting, "guest_form_locked", lambda *a, **k: True)
    page = client.get(f"/l/{TOKEN}/{rid}/edit/{gid}?lang=en")
    assert page.status_code == 403
    assert "This form is locked" in page.text
    assert f'href="/l/{TOKEN}/{rid}?lang=en"' in page.text
    assert "data-back-to-stay" in page.text
    assert 'href="#host-contact"' in page.text
    assert 'id="host-contact"' in page.text


def test_wrong_device_page_has_back_to_stay():
    rid = _seed(declared=2)
    _save(_client(), rid, party_size="2")
    gid = db.query_one("SELECT id FROM guest WHERE reservation_id = ?", (rid,))["id"]
    page = _client().get(f"/l/{TOKEN}/{rid}/edit/{gid}?lang=en")
    assert page.status_code == 403
    assert "data-back-to-stay" in page.text
