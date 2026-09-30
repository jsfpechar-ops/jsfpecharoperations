"""Host-only document type field for the stay-fee register."""
from __future__ import annotations

import base64
import re
from datetime import timedelta

from fastapi.testclient import TestClient

from app import auth, claim, db, validation
from app.main import app
from tests.conftest import complete_guest_claim

OWNER = "stay-fee-doc-type"
TOKEN = "stay-fee-doc-type-token"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _cleanup():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (apartment["owner_user_id"],))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (apartment["owner_user_id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
    db.execute("DELETE FROM user_account WHERE id = ?", (apartment["owner_user_id"],))


def _host_stay():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        OWNER, "Host-Fixture-7-login!", role="host", must_change_password=False
    )
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Example Host s.r.o.",
            "seat": "Example Street 1, Prague",
            "ico": "00000000",
            "contact_email": "host@example.test",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Example Studio",
            "permalink_token": TOKEN,
            "permalink_pin": "246810",
            "permalink_window_days": 14,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    today = claim.prague_today()
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "stay-fee-doc-type-stay",
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


def _host_guest(stay_id: int, **overrides) -> int:
    now = db.utcnow()
    values = {
        "reservation_id": stay_id,
        "surname": "Smith",
        "first_name": "John",
        "birth_date": "1990-01-01",
        "nationality": "CZE",
        "doc_number": "P1234567",
        "res_street": "Example Street 1",
        "res_city": "Prague",
        "res_country": "CZE",
        "purpose": "10",
        "signature_png": SIGNATURE,
        "entered_by": "host",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return db.insert("guest", values)


def _save_guest(client: TestClient, guest_id: int, doc_type: str):
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    return client.post(
        f"/guests/{guest_id}",
        data={
            "surname": guest["surname"],
            "first_name": guest["first_name"],
            "birth_date": "01.01.1990",
            "nationality": guest["nationality"],
            "doc_number": guest["doc_number"],
            "res_street": guest["res_street"],
            "res_city": guest["res_city"],
            "res_country": guest["res_country"],
            "stay_from": claim.prague_today().isoformat(),
            "stay_to": (claim.prague_today() + timedelta(days=2)).isoformat(),
            "purpose": guest["purpose"],
            "doc_type": doc_type,
            "signature": SIGNATURE,
        },
        follow_redirects=False,
    )


def test_host_document_type_select_has_nine_options_and_defaults_for_czech_guest():
    owner_id, stay_id = _host_stay()
    try:
        guest_id = _host_guest(stay_id)
        response = _host_client(owner_id).get(f"/guests/{guest_id}")
        assert response.status_code == 200

        select = re.search(
            r'<select id="doc_type" name="doc_type">(.*?)</select>',
            response.text,
            re.DOTALL,
        )
        assert select
        options = re.findall(r'<option value="([^"]+)"([^>]*)>', select.group(1))
        assert len(options) == 9
        assert {value for value, _attrs in options} == set(validation.DOC_TYPES)
        assert [value for value, attrs in options if "selected" in attrs] == ["op"]
    finally:
        _cleanup()


def test_host_can_save_valid_document_type_and_invalid_values_become_null():
    owner_id, stay_id = _host_stay()
    try:
        guest_id = _host_guest(stay_id)
        client = _host_client(owner_id)

        response = _save_guest(client, guest_id, "trvaly_pobyt")
        assert response.status_code == 303, response.text
        saved = db.query_one("SELECT doc_type FROM guest WHERE id = ?", (guest_id,))
        assert saved["doc_type"] == "trvaly_pobyt"

        response = _save_guest(client, guest_id, "bogus")
        assert response.status_code == 303, response.text
        saved = db.query_one("SELECT doc_type FROM guest WHERE id = ?", (guest_id,))
        assert saved["doc_type"] is None
    finally:
        _cleanup()


def test_guest_own_form_has_no_document_type_field():
    _owner_id, stay_id = _host_stay()
    try:
        client = TestClient(app)
        complete_guest_claim(client, TOKEN, stay_id)
        response = client.get(f"/l/{TOKEN}/{stay_id}/new")
        assert response.status_code == 200
        assert 'name="doc_type"' not in response.text
    finally:
        _cleanup()
