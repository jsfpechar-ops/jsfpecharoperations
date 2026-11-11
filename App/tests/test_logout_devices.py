"""0947: "log out" ends this browser only; "log out of all devices" ends every session.

Exports of personal data still need a login made within the last 10 minutes.
Saving a bank account does not open Security.
"""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

def _recent_login_redirect(response) -> bool:
    location = response.headers["location"]
    return location.startswith("/settings/security?err=") and location.endswith("#settings-security")


def _signed_in(username: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


def _new_host() -> str:
    db.init_db()
    username = f"devices-{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Devices Host", role="host", username=username)
    return username


def _signed_out(response) -> bool:
    return response.status_code in (302, 303)


def test_logout_on_one_device_keeps_the_other_signed_in():
    username = _new_host()
    laptop, phone = _signed_in(username), _signed_in(username)
    copied = dict(phone.cookies)

    assert laptop.post("/logout", follow_redirects=False).status_code == 303

    assert phone.get("/reservations", follow_redirects=False).status_code == 200
    replay = TestClient(app, cookies=copied)
    assert replay.get("/reservations", follow_redirects=False).status_code == 200


def test_logout_all_ends_every_session_and_clears_the_device_cookie():
    username = _new_host()
    laptop, phone = _signed_in(username), _signed_in(username)
    copied = dict(phone.cookies)
    assert phone.get("/reservations", follow_redirects=False).status_code == 200

    response = laptop.post("/account/logout-all", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
    assert "ubyhost_device" not in laptop.cookies
    assert _signed_out(phone.get("/reservations", follow_redirects=False))
    replay = TestClient(app, cookies=copied)
    assert _signed_out(replay.get("/reservations", follow_redirects=False))


def test_logout_all_without_login_redirects_to_login():
    response = TestClient(app).post("/account/logout-all", follow_redirects=False)

    assert _signed_out(response)
    assert "/login" in response.headers["location"]


def test_workspace_export_needs_a_recent_login(monkeypatch):
    username = _new_host()
    client = _signed_in(username)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)

    response = client.post("/settings/workspace-export", follow_redirects=False)

    assert response.status_code == 303
    assert _recent_login_redirect(response)


def test_guest_export_json_needs_a_recent_login_and_passes_when_fresh(monkeypatch):
    username = _new_host()
    client = _signed_in(username)

    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)
    stale = client.get("/guests/999999/export.json", follow_redirects=False)
    assert stale.status_code == 303
    assert _recent_login_redirect(stale)

    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", 600)
    fresh = client.get("/guests/999999/export.json", follow_redirects=False)
    assert fresh.status_code == 404


def test_invoice_bank_save_stays_off_security(monkeypatch):
    """The invoice form always posts the account. A stale login must save it, not open Security."""
    username = _new_host()
    entity_id = _entity_for(username)
    client = _signed_in(username)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)

    response = client.post(
        f"/entities/{entity_id}/invoice",
        data={
            "account_prefix": "19",
            "account_number": "2000781379",
            "account_bank": "0800",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert not _recent_login_redirect(response)
    row = db.query_one("SELECT bank_account, iban FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] == "19-2000781379/0800"
    assert (row["iban"] or "").startswith("CZ")


def _entity_for(username: str, **fields) -> int:
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"]
    values = {
        "name": "Devices s.r.o.",
        "owner_user_id": owner_id,
        "bank_account": "123/0600",
        "iban": "CZ9106000000000000000123",
        "created_at": db.utcnow(),
    }
    values.update(fields)
    return db.insert("legal_entity", values)


def test_identity_post_saves_bank_on_a_stale_session(monkeypatch):
    """POST /entities/{id} writes bank_account. A stale login must not open Security."""
    username = _new_host()
    entity_id = _entity_for(username)
    client = _signed_in(username)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)

    response = client.post(
        f"/entities/{entity_id}",
        data={"name": "Devices s.r.o.", "bank_account": "19-2000781379/0800"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert not _recent_login_redirect(response)
    row = db.query_one("SELECT bank_account, iban FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] == "19-2000781379/0800"
    assert (row["iban"] or "").startswith("CZ")


def test_identity_post_still_saves_the_name_when_the_session_is_stale(monkeypatch):
    username = _new_host()
    entity_id = _entity_for(username)
    client = _signed_in(username)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)

    response = client.post(
        f"/entities/{entity_id}",
        data={"name": "Renamed s.r.o."},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert not _recent_login_redirect(response)
    assert db.query_one("SELECT name FROM legal_entity WHERE id = ?", (entity_id,))["name"] == "Renamed s.r.o."


def test_identity_post_changes_bank_when_the_login_is_fresh():
    username = _new_host()
    entity_id = _entity_for(username)
    client = _signed_in(username)

    response = client.post(
        f"/entities/{entity_id}",
        data={"name": "Devices s.r.o.", "bank_account": "19-2000781379/0800"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert not _recent_login_redirect(response)
    row = db.query_one("SELECT bank_account FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] == "19-2000781379/0800"


def test_identity_post_ignores_a_bare_iban_field_without_opening_security(monkeypatch):
    """This form stores bank_account, not a lone iban field, and must not open Security."""
    username = _new_host()
    entity_id = _entity_for(username)
    client = _signed_in(username)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)

    response = client.post(
        f"/entities/{entity_id}",
        data={"name": "Devices s.r.o.", "iban": "CZ1753060000000012345678"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert not _recent_login_redirect(response)
    row = db.query_one("SELECT iban FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["iban"] == "CZ9106000000000000000123"


def test_identity_post_ignores_split_account_fields_without_opening_security(monkeypatch):
    """Prefix, number and bank belong on the invoice form. Here they must not open Security."""
    username = _new_host()
    entity_id = _entity_for(username)
    client = _signed_in(username)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)

    response = client.post(
        f"/entities/{entity_id}",
        data={
            "name": "Devices s.r.o.",
            "account_prefix": "19",
            "account_number": "2000781379",
            "account_bank": "0800",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert not _recent_login_redirect(response)
    row = db.query_one(
        "SELECT bank_account, iban FROM legal_entity WHERE id = ?", (entity_id,)
    )
    assert row["bank_account"] == "123/0600"
    assert row["iban"] == "CZ9106000000000000000123"
