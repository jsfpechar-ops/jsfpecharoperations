"""UX-129 (audit B-25): re-issuing a session keeps "Remember me".

The first-run sequence mints a new session cookie twice — once when the host
chooses a password, once when 2FA is switched on. Both used to drop the flag,
so a host who ticked "Remember me for 30 days" silently fell back to the
12-hour session.
"""
from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
NEW_PASSWORD = "Another-Secure-Password-456"
USERNAME = "ux129-host"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _session_header(response) -> str:
    headers = response.headers.get_list("set-cookie")
    return next(h for h in headers if h.startswith(f"{auth.SESSION_COOKIE}="))


def _new_session(response) -> dict:
    cookie = response.cookies.get(auth.SESSION_COOKIE)
    assert cookie, "the route did not re-issue a session cookie"
    payload = auth._session_payload(cookie)
    assert payload is not None
    return payload


@pytest.fixture
def client():
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Ux 129", must_change_password=False)
    try:
        yield TestClient(app)
    finally:
        _cleanup()


def _login(client, *, remember: bool):
    response = client.post(
        "/login",
        data={
            "username": USERNAME,
            "password": PASSWORD,
            **({"remember": "1"} if remember else {}),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_remember_me_survives_a_password_change(client):
    _login(client, remember=True)
    response = client.post(
        "/account/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert _new_session(response).get("rm") == 1
    assert f"Max-Age={auth.SESSION_REMEMBER_MAX_AGE}" in _session_header(response)


def test_a_plain_session_stays_plain_after_a_password_change(client):
    _login(client, remember=False)
    response = client.post(
        "/account/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert _new_session(response).get("rm") is None
    assert f"Max-Age={auth.SESSION_MAX_AGE}" in _session_header(response)


def test_remember_me_survives_switching_two_factor_on(client):
    _login(client, remember=True)
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    secret = auth.new_totp_secret()
    auth.stage_totp(account["id"], secret)
    response = client.post(
        "/account/2fa/setup",
        data={"code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert _new_session(response).get("rm") == 1
    assert f"Max-Age={auth.SESSION_REMEMBER_MAX_AGE}" in _session_header(response)


def test_a_plain_session_stays_plain_after_switching_two_factor_on(client):
    _login(client, remember=False)
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    secret = auth.new_totp_secret()
    auth.stage_totp(account["id"], secret)
    response = client.post(
        "/account/2fa/setup",
        data={"code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert _new_session(response).get("rm") is None
    assert f"Max-Age={auth.SESSION_MAX_AGE}" in _session_header(response)


def test_session_remembers_is_false_without_a_session():
    from types import SimpleNamespace

    request = SimpleNamespace(state=SimpleNamespace(), cookies={})
    assert auth.session_remembers(request) is False
