"""0911: a host stays signed in, and a known device skips the login Turnstile."""
from __future__ import annotations

import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.responses import Response

from app import auth, config, db, mail, templating, turnstile
from app import signup as signup_app
from app.main import app
from tests.conftest import login_as

BASE = "https://testserver"
DAY = 60 * 60 * 24


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://ubyhost.test")
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    # Production behaviour: the login Turnstile is required unless a device is trusted.
    monkeypatch.setattr(turnstile, "required", lambda: True)
    yield


def _host(role_name: str = "Persist Host"):
    token = uuid.uuid4().hex[:10]
    email = f"persist-{token}@example.test"
    username = f"persist{token}"
    auth.create_account(email, role_name, username=username)
    account = auth.account_by_email(email)
    return account, email, username


def _set_cookie_values(response) -> list[str]:
    return response.headers.getlist("set-cookie")


def _cookie_value(set_cookie: str) -> str:
    return set_cookie.split(";", 1)[0].split("=", 1)[1]


def test_session_cookie_is_lax_httponly_and_secure_when_secure_cookies_on(monkeypatch):
    monkeypatch.setattr(auth, "secure_cookies", lambda: True)
    response = Response()
    auth.attach_session(response, "token-value", remember=True)
    header = _set_cookie_values(response)[0].lower()
    assert "samesite=lax" in header
    assert "httponly" in header
    assert "secure" in header
    assert "path=/" in header


def test_logout_cookie_is_also_lax(monkeypatch):
    monkeypatch.setattr(auth, "secure_cookies", lambda: True)
    response = Response()
    auth.clear_session(response)
    header = _set_cookie_values(response)[0].lower()
    assert "samesite=lax" in header
    assert "httponly" in header


def test_remember_cookie_is_re_signed_after_a_day_with_the_same_login_time():
    now = int(time.time())
    payload = {"uid": 7, "sv": 0, "rm": 1, "iat": now - 3 * DAY, "rf": now - 2 * DAY}
    request = SimpleNamespace(state=SimpleNamespace(session_payload=payload))
    response = Response()
    auth.refresh_session_cookie(request, response)
    headers = _set_cookie_values(response)
    assert len(headers) == 1
    token = _cookie_value(headers[0])
    refreshed = auth._serializer().loads(token, max_age=auth.SESSION_REMEMBER_MAX_AGE)
    assert refreshed["iat"] == now - 3 * DAY
    assert refreshed["rf"] >= now - 5
    assert refreshed["uid"] == 7


def test_recent_refresh_does_not_re_sign_the_cookie():
    now = int(time.time())
    payload = {"uid": 7, "sv": 0, "rm": 1, "iat": now - DAY, "rf": now - 3600}
    request = SimpleNamespace(state=SimpleNamespace(session_payload=payload))
    response = Response()
    auth.refresh_session_cookie(request, response)
    assert _set_cookie_values(response) == []


def test_a_session_idle_for_31_days_is_rejected(monkeypatch):
    real_time = time.time
    past = real_time() - 31 * DAY
    monkeypatch.setattr(time, "time", lambda: past)
    token = auth.issue_session(7, 0, remember=True)
    monkeypatch.setattr(time, "time", real_time)
    assert auth._session_payload(token) is None


def test_a_session_older_than_90_days_from_login_is_rejected():
    token = auth.issue_session(7, 0, remember=True, issued_at=int(time.time()) - 91 * DAY)
    assert auth._session_payload(token) is None


def test_a_session_within_both_limits_is_accepted():
    token = auth.issue_session(7, 0, remember=True, issued_at=int(time.time()) - 60 * DAY)
    payload = auth._session_payload(token)
    assert payload is not None and payload["uid"] == 7


def test_login_without_a_device_cookie_and_without_a_token_fails_turnstile():
    account, email, _ = _host()
    client = TestClient(app, base_url=BASE)
    response = client.post("/login", data={"email": email})
    assert response.status_code == 403


def test_login_with_the_device_cookie_for_that_email_skips_turnstile():
    account, email, username = _host()
    signed_in = TestClient(app, base_url=BASE)
    login_as(signed_in, username, url="/login?lang=en")
    device = signed_in.cookies.get(auth.DEVICE_COOKIE)
    assert device, "login should set the device cookie"

    new_browser = TestClient(app, base_url=BASE)
    new_browser.cookies.set(auth.DEVICE_COOKIE, device)
    response = new_browser.post("/login", data={"email": email})
    assert response.status_code == 200


