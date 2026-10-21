"""Brief 0225: urgent alerts on the host's phone: devices, queue and delivery."""
from __future__ import annotations

import json
import os
import secrets
import struct
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app import auth, config, db, host_vi_i18n, push, retention, scheduler, webpush

FCM = "https://fcm.googleapis.com/fcm/send/"


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "WEB_PUSH", True)
    yield


def _new_account() -> int:
    username = f"push{secrets.token_hex(4)}"
    return auth.create_account(f"{username}@example.test", "Push Host", role="host", username=username)


def _forget(owner: int) -> None:
    db.execute("DELETE FROM push_outbox WHERE user_account_id = ?", (owner,))
    db.execute("DELETE FROM push_subscription WHERE user_account_id = ?", (owner,))


@pytest.fixture
def account():
    owner = _new_account()
    yield owner
    _forget(owner)


class Browser:
    """A stand-in browser: its own key pair and auth secret, as pushManager makes them."""

    def __init__(self, endpoint=None):
        self.key = webpush.new_private_key()
        self.auth = os.urandom(16)
        self.endpoint = FCM + secrets.token_hex(8) if endpoint is None else endpoint

    def subscription(self):
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": webpush.b64url(webpush.public_raw(self.key)),
                "auth": webpush.b64url(self.auth),
            },
        }

    def read(self, body: bytes) -> dict:
        """Decrypt a push the way the browser does (RFC 8291)."""
        salt = body[:16]
        record_size, key_len = struct.unpack("!IB", body[16:21])
        as_public = body[21:21 + key_len]
        ua_public = webpush.public_raw(self.key)
        ecdh = self.key.exchange(ec.ECDH(), webpush.check_public_key(as_public))
        ikm = webpush._hkdf(self.auth, ecdh, b"WebPush: info\x00" + ua_public + as_public, 32)
        cek = webpush._hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = webpush._hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        plain = AESGCM(cek).decrypt(nonce, body[21 + key_len:], None)
        assert record_size == 4096 and plain.endswith(b"\x02")
        return json.loads(plain[:-1])


class PushService:
    """Records what would have gone to Apple or Google and answers ``status``."""

    def __init__(self, monkeypatch, status=201):
        self.status = status
        self.sent = []
        monkeypatch.setattr(webpush.requests, "post", self._post)

    def _post(self, url, data, headers, timeout, allow_redirects):
        self.sent.append({"url": url, "data": data, "headers": headers})
        if isinstance(self.status, Exception):
            raise self.status
        answer = type("Answer", (), {})()
        answer.status_code = self.status
        return answer


def _subscribe(account, browser=None, lang="en"):
    browser = browser or Browser()
    push.save_subscription(account, browser.subscription(), lang=lang, device="iPhone")
    return browser


def _later(minutes):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


@pytest.mark.parametrize("endpoint", [
    "https://169.254.169.254/latest/meta-data",
    "http://fcm.googleapis.com/fcm/send/x",
    "https://evil.example/fcm.googleapis.com/x",
    "https://fcm.googleapis.com.evil.example/x",
    "https://user:pw@fcm.googleapis.com/x",
    "https://fcm.googleapis.com:8443/x",
    "file:///etc/passwd",
    "",
])
def test_only_real_push_services_are_accepted(account, endpoint):
    with pytest.raises(push.SubscriptionError):
        push.save_subscription(account, Browser(endpoint).subscription(), lang="en", device="")


@pytest.mark.parametrize("endpoint", [
    "https://fcm.googleapis.com/fcm/send/abc",
    "https://web.push.apple.com/QGxabc",
    "https://updates.push.services.mozilla.com/wpush/v2/abc",
    "https://wns2-par02p.notify.windows.com/w/?token=abc",
])
def test_the_four_browser_push_services_are_accepted(account, endpoint):
    assert push.save_subscription(account, Browser(endpoint).subscription(), lang="en", device="Mac")


def test_bad_keys_are_refused(account):
    bad_point = Browser().subscription()
    bad_point["keys"]["p256dh"] = "not-a-key"
    short_secret = Browser().subscription()
    short_secret["keys"]["auth"] = webpush.b64url(b"short")
    for subscription in (bad_point, short_secret, "nonsense", {"endpoint": FCM + "x"}):
        with pytest.raises(push.SubscriptionError):
            push.save_subscription(account, subscription, lang="en", device="")


