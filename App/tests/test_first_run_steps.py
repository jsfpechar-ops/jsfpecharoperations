"""The way out of the authenticator setup screens.

Setting up an authenticator app (optional since task 0003: there is no forced
first run any more) is the moment a host most often notices they signed in as
the wrong account, so each screen carries a way to log out again.
"""
from __future__ import annotations

import html
import re

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "first-run-host"


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


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


def _sign_in(*, lang: str = "en") -> TestClient:
    """A signed-in host whose language cookie is already set.

    The cookie matters here: the recovery-codes screen is reached by a POST, and
    a POST never renders, so the only way it comes back in Czech is if the host
    asked for Czech at the login screen.
    """
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "First Run", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url=f"/login?lang={lang}", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def first_run_host():
    client = _sign_in()
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def czech_first_run_host():
    client = _sign_in(lang="cs")
    try:
        yield client
    finally:
        _cleanup()


def _body(response) -> str:
    return html.unescape(response.text)


def _secret(client) -> str:
    page = client.get("/account/2fa/setup")
    assert page.status_code == 200, page.text
    match = re.search(r'<code id="totp-setup-key">([^<]+)</code>', page.text)
    assert match, page.text
    return match.group(1).replace(" ", "")


def _recovery_page(client):
    code = pyotp.TOTP(_secret(client)).now()
    page = client.post("/account/2fa/setup", data={"code": code}, follow_redirects=False)
    assert page.status_code == 200, page.text
    return page


# --- the order the screens arrive in -------------------------------------


# --- "Not you? Log out" --------------------------------------------------


def test_the_first_run_screens_offer_a_way_out(first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    for page in (first_run_host.get("/account/2fa/setup"),):
        assert 'class="auth-not-you"' in page.text
        assert host_i18n.translate("en", "auth.not_you") in _body(page)
        form = re.search(r"<form[^>]*auth-not-you[^>]*>.*?</form>", page.text, re.S)
        assert form, page.text
        assert 'method="post"' in form.group(0)
        assert 'action="/logout"' in form.group(0)
        assert 'name="_csrf"' in form.group(0)


def test_the_recovery_screen_offers_it_too(first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    page = _recovery_page(first_run_host)
    assert 'class="auth-not-you"' in page.text
    assert host_i18n.translate("en", "auth.not_you") in _body(page)


def test_the_label_is_translated(czech_first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    assert host_i18n.translate("cs", "auth.not_you") == "Nejste to vy? Odhlásit se"
    text = _body(czech_first_run_host.get("/account/2fa/setup"))
    assert "Nejste to vy? Odhlásit se" in text
    assert "Not you?" not in text


def test_the_logout_button_actually_logs_out(first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    page = first_run_host.get("/account/2fa/setup")
    token = re.search(r'name="_csrf" value="([^"]+)"', page.text).group(1)

    response = first_run_host.post(
        "/logout", data={"_csrf": token}, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"].startswith("/login?notice=logged_out")


def test_the_signed_out_pages_do_not_offer_it():
    """There is nobody to log out on the login screen itself."""
    client = TestClient(app)
    text = client.get("/login").text
    assert 'class="auth-not-you"' not in text
    assert host_i18n.translate("en", "auth.not_you") not in _body(client.get("/login"))
