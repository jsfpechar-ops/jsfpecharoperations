"""Losing the phone must not mean losing the account.

Two-factor setup could only be run once. A host whose phone died, or who
replaced it, had no self-service way back in. This is that path, done by the
host: the old phone proves itself with a code (or a recovery code) first.
Since task 0003 there is no password to prove as well.
"""
from __future__ import annotations

import html
import re
from urllib.parse import unquote

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "move-phone-host"
MOVE_ACTION = "/account/2fa/move"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        for table in ("alert", "audit", "apartment", "legal_entity"):
            db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _client() -> TestClient:
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Move Phone", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


@pytest.fixture()
def host():
    """A signed-in host with no second factor yet."""
    client = _client()
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture()
def enrolled():
    """A signed-in host with an authenticator app already connected."""
    client = _client()
    try:
        yield client
    finally:
        _cleanup()


def _body(response) -> str:
    return html.unescape(response.text)


def _text(key: str, lang: str = "en") -> str:
    return host_i18n.STRINGS[lang][key]


def _setup_secret(client) -> str:
    page = client.get("/account/2fa/setup")
    assert page.status_code == 200, page.text
    match = re.search(r'<code id="totp-setup-key">([^<]+)</code>', page.text)
    assert match, page.text
    return match.group(1).replace(" ", "")


def _connect(client) -> tuple[str, list[str]]:
    """Run setup for real, so the session cookie is re-issued the app's way."""
    secret = _setup_secret(client)
    code = pyotp.TOTP(secret).now()
    page = client.post("/account/2fa/setup", data={"code": code}, follow_redirects=False)
    assert page.status_code == 200, page.text
    codes = re.findall(r"<code>([0-9A-F]{4}-[0-9A-F]{4})</code>", page.text)
    assert len(codes) == 8, page.text
    return secret, codes


def _account() -> dict:
    row = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    assert row, "the host went missing"
    return dict(row)


@pytest.fixture()
def phone(enrolled):
    """An enrolled host, plus the secret and recovery codes of that enrolment."""
    secret, codes = _connect(enrolled)
    assert _account()["totp_enabled"] == 1
    return enrolled, secret, codes


def _move(client, *, code=""):
    return client.post(MOVE_ACTION, data={"code": code}, follow_redirects=False)


# --- the way in ----------------------------------------------------------


def test_settings_offers_the_move_once_a_second_factor_is_on(phone):
    client, _secret, _codes = phone

    page = client.get("/settings")
    assert page.status_code == 200, page.text
    body = _body(page)

    assert f'action="{MOVE_ACTION}"' in body
    assert _text("settings.account.2fa_move") in body
    assert _text("settings.account.2fa_move_help") in body
    assert _text("settings.account.2fa_move_action") in body


def test_the_move_form_is_labelled_and_its_hint_is_linked(phone):
    client, _secret, _codes = phone
    body = _body(client.get("/settings"))

    assert f'<label for="move-code">{_text("settings.account.2fa_move_code")}</label>' in body
    assert 'aria-describedby="move-code-hint"' in body
    assert f'id="move-code-hint">{_text("settings.account.2fa_move_code_hint")}' in body


def test_settings_does_not_offer_a_move_without_a_second_factor(host):
    body = _body(host.get("/settings"))

    assert f'action="{MOVE_ACTION}"' not in body
    assert _text("settings.account.2fa_move") not in body


def test_the_move_cannot_be_triggered_by_a_link(phone):
    client, _secret, _codes = phone

    assert client.get(MOVE_ACTION, follow_redirects=False).status_code == 405


# --- the old phone has to prove itself -------------------------------------


def test_a_wrong_code_stops_the_move(phone):
    client, secret, _codes = phone

    response = _move(client, code="000000")

    assert response.status_code == 303
    assert _text("auth.error.code_invalid") in unquote(response.headers["location"])
    assert _account()["totp_enabled"] == 1, "the second factor was wiped anyway"
    assert auth.verify_second_factor(_account(), pyotp.TOTP(secret).now())


# --- what a successful move does -----------------------------------------


def test_the_right_pair_starts_setup_again(phone):
    client, secret, _codes = phone

    response = _move(client, code=pyotp.TOTP(secret).now())

    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/account/2fa/setup?moved=1"
    row = _account()
    assert row["totp_enabled"] == 0, "the old app would still be a way in"
    assert not row["recovery_codes_hash"], "the old codes would still be a way in"


def test_the_old_recovery_codes_stop_working(phone):
    client, secret, codes = phone

    _move(client, code=pyotp.TOTP(secret).now())

    assert not auth.verify_second_factor(_account(), codes[0])


def test_a_recovery_code_can_start_the_move(phone):
    """The phone is dead: the code on the printout is the only second factor left."""
    client, _secret, codes = phone

    response = _move(client, code=codes[0])

    assert response.status_code == 303
    assert response.headers["location"] == "/account/2fa/setup?moved=1"


def test_the_host_is_still_signed_in_afterwards(phone):
    """reset_totp bumps session_version, so the POST must re-issue the cookie."""
    client, secret, _codes = phone

    _move(client, code=pyotp.TOTP(secret).now())

    page = client.get("/settings", follow_redirects=False)
    assert page.status_code == 200, "the move logged the host out"


