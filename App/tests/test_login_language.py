"""A Czech login must not flip the workspace to English.

Signed-out pages fall back to Czech (``PUBLIC_DEFAULT_LANGUAGE``) and signed-in
pages to English (``DEFAULT_LANGUAGE``), and nothing wrote the language cookie
at login. So a host who never touched the switch read Czech on /login and then
landed in English on every screen after it.
"""
from __future__ import annotations

import re

import pyotp
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "loginlanghost"


def _cleanup():
    """Logging in writes audit rows owned by the account, so they go first."""
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


def _account(*, two_factor: bool = False) -> str:
    """A host ready to log in; returns the TOTP secret when asked for one."""
    db.init_db()
    _cleanup()
    user_id = auth.create_account(f"{USERNAME}@example.test", "Login Lang", username=USERNAME)
    if not two_factor:
        return ""
    secret = auth.new_totp_secret()
    auth.enable_totp(user_id, secret, auth.new_recovery_codes())
    return secret


def _sign_in(client: TestClient, query: str = "") -> "object":
    return login_as(client, USERNAME, url=f"/login{query}", follow_redirects=False)


def test_a_cookieless_login_keeps_the_czech_the_login_page_showed():
    _account()
    try:
        client = TestClient(app)
        page = client.get("/login")
        assert 'lang="cs"' in page.text, "signed-out login page is not Czech by default"

        response = _sign_in(client)

        assert response.status_code == 303
        assert client.cookies.get(host_i18n.LANG_COOKIE) == "cs", (
            "logging in dropped the Czech the host just read"
        )
        after = client.get("/")
        assert after.status_code == 200
        assert 'lang="cs"' in after.text, "the workspace came back in English"
    finally:
        _cleanup()


def test_a_language_the_host_asked_for_is_what_gets_remembered():
    _account()
    try:
        client = TestClient(app)
        response = _sign_in(client, "?lang=en")

        assert response.status_code == 303
        assert client.cookies.get(host_i18n.LANG_COOKIE) == "en"
        assert 'lang="en"' in client.get("/").text
    finally:
        _cleanup()


def test_a_saved_choice_is_not_overwritten_by_the_signed_out_default():
    _account()
    try:
        client = TestClient(app)
        client.cookies.set(host_i18n.LANG_COOKIE, "en")

        assert _sign_in(client).status_code == 303

        assert client.cookies.get(host_i18n.LANG_COOKIE) == "en", (
            "the host's saved choice lost to the signed-out default"
        )
        assert 'lang="en"' in client.get("/").text
    finally:
        _cleanup()


def test_the_two_factor_step_keeps_the_login_language():
    secret = _account(two_factor=True)
    try:
        client = TestClient(app)
        challenge = _sign_in(client)
        assert challenge.status_code == 200
        pending = re.search(r'name="pending" value="([^"]+)"', challenge.text)
        assert pending, "no pending token on the 2FA page"

        response = client.post(
            "/login/2fa",
            data={"pending": pending.group(1), "code": pyotp.TOTP(secret).now()},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert client.cookies.get(host_i18n.LANG_COOKIE) == "cs", (
            "the 2FA step dropped the Czech the host just read"
        )
        assert 'lang="cs"' in client.get("/").text
    finally:
        _cleanup()


def test_the_login_page_itself_still_answers_in_the_asked_for_language():
    """Guard on the assumption the fix rests on: signed-out pages default to Czech."""
    page = TestClient(app).get("/login")
    assert 'lang="cs"' in page.text
    assert 'lang="en"' in TestClient(app).get("/login?lang=en").text
