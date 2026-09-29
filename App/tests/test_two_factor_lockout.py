"""The 2FA step has to say what went wrong and how to get back in.

Two halves of finding B-14, both about a host stuck on this screen:

* A wrong code is usually a clock-drift problem - the code on the phone rotated
  while it was being typed - so the message has to say so.
* The lockout says "wait 15 minutes", but the ``pending`` token that carries the
  half-finished login dies after 10 (``auth.TWO_FACTOR_PENDING_MAX_AGE``). A host
  who does as they were told comes back to a bare login form with no
  explanation, and the lockout message itself stays on the dead page. So the
  lockout carries a link back to the start, and a dead token says why it died.
"""
from __future__ import annotations

import html
import re

import pyotp
from fastapi.testclient import TestClient

from app import auth, db, host_i18n, rate_limit
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "lockouthost"


def _cleanup() -> None:
    """Login attempts write audit rows owned by the account, so those go first."""
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


def _key() -> str:
    return f"testclient:{USERNAME}:2fa"


def _page(response) -> str:
    """The body with HTML entities resolved, so copy pins match the catalogue.

    Jinja escapes the apostrophe in the audited wrong-code copy as ``&#39;``.
    """
    return html.unescape(response.text)


def _forget_rate_limit() -> None:
    """Drop the two rate-limit rows a failed 2FA attempt writes.

    The account key is ours; the per-IP key is the shared ``testclient`` one, and
    leaving failures on it would lock out unrelated tests later in the run.
    """
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope = ? AND key = ?", ("login_fail", _key())
    )
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope = ? AND key = ?",
        ("login_fail_ip", "testclient"),
    )


def _on_the_second_factor(lang: str = "en"):
    """A client parked on the 2FA step, plus its pending token and TOTP secret."""
    db.init_db()
    _cleanup()
    _forget_rate_limit()
    user_id = auth.create_account(
        USERNAME, PASSWORD, "Lockout Host", must_change_password=False
    )
    secret = auth.new_totp_secret()
    auth.enable_totp(user_id, secret, auth.new_recovery_codes())
    client = TestClient(app)
    client.cookies.set(host_i18n.LANG_COOKIE, lang)
    challenge = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert challenge.status_code == 200, challenge.text
    token = re.search(r'name="pending" value="([^"]+)"', challenge.text)
    assert token, challenge.text
    return client, token.group(1), secret


def _finish() -> None:
    _forget_rate_limit()
    _cleanup()


# --- the wrong-code message ----------------------------------------------


def test_a_wrong_code_explains_that_codes_rotate():
    client, token, _ = _on_the_second_factor()
    try:
        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": "000000"},
            follow_redirects=False,
        )

        assert response.status_code == 401
        assert host_i18n.translate("en", "auth.error.code_invalid") in _page(response)
    finally:
        _finish()


def test_the_wrong_code_message_is_translated():
    client, token, _ = _on_the_second_factor("cs")
    try:
        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": "000000"},
            follow_redirects=False,
        )

        assert host_i18n.translate("cs", "auth.error.code_invalid") in _page(response)
    finally:
        _finish()


def test_a_wrong_code_does_not_offer_the_start_over_link():
    """Only the lockout sends them back to the beginning; a typo should not."""
    client, token, _ = _on_the_second_factor()
    try:
        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": "000000"},
            follow_redirects=False,
        )

        assert host_i18n.translate("en", "auth.error.code_locked_again") not in _page(response)
    finally:
        _finish()


# --- the lockout message -------------------------------------------------


def test_a_locked_out_host_is_told_to_start_again_with_a_link():
    client, token, _ = _on_the_second_factor()
    try:
        for _ in range(rate_limit._LOGIN_MAX_FAILURES):
            rate_limit.record_login_failure(_key())

        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": "000000"},
            follow_redirects=False,
        )

        assert response.status_code == 429
        assert host_i18n.translate("en", "auth.error.code_locked") in _page(response)
        alert = re.search(
            r'<div class="auth-alert" role="alert">(.*?)</div>', response.text, re.S
        )
        assert alert, response.text
        assert '<a href="/login">' in alert.group(1)
        assert host_i18n.translate("en", "auth.error.code_locked_again") in alert.group(1)
    finally:
        _finish()


def test_the_lockout_message_is_translated():
    client, token, _ = _on_the_second_factor("cs")
    try:
        for _ in range(rate_limit._LOGIN_MAX_FAILURES):
            rate_limit.record_login_failure(_key())

        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": "000000"},
            follow_redirects=False,
        )

        assert host_i18n.translate("cs", "auth.error.code_locked") in _page(response)
        assert host_i18n.translate("cs", "auth.error.code_locked_again") in _page(response)
    finally:
        _finish()


