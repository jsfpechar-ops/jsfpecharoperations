"""Brief 0226: the urgent-alert endpoints behind Settings > Phone app."""
from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, push
from app.main import app
from tests.conftest import csrf_token_for, login_as
from tests.test_push import Browser, PushService

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15"


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "WEB_PUSH", True)
    yield


def _signed_in():
    username = f"pr{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Push Routes", role="host", username=username)
    client = TestClient(app, base_url="https://testserver")
    login_as(client, username, url="/login?lang=en")
    return client, owner


def _post(client, url, body, user_agent="testclient"):
    return client.post(
        url,
        json=body,
        headers={
            "X-CSRF-Token": csrf_token_for(client),
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )


def _lang(owner):
    return db.query_one("SELECT lang FROM push_subscription WHERE user_account_id = ?", (owner,))["lang"]


def test_turning_on_stores_this_device_with_its_name_and_language():
    client, owner = _signed_in()
    browser = Browser()
    response = _post(
        client, "/account/push/subscribe",
        {"subscription": browser.subscription(), "lang": "cs"}, user_agent=IPHONE,
    )
    assert response.status_code == 200 and response.json() == {"ok": True}
    [device] = push.devices_for(owner)
    assert device["device"] == "iPhone"
    assert _lang(owner) == "cs"


def test_a_browser_that_does_not_say_what_it_is_gets_no_made_up_name():
    client, owner = _signed_in()
    _post(client, "/account/push/subscribe", {"subscription": Browser().subscription()})
    assert push.devices_for(owner)[0]["device"] == ""


def test_a_foreign_push_address_is_refused_with_a_readable_error():
    client, owner = _signed_in()
    response = _post(
        client, "/account/push/subscribe",
        {"subscription": Browser("https://evil.example/x").subscription()},
    )
    assert response.status_code == 400 and response.json()["error"]
    assert push.count_for(owner) == 0


def test_refresh_keeps_a_known_device_current_and_never_creates_one():
    client, owner = _signed_in()
    browser = Browser()
    refresh = {"endpoint": browser.endpoint, "lang": "vi"}
    assert _post(client, "/account/push/refresh", refresh).json() == {"known": False}
    assert push.count_for(owner) == 0
    _post(client, "/account/push/subscribe", {"subscription": browser.subscription(), "lang": "en"})
    assert _post(client, "/account/push/refresh", refresh).json() == {"known": True}
    assert _lang(owner) == "vi"


def test_turning_off_forgets_this_device():
    client, owner = _signed_in()
    browser = Browser()
    _post(client, "/account/push/subscribe", {"subscription": browser.subscription()})
    assert _post(client, "/account/push/unsubscribe", {"endpoint": browser.endpoint}).json() == {"ok": True}
    assert push.count_for(owner) == 0


def test_the_test_alert_reaches_this_device_and_is_limited_to_five_an_hour(monkeypatch):
    client, owner = _signed_in()
    browser = Browser()
    service = PushService(monkeypatch)
    _post(client, "/account/push/subscribe", {"subscription": browser.subscription()})
    for _ in range(5):
        response = _post(client, "/account/push/test", {"endpoint": browser.endpoint})
        assert response.status_code == 200 and response.json()["message"]
    assert _post(client, "/account/push/test", {"endpoint": browser.endpoint}).status_code == 429
    assert len(service.sent) == 5
    assert browser.read(service.sent[0]["data"])["url"] == "/settings#settings-group-phone"


def test_a_device_is_removed_from_settings_without_javascript_by_its_owner_only():
    client, owner = _signed_in()
    stranger, _ = _signed_in()
    _post(client, "/account/push/subscribe", {"subscription": Browser().subscription()})
    [device] = push.devices_for(owner)
    stranger.post(f"/account/push/devices/{device['id']}/delete", follow_redirects=False)
    assert push.count_for(owner) == 1
    response = client.post(f"/account/push/devices/{device['id']}/delete", follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "#settings-group-phone" in response.headers["location"]
    assert push.count_for(owner) == 0


def test_a_signed_out_browser_cannot_turn_alerts_on():
    client = TestClient(app, base_url="https://testserver")
    response = _post(client, "/account/push/subscribe", {"subscription": Browser().subscription()})
    assert response.status_code in (401, 403)


def test_nothing_is_stored_when_push_is_switched_off(monkeypatch):
    client, owner = _signed_in()
    monkeypatch.setattr(config, "WEB_PUSH", False)
    response = _post(client, "/account/push/subscribe", {"subscription": Browser().subscription()})
    assert response.status_code == 409 and push.count_for(owner) == 0
