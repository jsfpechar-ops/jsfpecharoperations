"""The operator form stays short and must not wipe invoicing details."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "operator-form-host"

DETAILS = {
    "bank_account": "123/0600",
    "bic": "AIRACZPP",
    "registry_entry": "Zapsáno v živnostenském registru",
    "vat_status": "payer",
    "invoice_prefix": "2026",
    "invoice_next_number": "12",
    "invoice_due_days": "7",
}

CORE = {
    "name": "Josef Novák",
    "seat": "Praha 2",
    "ico": "04656679",
    "contact_email": "josef@example.test",
    "contact_phone": "+420777100200",
    "dic": "CZ12345678",
}


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "Operator Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_the_operator_form_carries_only_the_identity_block(host):
    page = host.get("/entities?lang=en")
    assert page.status_code == 200
    for absent in ("new_bank_account", "new_bic", "new_vat_status",
                   "new_registry_entry", "new_invoice_prefix",
                   "new_invoice_next_number", "new_invoice_due_days"):
        assert f'id="{absent}"' not in page.text, f"{absent} should not be on the short form"


def test_a_core_only_update_keeps_the_stored_details(host):
    entity_id = db.insert(
        "legal_entity",
        {"name": "Detail s.r.o.", "seat": "Praha", "ico": "04656679",
         "contact_email": "d@example.test", **DETAILS,
         "owner_user_id": db.query_one("SELECT id FROM user_account WHERE username = ?",
                                       (USERNAME,))["id"],
         "created_at": db.utcnow()},
    )
    host.post(f"/entities/{entity_id}?lang=en", data={"name": "Detail s.r.o. II"})
    row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["name"] == "Detail s.r.o. II"
    for key, expected in DETAILS.items():
        stored = row[key]
        assert stored is not None, f"{key} was wiped by a core-only update"


def test_the_identity_block_updates_and_details_survive_together(host):
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity_id = db.insert(
        "legal_entity",
        {"name": "Shared s.r.o.", "seat": "Praha", "ico": "04656679",
         "contact_email": "s@example.test", **DETAILS,
         "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    host.post(f"/entities/{entity_id}?lang=en",
              data={**CORE, "name": "Shared s.r.o. (renamed)"})
    row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["name"] == "Shared s.r.o. (renamed)"
    assert row["dic"] == CORE["dic"]
    assert row["bank_account"] == DETAILS["bank_account"]
    assert row["vat_status"] == DETAILS["vat_status"]
    assert row["invoice_due_days"] == 7


def test_by_an_ico_checksum_gates_the_short_form_save(host):
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity_id = db.insert(
        "legal_entity",
        {"name": "Ico Guard s.r.o.", "seat": "Praha", "ico": "04656679",
         "contact_email": "i@example.test",
         "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    response = host.post(f"/entities/{entity_id}?lang=en",
                         data={**CORE, "name": "Ico Guard s.r.o.", "ico": "12345678"},
                         follow_redirects=True)
    assert response.status_code == 200
    assert "That company ID (IČO) is not valid." in response.text
    assert db.query_one("SELECT ico FROM legal_entity WHERE id = ?", (entity_id,))["ico"] == "04656679"
