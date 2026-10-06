"""Task 0006: hardening found in the review of the e-mail login release."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, login_link, mail, passkeys
from app.main import app
from tests.conftest import csrf_token_for, login_as

BASE = "https://ubyhost.test"
EMAIL = "hardening-host@example.test"


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", BASE)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    _clean()
    yield
    _clean()


def _clean():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'hardening-%'"):
        for table in ("passkey", "webauthn_challenge", "login_token", "legal_acceptance"):
            db.execute(f"DELETE FROM {table} WHERE user_account_id = ?", (row["id"],))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM rate_limit_event WHERE scope LIKE 'login_link%'")


def _account(email=EMAIL):
    user_id = auth.create_account(email, "Hardening Host", username="hardening-host")
    return db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))


def _client(account) -> TestClient:
    client = TestClient(app, base_url="https://testserver")
    login_as(client, account["username"], url="/login?lang=en")
    return client


# --- finding 1: an address change retires pending links ---------------------


def test_changing_the_address_retires_a_pending_address_change_link():
    account = _account()
    token = login_link.issue(account, purpose=login_link.EMAIL_CHANGE, email="thief@example.test")
    assert login_link.peek(token, (login_link.EMAIL_CHANGE,))
    auth.set_account_email(account["id"], "owner-new@example.test")
    assert login_link.peek(token, (login_link.EMAIL_CHANGE,)) is None


def test_a_change_link_for_the_address_already_in_use_does_nothing():
    account = _account()
    token = login_link.issue(account, purpose=login_link.EMAIL_CHANGE, email=EMAIL)
    row = login_link.peek(token, (login_link.EMAIL_CHANGE,))
    assert row and login_link.account_for(row) is None


# --- finding 2: a stolen older cookie cannot add a way in -------------------


def test_a_fresh_login_may_change_the_address_and_an_old_one_may_not(monkeypatch):
    account = _account()
    client = _client(account)
    data = {"email": "next@example.test", "csrf_token": csrf_token_for(client)}
    ok = client.post("/account/email", data=data, follow_redirects=False)
    assert "err=" not in ok.headers["location"]
    assert db.query_one(
        "SELECT 1 FROM login_token WHERE user_account_id = ? AND purpose = 'email_change'",
        (account["id"],),
    )
    db.execute("DELETE FROM login_token WHERE user_account_id = ?", (account["id"],))
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)
    refused = client.post("/account/email", data=data, follow_redirects=False)
    assert "err=" in refused.headers["location"]
    assert not db.query_one(
        "SELECT 1 FROM login_token WHERE user_account_id = ? AND purpose = 'email_change'",
        (account["id"],),
    )


def test_an_old_session_cannot_start_adding_a_passkey(monkeypatch):
    account = _account()
    client = _client(account)
    monkeypatch.setattr(passkeys, "available", lambda: True)
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)
    response = client.post(
        "/account/passkeys/options",
        json={},
        headers={"X-CSRF-Token": csrf_token_for(client), "Accept": "application/json"},
    )
    assert response.status_code == 403
    assert passkeys.count_for(account["id"]) == 0


def test_an_old_session_cannot_remove_a_passkey(monkeypatch):
    account = _account()
    client = _client(account)
    passkey_id = db.insert(
        "passkey",
        {
            "user_account_id": account["id"],
            "credential_id": "cred-1",
            "public_key": "AA",
            "sign_count": 0,
            "name": "Phone",
            "created_at": db.utcnow(),
        },
    )
    monkeypatch.setattr(auth, "FRESH_LOGIN_SECONDS", -1)
    client.post(
        f"/account/passkeys/{passkey_id}/delete",
        data={"csrf_token": csrf_token_for(client)},
        follow_redirects=False,
    )
    assert passkeys.count_for(account["id"]) == 1


# --- finding 4: the unique check does not depend on SQLite's wording --------


def test_unique_violation_is_recognised_on_both_engines():
    assert db.is_unique_violation(sqlite3.IntegrityError("UNIQUE constraint failed: user_account.email"))
    assert not db.is_unique_violation(sqlite3.IntegrityError("NOT NULL constraint failed: x.y"))

    class PgUnique(Exception):
        sqlstate = "23505"

    class PgOther(Exception):
        sqlstate = "23502"

    assert db.is_unique_violation(PgUnique("duplicate key value"))
    assert not db.is_unique_violation(PgOther("null value"))
    assert not db.is_unique_violation(ValueError("UNIQUE constraint failed"))


# --- finding 6: padded credential ids still find the passkey ----------------


def test_credential_ids_are_normalised_before_the_clone_lookup():
    assert passkeys.normalise_credential_id("YWJj") == "YWJj"
    assert passkeys.normalise_credential_id("YWJjZA==") == passkeys.normalise_credential_id("YWJjZA")
    assert passkeys.normalise_credential_id(None) == ""