def test_device_cookie_for_another_email_does_not_skip_turnstile():
    account, email, username = _host()
    other, other_email, _ = _host("Other Host")
    signed_in = TestClient(app, base_url=BASE)
    login_as(signed_in, username, url="/login?lang=en")
    device = signed_in.cookies.get(auth.DEVICE_COOKIE)

    new_browser = TestClient(app, base_url=BASE)
    new_browser.cookies.set(auth.DEVICE_COOKIE, device)
    response = new_browser.post("/login", data={"email": other_email})
    assert response.status_code == 403


def test_device_cookie_with_a_stale_session_version_does_not_skip_turnstile():
    account, email, username = _host()
    signed_in = TestClient(app, base_url=BASE)
    login_as(signed_in, username, url="/login?lang=en")
    device = signed_in.cookies.get(auth.DEVICE_COOKIE)
    db.execute(
        "UPDATE user_account SET session_version = session_version + 1 WHERE id = ?",
        (account["id"],),
    )

    new_browser = TestClient(app, base_url=BASE)
    new_browser.cookies.set(auth.DEVICE_COOKIE, device)
    response = new_browser.post("/login", data={"email": email})
    assert response.status_code == 403


def test_signup_still_requires_turnstile(monkeypatch):
    asked: list[str] = []

    def refuse(request, token, action):
        asked.append(action)
        return False

    monkeypatch.setattr(signup_app, "enabled", lambda: True)
    monkeypatch.setattr(turnstile, "verify", refuse)
    response = TestClient(app, base_url=BASE).post(
        "/signup", data={"email": "new-signup@example.test"}
    )
    assert "host_signup" in asked
    assert response.status_code == 403


def test_login_page_hides_the_widget_with_a_valid_device_cookie(monkeypatch):
    monkeypatch.setattr(config, "TURNSTILE_SITE_KEY", "test-site-key")
    monkeypatch.setitem(templating.templates.env.globals, "turnstile_site_key", "test-site-key")
    account, email, username = _host()
    signed_in = TestClient(app, base_url=BASE)
    login_as(signed_in, username, url="/login?lang=en")
    device = signed_in.cookies.get(auth.DEVICE_COOKIE)
    assert device, "login should set the device cookie"

    new_browser = TestClient(app, base_url=BASE)
    new_browser.cookies.set(auth.DEVICE_COOKIE, device)
    body = new_browser.get("/login?lang=en").text
    assert "cf-turnstile" not in body
    assert "challenges.cloudflare.com" not in body


def test_login_page_shows_the_widget_without_a_device_cookie(monkeypatch):
    monkeypatch.setitem(templating.templates.env.globals, "turnstile_site_key", "test-site-key")
    body = TestClient(app, base_url=BASE).get("/login?lang=en").text
    assert "cf-turnstile" in body
    assert "challenges.cloudflare.com" in body


def test_login_page_shows_the_widget_with_a_forged_or_stale_device_cookie(monkeypatch):
    monkeypatch.setattr(config, "TURNSTILE_SITE_KEY", "test-site-key")
    monkeypatch.setitem(templating.templates.env.globals, "turnstile_site_key", "test-site-key")
    garbage = TestClient(app, base_url=BASE)
    garbage.cookies.set(auth.DEVICE_COOKIE, "garbage")
    assert "cf-turnstile" in garbage.get("/login?lang=en").text

    account, email, username = _host()
    signed_in = TestClient(app, base_url=BASE)
    login_as(signed_in, username, url="/login?lang=en")
    device = signed_in.cookies.get(auth.DEVICE_COOKIE)
    db.execute(
        "UPDATE user_account SET session_version = session_version + 1 WHERE id = ?",
        (account["id"],),
    )
    stale = TestClient(app, base_url=BASE)
    stale.cookies.set(auth.DEVICE_COOKIE, device)
    assert "cf-turnstile" in stale.get("/login?lang=en").text


def test_turnstile_failure_rerenders_the_form_with_the_widget(monkeypatch):
    monkeypatch.setattr(config, "TURNSTILE_SITE_KEY", "test-site-key")
    monkeypatch.setitem(templating.templates.env.globals, "turnstile_site_key", "test-site-key")
    account, email, username = _host()
    other, other_email, _ = _host("Other Host")
    signed_in = TestClient(app, base_url=BASE)
    login_as(signed_in, username, url="/login?lang=en")
    device = signed_in.cookies.get(auth.DEVICE_COOKIE)

    new_browser = TestClient(app, base_url=BASE)
    new_browser.cookies.set(auth.DEVICE_COOKIE, device)
    response = new_browser.post("/login", data={"email": other_email})
    assert response.status_code == 403
    assert "cf-turnstile" in response.text
