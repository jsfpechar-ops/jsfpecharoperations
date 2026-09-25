"""What the admin has to pass on, and what the host will be asked for.

Resetting a password also wipes the second factor, which makes it the lost-phone
fix -- but the panel only said the old password stopped working, so the admin had
no way to know. Neither panel said where the host signs in, so the credentials
travelled without an address.
"""
from __future__ import annotations

import html

import pytest
from starlette.testclient import TestClient

from app import auth, config, db, host_i18n
from app.main import app

ADMIN = "handoff-admin"
HOST = "handoff-host"
PASSWORD = "Tr0ub4dour-Test-Pass"


def _purge():
    for name in (ADMIN, HOST):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not row:
            continue
        for table in ("apartment", "legal_entity", "alert", "audit"):
            db.execute(
                f"UPDATE {table} SET owner_user_id = NULL WHERE owner_user_id = ?",
                (row["id"],),
            )
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


@pytest.fixture()
def admin():
    db.init_db()
    _purge()
    auth.create_account(
        ADMIN, PASSWORD, "Hand-off admin", role="admin", must_change_password=False
    )
    with TestClient(app) as client:
        response = client.post(
            "/login?lang=en",
            data={"username": ADMIN, "password": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        yield client
    _purge()


@pytest.fixture()
def czech_admin():
    db.init_db()
    _purge()
    auth.create_account(
        ADMIN, PASSWORD, "Hand-off admin", role="admin", must_change_password=False
    )
    with TestClient(app) as client:
        response = client.post(
            "/login?lang=cs",
            data={"username": ADMIN, "password": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        yield client
    _purge()


def _text(key: str, lang: str = "en") -> str:
    return host_i18n.STRINGS[lang][key]


def _body(response) -> str:
    return html.unescape(response.text)


def _create(client, username: str = HOST):
    response = client.post(
        "/admin/users",
        data={"username": username, "display_name": "Hand-off host"},
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    return _body(response)


def _reset(client, username: str = HOST):
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    assert row, "the host to reset was never created"
    response = client.post(f"/admin/users/{row['id']}/password", data={}, follow_redirects=False)
    assert response.status_code == 200, response.text
    return _body(response)


# --- where the host signs in ----------------------------------------------


def test_a_new_host_comes_with_the_login_address(admin):
    body = _create(admin)

    assert "Send them the login address" in body
    assert f"{config.PUBLIC_BASE_URL}/login" in body


def test_the_address_is_filled_in_and_not_left_as_a_placeholder(admin):
    body = _create(admin)

    assert "%(url)s" not in body


def test_a_reset_carries_the_login_address_too(admin):
    _create(admin)
    body = _reset(admin)

    assert f"{config.PUBLIC_BASE_URL}/login" in body


# --- what the host will be asked for -------------------------------------


def test_a_new_host_is_told_an_authenticator_app_is_required(admin):
    body = _create(admin)

    assert "set up an authenticator app" in body


def test_a_reset_says_two_factor_went_with_the_password(admin):
    _create(admin)
    body = _reset(admin)

    assert _text("users.credential.reset_2fa") in body


def test_a_brand_new_host_is_not_told_two_factor_was_reset(admin):
    """Nothing was reset: the account never had a second factor to lose."""
    body = _create(admin)

    assert _text("users.credential.reset_2fa") not in body


# --- the admin reads it in their own language ----------------------------


def test_the_hand_off_is_translated(czech_admin):
    body = _create(czech_admin)

    assert _text("users.credential.next_steps", "cs").replace(
        "%(url)s", f"{config.PUBLIC_BASE_URL}/login"
    ) in body
    assert "Send them the login address" not in body


def test_a_czech_reset_says_two_factor_went_too(czech_admin):
    _create(czech_admin)
    body = _reset(czech_admin)

    assert _text("users.credential.reset_2fa", "cs") in body


# --- the copy itself ------------------------------------------------------


def test_the_hand_off_copy_is_the_audited_wording():
    assert _text("users.credential.reset_2fa") == (
        "Two-factor authentication was reset too. They'll set it up again right "
        "after choosing a new password."
    )
    assert _text("users.credential.reset_2fa", "cs") == (
        "Resetovalo se i dvoufázové ověření. Hned po zvolení nového hesla si ho "
        "nastaví znovu."
    )
    assert _text("users.credential.next_steps") == (
        "Send them the login address %(url)s with these details. At first login "
        "they'll choose a password and set up an authenticator app."
    )
    assert _text("users.credential.next_steps", "cs") == (
        "Pošlete jim adresu pro přihlášení %(url)s spolu s těmito údaji. Při prvním "
        "přihlášení si zvolí heslo a nastaví autentizační aplikaci."
    )


def test_both_new_keys_keep_their_url_placeholder():
    for lang in ("en", "cs"):
        assert "%(url)s" in _text("users.credential.next_steps", lang)