def test_the_push_address_and_keys_are_stored_encrypted(account):
    browser = _subscribe(account)
    row = db.query_one("SELECT * FROM push_subscription WHERE user_account_id = ?", (account,))
    stored = " ".join(str(value) for value in dict(row).values())
    assert browser.endpoint not in stored
    assert browser.subscription()["keys"]["p256dh"] not in stored
    assert browser.subscription()["keys"]["auth"] not in stored
    assert row["device"] == "iPhone" and row["lang"] == "en"


def test_one_browser_is_one_row_and_follows_the_account_signed_in(account):
    browser = _subscribe(account)
    _subscribe(account, browser, lang="cs")
    assert push.count_for(account) == 1
    other = _new_account()
    try:
        push.notify(account, "door_code", key="stay1", url="/reservations/1", params={})
        _subscribe(other, browser)
        assert push.count_for(account) == 0 and push.count_for(other) == 1
        # An alert queued for the first account never reaches the next person.
        assert not db.query_one("SELECT 1 AS x FROM push_outbox WHERE user_account_id = ?", (account,))
    finally:
        _forget(other)


def test_an_account_has_at_most_ten_devices(account):
    for _ in range(push.MAX_DEVICES):
        _subscribe(account)
    with pytest.raises(push.SubscriptionError):
        _subscribe(account)


def test_notify_queues_once_per_device_and_never_twice_for_one_event(account):
    _subscribe(account)
    _subscribe(account)
    args = dict(key="7:2026-10-21", url="/apartments/7", params={"property": "Flat"})
    assert push.notify(account, "filing_problem", **args) == 2
    assert push.notify(account, "filing_problem", **args) == 0


def test_only_the_four_urgent_kinds_can_be_queued_and_notify_never_raises(account):
    _subscribe(account)
    assert push.KINDS == ("filing_problem", "deadline_at_risk", "door_code", "cancelled_with_guests")
    assert push.notify(account, "guests_registered", key="1", url="/", params={}) == 0
    assert push.notify(account, "test", key="1", url="/", params={}) == 0
    assert push.notify(None, "door_code", key="1", url="/", params={}) == 0


def test_notify_does_nothing_when_push_is_switched_off(account, monkeypatch):
    _subscribe(account)
    monkeypatch.setattr(config, "WEB_PUSH", False)
    assert push.notify(account, "door_code", key="1", url="/", params={}) == 0
    assert push.drain() == {}


def test_a_delivered_alert_is_encrypted_for_the_device_in_its_language(account, monkeypatch):
    browser = _subscribe(account, lang="cs")
    service = PushService(monkeypatch)
    push.notify(
        account, "deadline_at_risk", key="stay9", url="/reservations/9",
        params={"property": "Byt 1", "date": "21.10.2026", "deadline": "23.10.2026 14:00"},
    )
    assert push.drain() == {"sent": 1}
    [request] = service.sent
    assert request["url"] == browser.endpoint
    message = browser.read(request["data"])
    assert message["title"] == "Hrozí zmeškání lhůty pro policii"
    assert "Byt 1" in message["body"] and "23.10.2026 14:00" in message["body"]
    assert message["url"] == "/reservations/9"
    assert message["tag"] == "deadline_at_risk:stay9"
    assert push.drain() == {}


def test_an_outside_address_never_becomes_the_click_target(account, monkeypatch):
    browser = _subscribe(account)
    service = PushService(monkeypatch)
    push.notify(account, "door_code", key="x", url="https://evil.example/", params={})
    push.drain()
    assert browser.read(service.sent[0]["data"])["url"] == "/"


def test_a_gone_device_is_forgotten(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch, status=410)
    push.notify(account, "door_code", key="x", url="/", params={})
    assert push.drain() == {"gone": 1}
    assert push.count_for(account) == 0


