"""Setting up an authenticator app has to work on the phone holding the screen.

The page used to show only a QR code, so a host setting up on their phone had to
copy a 32-character string by hand with no grouping and no Copy button.
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "setup-page-host"


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


@pytest.fixture
def host():
    """A signed-in host who still has to connect an authenticator app."""
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Setup Page", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _body(response):
    return html.unescape(response.text)


def _secret(client) -> str:
    page = client.get("/account/2fa/setup")
    assert page.status_code == 200, page.text
    match = re.search(r'<code id="totp-setup-key">([^<]+)</code>', page.text)
    assert match, page.text
    return match.group(1).replace(" ", "")


def test_the_page_offers_to_open_the_app_on_this_phone(host):
    page = host.get("/account/2fa/setup")
    assert page.status_code == 200
    text = _body(page)
    secret = _secret(host)
    assert 'href="{}"'.format(auth.totp_uri(secret, USERNAME)) in text
    assert host_i18n.translate("en", "account.2fa.setup_open_app") in text
    assert 'class="btn auth-setup-open"' in text


def test_the_instructions_name_real_apps_and_drop_the_protocol_jargon(host):
    for lang in ("en", "cs"):
        text = _body(host.get("/account/2fa/setup?lang={}".format(lang)))
        assert host_i18n.translate(lang, "account.2fa.setup_scan") in text
        assert "TOTP" not in text
        assert "Google Authenticator" in text
        assert 'alt="{}"'.format(host_i18n.translate(lang, "account.2fa.qr_alt")) in text


def test_the_setup_key_is_grouped_in_fours_and_has_a_copy_button(host):
    secret = _secret(host)
    text = _body(host.get("/account/2fa/setup"))
    grouped = " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))
    assert grouped in text
    assert 'data-copy="totp-setup-key"' in text
    assert host_i18n.translate("en", "common.copy") in text


def test_the_form_posts_a_csrf_token_and_accepts_a_spaced_code(host):
    page = host.get("/account/2fa/setup")
    assert '<input type="hidden" name="_csrf" value="' in page.text
    assert 'maxlength="7"' in page.text
    assert "pattern=" not in page.text

    code = pyotp.TOTP(_secret(host)).now()
    response = host.post(
        "/account/2fa/setup",
        data={"code": "{} {}".format(code[:3], code[3:])},
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    assert host_i18n.translate("en", "account.2fa.recovery_title") in _body(response)


def test_a_re_post_keeps_the_codes_already_written_down(host):
    """A reload must not mint a second set and kill the first one.

    Only the hashes are stored, so a regenerated set is unrecoverable: the codes
    on the host's printout would stop working with nothing on screen to say so.
    """
    code = pyotp.TOTP(_secret(host)).now()
    first = host.post("/account/2fa/setup", data={"code": code}, follow_redirects=False)
    assert first.status_code == 200, first.text
    stored = db.query_one(
        "SELECT recovery_codes_hash FROM user_account WHERE username = ?", (USERNAME,)
    )["recovery_codes_hash"]
    assert stored

    again = host.post("/account/2fa/setup", data={"code": code}, follow_redirects=False)
    assert again.status_code == 303, again.text
    assert again.headers["location"] == "/settings?msg={}".format(
        quote(host_i18n.translate("en", "flash.accounts.twofa_enabled"))
    )
    assert (
        db.query_one(
            "SELECT recovery_codes_hash FROM user_account WHERE username = ?",
            (USERNAME,),
        )["recovery_codes_hash"]
        == stored
    )


def test_a_wrong_code_says_what_to_try_next(host):
    response = host.post(
        "/account/2fa/setup", data={"code": "000000"}, follow_redirects=False
    )
    assert response.status_code == 400
    assert host_i18n.translate("en", "auth.error.setup_code_invalid") in _body(response)