def test_setup_issues_a_fresh_secret_and_fresh_codes(phone):
    client, secret, old_codes = phone

    _move(client, code=pyotp.TOTP(secret).now())
    new_secret, new_codes = _connect(client)

    assert new_secret != secret
    assert not set(new_codes) & set(old_codes)
    assert _account()["totp_enabled"] == 1


def test_the_first_login_on_a_new_phone_is_not_refused_as_a_replay(monkeypatch):
    """A step spent before the move must not lock the new device out.

    ``totp_last_step`` is a replay watermark. It used to survive both the move
    (``reset_totp``) and re-enrolment (``enable_totp``), so a first login in the
    same 30-second step as the code that started the move was refused by the CAS.
    """
    db.init_db()
    _cleanup()
    fixed = 1_700_000_000.0
    monkeypatch.setattr(auth.time, "time", lambda: fixed)
    try:
        user_id = auth.create_account(f"{USERNAME}@example.test", "Move Phone", username=USERNAME)
        old_secret = auth.new_totp_secret()
        auth.enable_totp(user_id, old_secret, auth.new_recovery_codes())
        assert _account()["totp_last_step"] is None, (
            "enabling a factor starts with no spent step"
        )

        # Proving the old device for the move spends the current step.
        assert auth.verify_second_factor(_account(), pyotp.TOTP(old_secret).at(fixed)) is True
        assert _account()["totp_last_step"] == int(fixed // 30)

        auth.reset_totp(user_id)
        assert _account()["totp_last_step"] is None, (
            "the replay watermark must not survive the move"
        )

        new_secret = auth.new_totp_secret()
        auth.enable_totp(user_id, new_secret, auth.new_recovery_codes())
        assert _account()["totp_last_step"] is None

        # The new phone's first code can land in the same step that was spent.
        assert auth.verify_second_factor(
            _account(), pyotp.TOTP(new_secret).at(fixed)
        ) is True
    finally:
        _cleanup()


def test_a_move_without_a_second_factor_goes_to_setup(host):
    response = _move(host, code="123456")

    assert response.status_code == 303
    assert response.headers["location"] == "/account/2fa/setup"


# --- what the setup page says on the way back ----------------------------


def test_setup_says_why_it_is_asking_again(phone):
    client, secret, _codes = phone

    _move(client, code=pyotp.TOTP(secret).now())
    body = _body(client.get("/account/2fa/setup?moved=1"))

    assert _text("account.2fa.moved_notice") in body


def test_a_first_time_setup_is_not_told_about_an_old_phone(host):
    body = _body(host.get("/account/2fa/setup"))

    assert _text("account.2fa.moved_notice") not in body


# --- the host's own language ---------------------------------------------


def test_the_move_form_is_translated(phone):
    client, _secret, _codes = phone
    body = _body(client.get("/settings?lang=cs"))

    assert _text("settings.account.2fa_move", "cs") in body
    assert _text("settings.account.2fa_move_help", "cs") in body
    assert _text("settings.account.2fa_move_action", "cs") in body
    assert _text("settings.account.2fa_move", "en") not in body


def test_the_errors_come_back_in_the_hosts_language(phone):
    client, _secret, _codes = phone

    response = client.post(
        MOVE_ACTION + "?lang=cs",
        data={"code": "000000"},
        follow_redirects=False,
    )

    assert _text("auth.error.code_invalid", "cs") in unquote(
        response.headers["location"]
    )


def test_the_moved_notice_is_translated(phone):
    client, secret, _codes = phone

    _move(client, code=pyotp.TOTP(secret).now())
    body = _body(client.get("/account/2fa/setup?lang=cs&moved=1"))

    assert _text("account.2fa.moved_notice", "cs") in body
    assert _text("account.2fa.moved_notice", "en") not in body


def test_every_new_key_exists_in_both_languages():
    for key in (
        "settings.account.2fa_move",
        "settings.account.2fa_move_help",
        "settings.account.2fa_move_code",
        "settings.account.2fa_move_code_hint",
        "settings.account.2fa_move_action",
        "account.2fa.moved_notice",
    ):
        for lang in ("en", "cs"):
            assert host_i18n.STRINGS[lang][key].strip(), f"{key} is empty in {lang}"


# --- the per-account second-factor budget --------------------------------


def test_ten_failed_codes_lock_the_move_even_with_the_right_code(phone):
    client, secret, _codes = phone
    account_id = _account()["id"]
    try:
        for _ in range(10):
            _move(client, code="000000")

        response = _move(client, code=pyotp.TOTP(secret).now())

        assert response.status_code == 303
        assert _text("auth.error.code_locked") in unquote(response.headers["location"])
        assert _account()["totp_enabled"] == 1, "the second factor was wiped anyway"
        assert db.decrypt_secret(_account()["totp_secret_enc"]) == secret
    finally:
        db.execute(
            "DELETE FROM rate_limit_event WHERE scope = '2fa_fail_account' AND key = ?",
            (str(account_id),),
        )
