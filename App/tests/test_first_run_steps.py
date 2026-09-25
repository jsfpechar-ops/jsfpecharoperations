"""The forced first run, and the way out of it.

In production a new host is walked through three screens in a row -- choose a
password, connect an authenticator app, write down the recovery codes -- with no
way to skip any of them. Numbering the screens says how long that takes. The
screens are also the moment a host most often notices they signed in as the
wrong account, so each one carries a way to log out again.
"""
from __future__ import annotations

import html
import re

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
TEMP_PASSWORD = "Temporary-Password-123"
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


def _sign_in(*, must_change_password: bool, lang: str = "en") -> TestClient:
    """A signed-in host whose language cookie is already set.

    The cookie matters here: the recovery-codes screen is reached by a POST, and
    a POST never renders, so the only way it comes back in Czech is if the host
    asked for Czech at the login screen.
    """
    _cleanup()
    password = TEMP_PASSWORD if must_change_password else PASSWORD
    auth.create_account(
        USERNAME, password, "First Run", must_change_password=must_change_password
    )
    client = TestClient(app)
    response = client.post(
        "/login?lang={}".format(lang),
        data={"username": USERNAME, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def host():
    client = _sign_in(must_change_password=False)
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def first_run_host():
    client = _sign_in(must_change_password=True)
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def czech_first_run_host():
    client = _sign_in(must_change_password=True, lang="cs")
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


# --- "Step N of 3" -------------------------------------------------------


def test_production_numbers_the_three_first_run_screens(first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    password = _body(first_run_host.get("/account/password"))
    setup = _body(first_run_host.get("/account/2fa/setup"))
    recovery = _body(_recovery_page(first_run_host))

    assert "Step 1 of 3" in password
    assert "Step 2 of 3" in setup
    assert "Step 3 of 3" in recovery


def test_the_numbers_are_translated(czech_first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    password = _body(czech_first_run_host.get("/account/password"))
    setup = _body(czech_first_run_host.get("/account/2fa/setup"))
    recovery = _body(_recovery_page(czech_first_run_host))

    assert "Krok 1 ze 3" in password
    assert "Krok 2 ze 3" in setup
    assert "Krok 3 ze 3" in recovery
    assert "Step" not in password + setup + recovery


def test_the_step_number_leaves_the_lede_intact(first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    text = _body(first_run_host.get("/account/password"))
    lede = host_i18n.translate("en", "account.password.choose_lede")
    assert lede in text
    assert "Step 1 of 3 · " + lede in text


def test_staging_does_not_number_the_screens(first_run_host):
    """2FA is optional outside production, so there is no three-step run."""
    password = _body(first_run_host.get("/account/password"))
    setup = _body(first_run_host.get("/account/2fa/setup"))

    assert "Step 1 of 3" not in password
    assert "Step 2 of 3" not in setup
    assert host_i18n.translate("en", "account.password.choose_lede") in password


def test_a_host_with_2fa_already_on_sees_no_step_number(host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    _recovery_page(host)

    assert "Step 1 of 3" not in _body(host.get("/account/password"))
    assert "Step 2 of 3" not in _body(host.get("/account/2fa/setup"))


def test_a_failed_setup_code_keeps_the_step_number(first_run_host, monkeypatch):
    """A wrong code re-renders step 2; the host has not moved on."""
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    _secret(first_run_host)

    page = first_run_host.post(
        "/account/2fa/setup", data={"code": "000000"}, follow_redirects=False
    )
    assert page.status_code == 400, page.text
    assert "Step 2 of 3" in _body(page)


# --- the order the screens arrive in -------------------------------------


def test_production_walks_a_new_host_from_step_1_to_step_2(first_run_host, monkeypatch):
    """Step 1 has to be reachable, or the numbering starts at 2.

    The 2FA gate used to allow only ``/account/2fa/setup`` and ``/logout``. The
    guard above it sends a host with a temporary password to the password screen,
    so the 2FA gate then bounced them straight back off it and "Step 1 of 3"
    could never render.
    """
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    page = first_run_host.get("/account/password", follow_redirects=False)
    assert page.status_code == 200, page.text
    assert "Step 1 of 3" in _body(page)

    # Anything else still waits for the temporary password to be replaced.
    other = first_run_host.get("/", follow_redirects=False)
    assert other.status_code == 303
    assert other.headers["location"] == "/account/password"

    # With the password replaced, the 2FA screen is the second step.
    db.execute(
        "UPDATE user_account SET must_change_password = 0 WHERE username = ?",
        (USERNAME,),
    )
    moved = first_run_host.get("/", follow_redirects=False)
    assert moved.status_code == 303
    assert moved.headers["location"] == "/account/2fa/setup"
    assert "Step 2 of 3" in _body(first_run_host.get("/account/2fa/setup"))


# --- "Not you? Log out" --------------------------------------------------


def test_the_first_run_screens_offer_a_way_out(first_run_host, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    for page in (
        first_run_host.get("/account/password"),
        first_run_host.get("/account/2fa/setup"),
    ):
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