def test_a_lockout_beats_a_wrong_code():
    """A locked-out host must not be told the code was wrong."""
    client, token, _ = _on_the_second_factor()
    try:
        for _ in range(rate_limit._LOGIN_MAX_FAILURES):
            rate_limit.record_login_failure(_key())

        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": "000000"},
            follow_redirects=False,
        )

        assert host_i18n.translate("en", "auth.error.code_invalid") not in _page(response)
    finally:
        _finish()


# --- a pending token that has died ---------------------------------------


def test_a_dead_pending_token_says_the_page_expired():
    """The 15-minute wait outlives the 10-minute token; say so, don't just drop them."""
    client, _, _ = _on_the_second_factor()
    try:
        response = client.post(
            "/login/2fa",
            data={"pending": "not-a-token", "code": "000000"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/login?notice=2fa_expired"
    finally:
        _finish()


def test_the_expired_notice_is_what_the_login_page_then_shows():
    client, _, _ = _on_the_second_factor()
    try:
        landing = client.post(
            "/login/2fa",
            data={"pending": "not-a-token", "code": "000000"},
            follow_redirects=True,
        )

        assert landing.status_code == 200
        assert host_i18n.translate("en", "auth.notice.2fa_expired") in _page(landing)
    finally:
        _finish()


def test_the_expired_notice_is_translated():
    client, _, _ = _on_the_second_factor("cs")
    try:
        landing = client.post(
            "/login/2fa",
            data={"pending": "not-a-token", "code": "000000"},
            follow_redirects=True,
        )

        assert host_i18n.translate("cs", "auth.notice.2fa_expired") in _page(landing)
    finally:
        _finish()


# --- the copies the item names -------------------------------------------


def test_both_error_copies_match_the_audited_wording():
    assert host_i18n.translate("en", "auth.error.code_invalid") == (
        "That code didn't work. Codes change every 30 seconds — enter the one showing now."
    )
    assert host_i18n.translate("cs", "auth.error.code_invalid") == (
        "Kód nefunguje. Kódy se mění každých 30 vteřin — zadejte ten, který vidíte teď."
    )
    assert host_i18n.translate("en", "auth.error.code_locked") == (
        "Too many wrong codes. Wait 15 minutes, then log in again from the start."
    )
    assert host_i18n.translate("cs", "auth.error.code_locked") == (
        "Příliš mnoho chybných kódů. Počkejte 15 minut a pak se přihlaste znovu od začátku."
    )


def test_the_lockout_link_copy_exists_in_both_languages():
    assert host_i18n.translate("en", "auth.error.code_locked_again")
    assert host_i18n.translate("cs", "auth.error.code_locked_again")
    assert host_i18n.translate("en", "auth.error.code_locked_again") != (
        host_i18n.translate("cs", "auth.error.code_locked_again")
    )


def test_a_live_code_still_signs_the_host_in():
    """Guard on the assumption the two messages rest on: the happy path is untouched."""
    client, token, secret = _on_the_second_factor()
    try:
        response = client.post(
            "/login/2fa",
            data={"pending": token, "code": pyotp.TOTP(secret).now()},
            follow_redirects=False,
        )

        assert response.status_code == 303
    finally:
        _finish()


# --- the per-account second-factor budget --------------------------------


def test_ten_failed_codes_lock_one_account_only():
    db.init_db()
    db.execute("DELETE FROM rate_limit_event WHERE scope = '2fa_fail_account'")
    try:
        for _ in range(10):
            rate_limit.record_account_2fa_failure(99)

        assert rate_limit.account_2fa_blocked(99) is True
        assert rate_limit.account_2fa_blocked(98) is False
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE scope = '2fa_fail_account'")


# --- replay: a code or recovery code is spent when it is used --------------


def test_the_same_totp_code_is_refused_the_second_time():
    db.init_db()
    _cleanup()
    try:
        user_id = auth.create_account(
            USERNAME, PASSWORD, "Lockout Host", must_change_password=False
        )
        secret = auth.new_totp_secret()
        auth.enable_totp(user_id, secret, auth.new_recovery_codes())
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        code = pyotp.TOTP(secret).now()

        assert auth.verify_second_factor(account, code) is True
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        assert auth.verify_second_factor(account, code) is False
    finally:
        _cleanup()


def test_a_recovery_code_can_only_be_spent_once():
    db.init_db()
    _cleanup()
    try:
        user_id = auth.create_account(
            USERNAME, PASSWORD, "Lockout Host", must_change_password=False
        )
        codes = auth.new_recovery_codes()
        auth.enable_totp(user_id, auth.new_totp_secret(), codes)
        stale = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))

        assert auth.verify_second_factor(stale, codes[0]) is True
        # The second request still holds the row it read before the first spend.
        assert auth.verify_second_factor(stale, codes[0]) is False
    finally:
        _cleanup()