def test_a_busy_push_service_is_retried_then_given_up_after_five_tries(account, monkeypatch):
    _subscribe(account)
    service = PushService(monkeypatch, status=503)
    push.notify(account, "door_code", key="x", url="/", params={})
    assert push.drain() == {"retry": 1}
    assert push.drain() == {}
    for minutes in (2, 8, 25, 90):
        push.drain(now=_later(minutes))
    row = db.query_one(
        "SELECT state, attempts, last_status FROM push_outbox WHERE user_account_id = ?", (account,)
    )
    assert (row["state"], row["attempts"], row["last_status"]) == ("failed", 5, 503)
    assert len(service.sent) == 5


def test_an_unreachable_push_service_is_retried(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch, status=webpush.requests.ConnectionError("down"))
    push.notify(account, "door_code", key="x", url="/", params={})
    assert push.drain() == {"retry": 1}


def test_a_refusing_push_service_drops_the_device_after_five_refusals(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch, status=400)
    for n in range(push.MAX_FAILURES):
        push.notify(account, "door_code", key=f"x{n}", url="/", params={})
        assert push.drain() == {"failed": 1}
    assert push.count_for(account) == 0


def test_one_device_gets_at_most_the_daily_cap(account, monkeypatch):
    _subscribe(account)
    PushService(monkeypatch)
    for n in range(push.DAILY_CAP + 2):
        push.notify(account, "door_code", key=f"s{n}", url="/", params={})
    assert push.drain() == {"sent": push.DAILY_CAP, "capped": 2}


def test_the_test_alert_goes_to_this_device_only_and_now(account, monkeypatch):
    first = _subscribe(account)
    _subscribe(account)
    service = PushService(monkeypatch)
    assert push.send_test(account, first.endpoint) == "sent"
    assert len(service.sent) == 1
    assert first.read(service.sent[0]["data"])["title"] == "Alerts are on"
    assert push.send_test(account, FCM + "unknown") == "gone"


def test_the_server_key_is_made_once_and_kept():
    assert push.public_key() == push.public_key()
    assert len(webpush.unb64url(push.public_key())) == 65


def test_an_unreadable_server_key_is_replaced_and_its_devices_dropped(account):
    _subscribe(account)
    before = push.public_key()
    db.set_setting(push.VAPID_SETTING, "not-a-fernet-token")
    assert push.public_key() != before
    assert push.count_for(account) == 0


def test_retention_deletes_old_alerts_and_unseen_devices(account):
    _subscribe(account)
    push.notify(account, "door_code", key="old", url="/", params={})
    long_ago = (datetime.now(timezone.utc) - timedelta(days=200)).replace(microsecond=0).isoformat()
    db.execute("UPDATE push_outbox SET created_at = ? WHERE user_account_id = ?", (long_ago, account))
    assert push.purge(dry_run=True, owner_user_id=account) == 1
    db.execute("UPDATE push_subscription SET last_seen_at = ? WHERE user_account_id = ?", (long_ago, account))
    assert push.purge(owner_user_id=account) == 2
    assert push.count_for(account) == 0
    assert "push" in dict(retention.STEPS)


def test_deleting_a_workspace_deletes_its_devices_and_alerts():
    owner = _new_account()
    _subscribe(owner)
    push.notify(owner, "door_code", key="w", url="/", params={})
    retention._delete_workspace(owner)
    assert not db.query_one("SELECT 1 AS x FROM push_subscription WHERE user_account_id = ?", (owner,))
    assert not db.query_one("SELECT 1 AS x FROM push_outbox WHERE user_account_id = ?", (owner,))


def test_the_scheduler_sends_alerts_every_minute(monkeypatch):
    called = []
    monkeypatch.setattr(push, "drain", lambda: called.append(1) or {})
    scheduler._job_push()
    assert called and scheduler.job_intervals()["push"] == 1
    assert scheduler._JOB_LEVELS["push"] == "warning"


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_every_alert_has_its_own_title_and_body_in_every_host_language(lang):
    params = {"property": "P", "date": "D", "deadline": "X"}
    for kind in push.KINDS + (push.TEST_KIND,):
        text = push.message(kind, lang, params)
        assert text["title"] != f"push.msg.{kind}.title"
        assert text["body"] != f"push.msg.{kind}.body"
        if lang == "vi":
            assert f"push.msg.{kind}.title" in host_vi_i18n.STRINGS
            assert f"push.msg.{kind}.body" in host_vi_i18n.STRINGS
