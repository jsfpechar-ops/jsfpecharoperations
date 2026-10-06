"""Task 0004: passkeys, end to end against a software authenticator.

The server's WebAuthn checks (py_webauthn) run unmodified; the authenticator
in ``tests/webauthn_soft.py`` signs with a real P-256 key.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, mail, passkeys, retention
from app.main import app
from tests.conftest import csrf_token_for, login_as
from tests.webauthn_soft import SoftAuthenticator

BASE = "https://ubyhost.test"
ORIGIN = BASE
RP_ID = "ubyhost.test"
EMAIL = "passkey-host@example.test"
OTHER = "passkey-other@example.test"


@pytest.fixture(autouse=True)
def https_site(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", BASE)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    _clean()
    yield
    _clean()


def _clean():
    for address in (EMAIL, OTHER):
        row = db.query_one("SELECT id FROM user_account WHERE email = ?", (address,))
        if not row:
            continue
        for table in ("passkey", "webauthn_challenge", "login_token", "legal_acceptance"):
            db.execute(f"DELETE FROM {table} WHERE user_account_id = ?", (row["id"],))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM webauthn_challenge WHERE user_account_id IS NULL")
    db.execute("DELETE FROM rate_limit_event WHERE scope LIKE 'passkey%'")


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _account(email=EMAIL, username="passkey-host"):
    user_id = auth.create_account(email, "Passkey Host", username=username)
    return db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))


def _post(client, url, body=None):
    return client.post(
        url, json=body or {},
        headers={"X-CSRF-Token": csrf_token_for(client), "Accept": "application/json"},
    )


def _signed_in(account):
    client = _client()
    login_as(client, account["username"], url="/login?lang=en")
    return client


def _add(client, authenticator=None, **create):
    authenticator = authenticator or SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID)
    options = _post(client, "/account/passkeys/options")
    assert options.status_code == 200, options.text
    answer = authenticator.create(options.json(), **create)
    return authenticator, _post(client, "/account/passkeys", {"credential": answer})


def _login(authenticator, client=None, **get):
    client = client or _client()
    options = _post(client, "/login/passkey/options")
    assert options.status_code == 200, options.text
    answer = authenticator.get(options.json(), **get)
    return client, _post(client, "/login/passkey", {"credential": answer, "next": "/settings"})


# --- adding ----------------------------------------------------------------


def test_options_ask_for_a_discoverable_verified_passkey_with_an_opaque_handle():
    account = _account()
    client = _signed_in(account)
    options = _post(client, "/account/passkeys/options").json()
    assert options["rp"] == {"id": RP_ID, "name": "UbyHost"}
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["attestation"] == "none"
    handle = db.query_one(
        "SELECT webauthn_user_handle FROM user_account WHERE id = ?", (account["id"],)
    )["webauthn_user_handle"]
    assert options["user"]["id"] == handle
    assert str(account["id"]) != handle and EMAIL not in handle
    # Only a hash of the challenge is stored.
    row = db.query_one(
        "SELECT * FROM webauthn_challenge WHERE user_account_id = ? ORDER BY id DESC",
        (account["id"],),
    )
    assert row["purpose"] == "register" and options["challenge"] not in row["challenge_hash"]


def test_adding_a_passkey_stores_only_public_data_audits_and_mails_the_owner():
    account = _account()
    client = _signed_in(account)
    authenticator, response = _add(client)
    assert response.status_code == 200, response.text
    assert response.json()["redirect"].startswith("/settings?msg=")
    row = db.query_one("SELECT * FROM passkey WHERE user_account_id = ?", (account["id"],))
    assert row["credential_id"] and row["public_key"] and row["sign_count"] == 0
    assert row["backed_up"] == 1 and row["name"] == "Passkey"
    assert "internal" in row["transports"]
    assert db.query_one(
        "SELECT 1 FROM audit WHERE action = 'passkey_added' AND owner_user_id = ?",
        (account["id"],),
    )
    notice = db.query_one(
        "SELECT to_email, payload FROM email_outbox WHERE kind = 'passkey_added' "
        "AND owner_user_id = ?",
        (account["id"],),
    )
    assert notice["to_email"] == EMAIL and "/login/link" not in notice["payload"]
    prompted = db.query_one(
        "SELECT two_factor_prompted_at FROM user_account WHERE id = ?", (account["id"],)
    )
    assert prompted["two_factor_prompted_at"]


def test_the_new_passkey_is_named_after_the_device():
    account = _account()
    client = _signed_in(account)
    client.headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"
    _add(client)
    assert db.query_one(
        "SELECT name FROM passkey WHERE user_account_id = ?", (account["id"],)
    )["name"] == "iPhone"


def test_a_signed_out_browser_cannot_add_a_passkey():
    assert _post(_client(), "/account/passkeys/options").status_code == 401


def test_a_challenge_minted_for_one_account_cannot_add_to_another():
    first = _account()
    second = _account(OTHER, "passkey-other")
    a, b = _signed_in(first), _signed_in(second)
    options = _post(a, "/account/passkeys/options").json()
    answer = SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID).create(options)
    assert _post(b, "/account/passkeys", {"credential": answer}).status_code == 400
    assert passkeys.count_for(second["id"]) == 0


def test_registration_without_user_verification_is_refused():
    account = _account()
    _, response = _add(_signed_in(account), uv=False)
    assert response.status_code == 400
    assert passkeys.count_for(account["id"]) == 0


def test_registration_from_another_origin_is_refused():
    account = _account()
    _, response = _add(_signed_in(account), origin="https://ubyhost.test.evil.example")
    assert response.status_code == 400


def test_the_same_registration_answer_cannot_be_used_twice():
    account = _account()
    client = _signed_in(account)
    options = _post(client, "/account/passkeys/options").json()
    answer = SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID).create(options)
    assert _post(client, "/account/passkeys", {"credential": answer}).status_code == 200
    assert _post(client, "/account/passkeys", {"credential": answer}).status_code == 400
    assert passkeys.count_for(account["id"]) == 1


# --- logging in --------------------------------------------------------------


def test_a_passkey_logs_in_without_the_inbox_or_a_code():
    account = _account()
    authenticator, _ = _add(_signed_in(account))
    db.execute("UPDATE user_account SET totp_enabled = 1 WHERE id = ?", (account["id"],))
    client, response = _login(authenticator)
    assert response.status_code == 200, response.text
    assert response.json()["redirect"] == "/settings"
    assert auth.SESSION_COOKIE in response.headers.get("set-cookie", "")
    assert client.get("/settings", follow_redirects=False).status_code == 200
    audit = db.query_one(
        "SELECT detail FROM audit WHERE action = 'login' AND owner_user_id = ? ORDER BY id DESC",
        (account["id"],),
    )
    assert audit["detail"].startswith("method=passkey:")
    assert db.query_one(
        "SELECT last_used_at FROM passkey WHERE user_account_id = ?", (account["id"],)
    )["last_used_at"]


def test_login_options_name_no_account():
    options = _post(_client(), "/login/passkey/options").json()
    assert options["rpId"] == RP_ID
    assert options["userVerification"] == "required"
    assert options.get("allowCredentials", []) == []


def test_a_replayed_login_answer_is_refused():
    authenticator, _ = _add(_signed_in(_account()))
    client = _client()
    options = _post(client, "/login/passkey/options").json()
    answer = authenticator.get(options)
    assert _post(client, "/login/passkey", {"credential": answer}).status_code == 200
    assert _post(_client(), "/login/passkey", {"credential": answer}).status_code == 401


def test_a_look_alike_site_cannot_use_the_answer():
    authenticator, _ = _add(_signed_in(_account()))
    _, response = _login(authenticator, origin="https://ubyhost-login.example")
    assert response.status_code == 401
    _, response = _login(authenticator, rp_id="ubyhost-login.example")
    assert response.status_code == 401


def test_login_without_user_verification_is_refused():
    authenticator, _ = _add(_signed_in(_account()))
    _, response = _login(authenticator, uv=False)
    assert response.status_code == 401


def test_a_counter_that_goes_backwards_looks_cloned_and_is_refused():
    account = _account()
    authenticator = SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID, counting=True, synced=False)
    _add(_signed_in(account), authenticator)
    assert _login(authenticator, count=5)[1].status_code == 200
    assert _login(authenticator, count=3)[1].status_code == 401
    assert db.query_one(
        "SELECT 1 FROM audit WHERE action = 'passkey_clone_suspected' AND owner_user_id = ?",
        (account["id"],),
    )
    assert db.query_one(
        "SELECT sign_count FROM passkey WHERE user_account_id = ?", (account["id"],)
    )["sign_count"] == 5


def test_a_disabled_account_cannot_log_in_with_its_passkey():
    account = _account()
    authenticator, _ = _add(_signed_in(account))
    db.execute("UPDATE user_account SET active = 0 WHERE id = ?", (account["id"],))
    assert _login(authenticator)[1].status_code == 401


def test_an_unknown_passkey_is_refused():
    _, response = _login(SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID))
    assert response.status_code == 401


def test_repeated_failures_block_the_connection(monkeypatch):
    monkeypatch.setattr(passkeys, "FAIL_MAX_WINDOW", 2)
    stranger = SoftAuthenticator(origin=ORIGIN, rp_id=RP_ID)
    client = _client()
    for _ in range(2):
        assert _login(stranger, client)[1].status_code == 401
    assert _post(client, "/login/passkey/options").status_code == 429


def test_the_next_path_stays_on_this_site():
    authenticator, _ = _add(_signed_in(_account()))
    client = _client()
    options = _post(client, "/login/passkey/options").json()
    response = _post(client, "/login/passkey", {
        "credential": authenticator.get(options), "next": "https://evil.example/",
    })
    assert response.json()["redirect"] == "/"


# --- managing ------------------------------------------------------------------


def test_removing_a_passkey_stops_it_logging_in():
    account = _account()
    client = _signed_in(account)
    authenticator, _ = _add(client)
    passkey_id = passkeys.for_account(account["id"])[0]["id"]
    response = client.post(f"/account/passkeys/{passkey_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert passkeys.count_for(account["id"]) == 0
    assert _login(authenticator)[1].status_code == 401


def test_nobody_removes_or_renames_someone_elses_passkey():
    owner = _account()
    _add(_signed_in(owner))
    passkey_id = passkeys.for_account(owner["id"])[0]["id"]
    intruder = _signed_in(_account(OTHER, "passkey-other"))
    intruder.post(f"/account/passkeys/{passkey_id}/delete")
    intruder.post(f"/account/passkeys/{passkey_id}/rename", data={"name": "mine"})
    row = passkeys.for_account(owner["id"])[0]
    assert row["name"] == "Passkey"


def test_renaming_trims_and_keeps_the_name_short():
    account = _account()
    client = _signed_in(account)
    _add(client)
    passkey_id = passkeys.for_account(account["id"])[0]["id"]
    client.post(f"/account/passkeys/{passkey_id}/rename", data={"name": "  Work   laptop " + "x" * 80})
    name = passkeys.for_account(account["id"])[0]["name"]
    assert name.startswith("Work laptop x") and len(name) == passkeys.NAME_MAX


def test_settings_lists_passkeys_first_in_security():
    account = _account()
    client = _signed_in(account)
    _add(client)
    html = client.get("/settings").text
    security = html[html.index('id="settings-security"'):]
    assert security.index("settings-passkeys") < security.index("/account/2fa/setup")
    assert "Passkey" in security and "/account/passkeys/" in security


# --- where passkeys are offered ------------------------------------------------


def test_the_login_page_offers_the_passkey_before_the_email_form():
    html = _client().get("/login?lang=en").text
    assert html.index("data-passkey-login") < html.index('action="/login"')
    assert 'autocomplete="email webauthn"' in html
    assert '<script src="/static/passkeys.js' in html


def test_an_ip_address_site_offers_no_passkeys(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "http://127.0.0.1:8080")
    client = TestClient(app)
    html = client.get("/login?lang=en").text
    assert "data-passkey-login" not in html and "passkeys.js" not in html
    assert _post(client, "/login/passkey/options").status_code == 409


@pytest.mark.parametrize(
    "base, ok",
    [
        ("https://ubyhost.com", True),
        ("http://localhost:8080", True),
        ("http://ubyhost.com", False),
        ("https://10.0.0.5", False),
        ("http://[::1]:8080", False),
    ],
)
def test_availability_follows_the_public_address(monkeypatch, base, ok):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", base)
    assert passkeys.available() is ok


def test_the_script_is_served_from_this_site_and_calls_no_one_else():
    response = _client().get("/static/passkeys.js")
    assert response.status_code == 200
    assert "http://" not in response.text and "https://" not in response.text


# --- the one-time prompt -------------------------------------------------------


def test_the_prompt_shows_once_after_the_first_login():
    account = _account()
    client = _client()
    login_as(client, account["username"], follow_redirects=False)
    first = client.get("/")
    assert 'id="security-prompt"' in first.text
    assert first.text.index("data-passkey-supported") < first.text.index("/account/2fa/setup")
    assert 'id="security-prompt"' not in client.get("/").text
    login_as(client, account["username"], follow_redirects=False)
    assert 'id="security-prompt"' not in client.get("/").text


def test_no_prompt_with_an_authenticator_app():
    account = _account()
    db.execute("UPDATE user_account SET totp_enabled = 1 WHERE id = ?", (account["id"],))
    client = _client()
    # Straight to a session: the TOTP step is not what this test is about.
    response = client.get("/login")
    client.cookies.set(
        auth.SESSION_COOKIE, auth.issue_session(account["id"], account["session_version"])
    )
    assert response.status_code == 200
    assert 'id="security-prompt"' not in client.get("/").text


def test_no_prompt_on_settings_and_it_waits_for_the_next_page():
    account = _account()
    client = _client()
    login_as(client, account["username"], follow_redirects=False)
    assert 'id="security-prompt"' not in client.get("/settings").text
    assert 'id="security-prompt"' in client.get("/").text


# --- retention -------------------------------------------------------------------


def test_expired_ceremonies_are_deleted_a_day_later():
    _post(_client(), "/login/passkey/options")
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    db.execute("UPDATE webauthn_challenge SET expires_at = ? WHERE user_account_id IS NULL", (old,))
    assert passkeys.purge(dry_run=True) >= 1
    assert "webauthn_challenges" in dict(retention.STEPS)
    dict(retention.STEPS)["webauthn_challenges"](date.today(), False, None)
    assert not db.query_one(
        "SELECT 1 FROM webauthn_challenge WHERE expires_at = ?", (old,)
    )
