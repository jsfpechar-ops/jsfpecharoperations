# 0226: Push endpoints and Settings data (turn on, refresh, test, turn off, remove)

Status: review
Depends on: 0225 | Branch: claude/project-thread-w35ftw
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the endpoints that `static/pwa.js` (brief 0227) calls to turn urgent alerts on and off for this device, keep it current, and send a test; a no-JavaScript form to remove a device; the Settings page data; and all Settings copy in EN, CS and VI.

## 2. Context

- `App/app/push.py` (0225) has `save_subscription`, `remove`, `remove_endpoint`, `send_test`, `devices_for`, `count_for`, `public_key`, `enabled`, `SubscriptionError` (message `"too many devices"` when the account has 10).
- Pattern to copy: `App/app/routes/passkeys.py` (JSON endpoints with `X-CSRF-Token`, included by `routes/admin.py`, whose router adds the CSRF check). `device_label(user_agent, lang)` in that file gives "iPhone", "Android", "Mac"…, or the passkey fallback name, which we turn into an empty string.
- Alerts are per person: every endpoint acts on the signed-in account and refuses while an admin previews someone else's workspace (`auth.workspace_user(request)["id"] != auth.current_user(request)["id"]`). Alerts about another host's stays must never reach the admin's phone.
- **Refresh never creates a device**: a device removed in Settings stays removed until its owner presses "Turn on" again on it.
- Test alerts: at most 5 per account per hour (`rate_limit`), and they also count toward the device's daily cap in `push.py`.
- Audit lines carry counts and sources only, never an endpoint.
- Copy: EN, CS, VI; no em dashes; flash messages go through `_flash` with a key that starts with `flash.`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/push.py` | edit | add `refresh()` |
| `App/app/routes/push.py` | new | the five endpoints |
| `App/app/routes/admin.py` | edit | import, include router, Settings context |
| `App/app/host_i18n.py` | edit | Settings copy EN, CS |
| `App/app/host_vi_i18n.py` | edit | Settings copy VI |
| `App/tests/test_push_routes.py` | new | endpoint tests |

No other file may change.

## 4. Steps

**Step 1.** `App/app/push.py`. Anchor: `def remove_endpoint(account_id: int, endpoint: str) -> bool:`. Insert BEFORE it:

```python
def refresh(account_id: int, endpoint: str, *, lang: str) -> bool:
    """A visit from a device that has alerts on: keep its language and last visit.

    Never creates a row: a device removed in Settings stays removed until its
    owner turns alerts on again on it. False when this account has no such device.
    """
    row = db.query_one(
        "SELECT id FROM push_subscription WHERE endpoint_hash = ? AND user_account_id = ?",
        (_hash(str(endpoint or "")), account_id),
    )
    if not row:
        return False
    db.execute(
        "UPDATE push_subscription SET lang = ?, last_seen_at = ? WHERE id = ?",
        (host_i18n.normalise_language(lang), db.utcnow(), row["id"]),
    )
    return True


```

**Step 2.** Create `App/app/routes/push.py` with exactly:

```python
"""Urgent alerts on this device (brief 0226): turn on, refresh, test, turn off.

JSON endpoints for static/pwa.js, with the CSRF token in X-CSRF-Token, and one
plain form (remove a device) that works without JavaScript. They always act on
the signed-in account and refuse while an admin previews another workspace:
alerts about someone else's stays must not reach the admin's phone.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from .. import auth, db, host_i18n, push, rate_limit
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .passkeys import device_label

router = APIRouter()

_PHONE = "/settings#settings-group-phone"
_MAX_BODY = 8 * 1024
TEST_MAX_PER_HOUR = 5


def _text(request: Request, key: str) -> str:
    return host_i18n.translate(host_i18n.lang_from_request(request), key)


def _answer(payload: dict, status_code: int = 200) -> JSONResponse:
    response = JSONResponse(payload, status_code=status_code)
    response.headers["Cache-Control"] = "no-store"
    return response


def _error(request: Request, key: str, status_code: int) -> JSONResponse:
    return _answer({"error": _text(request, key)}, status_code)


async def _body(request: Request) -> dict:
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        return {}
    try:
        data = json.loads(raw or b"{}")
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def own_account(request: Request):
    """The signed-in account, or None while an admin previews another workspace."""
    account = auth.current_user(request)
    workspace = auth.workspace_user(request)
    if not account or not workspace or int(workspace["id"]) != int(account["id"]):
        return None
    return account


def _device(request: Request) -> str:
    """A coarse device family ("iPhone"); empty when the browser does not say."""
    label = device_label(request.headers.get("user-agent", ""), "en")
    return "" if label == host_i18n.translate("en", "passkeys.default_name") else label


@router.post("/account/push/subscribe")
async def push_subscribe(request: Request):
    account = own_account(request)
    if not account:
        return _error(request, "push.error.signed_out", 401)
    if not push.enabled():
        return _error(request, "push.error.failed", 409)
    data = await _body(request)
    try:
        push.save_subscription(
            account["id"],
            data.get("subscription"),
            lang=str(data.get("lang") or host_i18n.lang_from_request(request)),
            device=_device(request),
        )
    except push.SubscriptionError as exc:
        key = "push.error.too_many" if str(exc) == "too many devices" else "push.error.failed"
        return _error(request, key, 400)
    db.audit("push_device_added", f"devices={push.count_for(account['id'])}", owner_user_id=account["id"])
    return _answer({"ok": True})


@router.post("/account/push/refresh")
async def push_refresh(request: Request):
    account = own_account(request)
    if not account:
        return _error(request, "push.error.signed_out", 401)
    data = await _body(request)
    known = push.refresh(
        account["id"],
        str(data.get("endpoint") or ""),
        lang=str(data.get("lang") or host_i18n.lang_from_request(request)),
    )
    return _answer({"known": known})


@router.post("/account/push/unsubscribe")
async def push_unsubscribe(request: Request):
    account = own_account(request)
    if not account:
        return _error(request, "push.error.signed_out", 401)
    data = await _body(request)
    if push.remove_endpoint(account["id"], str(data.get("endpoint") or "")):
        db.audit("push_device_removed", "source=device", owner_user_id=account["id"])
    return _answer({"ok": True})


@router.post("/account/push/test")
async def push_test(request: Request):
    account = own_account(request)
    if not account:
        return _error(request, "push.error.signed_out", 401)
    key = str(account["id"])
    if rate_limit.blocked("push_test", key, TEST_MAX_PER_HOUR, 3600):
        return _error(request, "push.error.rate_limited", 429)
    rate_limit.record("push_test", key)
    data = await _body(request)
    outcome = await run_in_threadpool(push.send_test, account["id"], str(data.get("endpoint") or ""))
    if outcome != "sent":
        return _error(request, "push.error.test_failed", 502)
    return _answer({"ok": True, "message": _text(request, "push.test_sent")})


@router.post("/account/push/devices/{device_id}/delete")
def push_device_delete(request: Request, device_id: int):
    account = own_account(request)
    if not account:
        return _back(_PHONE, err=_flash(request, "flash.push.signed_out"))
    if push.remove(account["id"], device_id):
        db.audit("push_device_removed", "source=settings", owner_user_id=account["id"])
        return _back(_PHONE, msg=_flash(request, "flash.push.device_removed"))
    return _back(_PHONE)
```

Run: `cd App && .venv/bin/python -c "import app.routes.push" 2>&1 | tail -3`. Expected: no error.

**Step 3.** `App/app/routes/admin.py`, four edits:

a. In the `from .. import (` block, replace the line `    passkeys,` (line 44) with two lines `    passkeys,` and `    push,`.

b. Anchor `from . import passkeys as passkey_routes`. Insert after it: `from . import push as push_routes`.

c. Anchor `router.include_router(passkey_routes.router)`. Insert after it: `router.include_router(push_routes.router)`.

d. Anchor `            "passkeys_available": passkeys.available(),`. Insert after it:

```python
            # Brief 0226: Settings > Phone app, urgent alerts on this device.
            "push_available": _push_available(request),
            "push_key": push.public_key() if _push_available(request) else "",
            "push_devices": _own_push_devices(request),
```

e. Anchor `def _own_passkeys(request: Request):`. Insert BEFORE it:

```python
def _push_available(request: Request) -> bool:
    """Alerts are per person: off while an admin previews another workspace."""
    return bool(push.enabled() and push_routes.own_account(request))


def _own_push_devices(request: Request):
    account = push_routes.own_account(request)
    return push.devices_for(account["id"]) if account and push.enabled() else []


```

Run: `cd App && .venv/bin/python -c "import app.main" 2>&1 | tail -3`. Expected: no error.

**Step 4.** `App/app/host_i18n.py`. Anchor (added by 0225):

```python
for _lang, _strings in _PUSH_MESSAGE_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Insert after it:

```python

# Brief 0226: Settings > Phone app > urgent alerts on this device.
_PUSH_SETTINGS_STRINGS = {
    "en": {
        "push.title": "Urgent alerts on this device",
        "push.help": "Only problems that need you now: a police report that failed, a police deadline at risk, a missing door code, or a cancelled stay whose guests had registered. You still get every e-mail. Logging out turns alerts off on that device.",
        "push.on": "Turn on",
        "push.off": "Turn off",
        "push.test": "Send a test",
        "push.state_on": "On",
        "push.ios_first": "On iPhone, add UbyHost to your Home Screen first (above), then open it from there to turn on alerts.",
        "push.unsupported": "This browser cannot show alerts. Use Chrome, Edge, Firefox or Safari, or on iPhone the app from your Home Screen.",
        "push.denied": "Alerts are blocked for UbyHost. Allow notifications for this site in the browser or phone settings, then reload this page.",
        "push.test_sent": "Test sent. It should arrive within a minute.",
        "push.devices": "Devices with alerts on",
        "push.device_added": "Added %(date)s",
        "push.device_unknown": "Device",
        "push.device_remove": "Remove",
        "push.error.failed": "Could not turn on alerts. Try again.",
        "push.error.too_many": "Alerts are on for 10 devices already. Remove one below first.",
        "push.error.signed_out": "Log in again, then try once more.",
        "push.error.rate_limited": "Too many tests in a row. Try again in an hour.",
        "push.error.test_failed": "The test did not go through. Turn alerts off and on again.",
        "flash.push.device_removed": "That device no longer gets alerts.",
        "flash.push.signed_out": "Log in again, then try once more.",
    },
    "cs": {
        "push.title": "Naléhavá upozornění na tomto zařízení",
        "push.help": "Jen problémy, které potřebují vás hned: nepřijaté hlášení policii, hrozící zmeškání lhůty, chybějící kód ke dveřím nebo zrušený pobyt s registrovanými hosty. E-maily chodí dál. Odhlášením se upozornění na daném zařízení vypnou.",
        "push.on": "Zapnout",
        "push.off": "Vypnout",
        "push.test": "Poslat zkoušku",
        "push.state_on": "Zapnuto",
        "push.ios_first": "Na iPhonu si nejdřív přidejte UbyHost na plochu (výše) a upozornění zapněte v aplikaci otevřené z plochy.",
        "push.unsupported": "Tento prohlížeč upozornění zobrazit neumí. Použijte Chrome, Edge, Firefox nebo Safari, na iPhonu aplikaci z plochy.",
        "push.denied": "Upozornění od UbyHost jsou zablokovaná. Povolte oznámení pro tento web v nastavení prohlížeče nebo telefonu a stránku načtěte znovu.",
        "push.test_sent": "Zkouška odeslána. Měla by dorazit do minuty.",
        "push.devices": "Zařízení se zapnutými upozorněními",
        "push.device_added": "Přidáno %(date)s",
        "push.device_unknown": "Zařízení",
        "push.device_remove": "Odebrat",
        "push.error.failed": "Upozornění se nepodařilo zapnout. Zkuste to znovu.",
        "push.error.too_many": "Upozornění už máte na 10 zařízeních. Nejdřív jedno níže odeberte.",
        "push.error.signed_out": "Přihlaste se znovu a zkuste to ještě jednou.",
        "push.error.rate_limited": "Příliš mnoho zkoušek za sebou. Zkuste to za hodinu.",
        "push.error.test_failed": "Zkouška neprošla. Upozornění vypněte a znovu zapněte.",
        "flash.push.device_removed": "Toto zařízení už upozornění nedostává.",
        "flash.push.signed_out": "Přihlaste se znovu a zkuste to ještě jednou.",
    },
}
for _lang, _strings in _PUSH_SETTINGS_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

**Step 5.** `App/app/host_vi_i18n.py`. Anchor (added by 0225): `    "notification.job_name.push": "cảnh báo khẩn",`. Insert after it:

```python
    # Brief 0226: Settings > urgent alerts.
    "push.title": "Cảnh báo khẩn trên thiết bị này",
    "push.help": "Chỉ những sự cố cần bạn xử lý ngay: báo cáo cảnh sát bị lỗi, sắp trễ hạn khai báo, thiếu mã cửa, hoặc lượt lưu trú bị hủy đã có khách đăng ký. Bạn vẫn nhận mọi email. Đăng xuất sẽ tắt cảnh báo trên thiết bị đó.",
    "push.on": "Bật",
    "push.off": "Tắt",
    "push.test": "Gửi thử",
    "push.state_on": "Đang bật",
    "push.ios_first": "Trên iPhone, hãy thêm UbyHost vào màn hình chính trước (ở trên), rồi mở từ đó để bật cảnh báo.",
    "push.unsupported": "Trình duyệt này không hiện được cảnh báo. Hãy dùng Chrome, Edge, Firefox hoặc Safari, hoặc trên iPhone dùng ứng dụng từ màn hình chính.",
    "push.denied": "Cảnh báo của UbyHost đang bị chặn. Hãy cho phép thông báo cho trang này trong cài đặt trình duyệt hoặc điện thoại, rồi tải lại trang.",
    "push.test_sent": "Đã gửi thử. Thông báo sẽ đến trong vòng một phút.",
    "push.devices": "Thiết bị đang bật cảnh báo",
    "push.device_added": "Đã thêm %(date)s",
    "push.device_unknown": "Thiết bị",
    "push.device_remove": "Gỡ",
    "push.error.failed": "Không bật được cảnh báo. Hãy thử lại.",
    "push.error.too_many": "Cảnh báo đã bật trên 10 thiết bị. Hãy gỡ bớt một thiết bị bên dưới trước.",
    "push.error.signed_out": "Hãy đăng nhập lại rồi thử lần nữa.",
    "push.error.rate_limited": "Gửi thử quá nhiều lần. Hãy thử lại sau một giờ.",
    "push.error.test_failed": "Gửi thử không thành công. Hãy tắt rồi bật lại cảnh báo.",
    "flash.push.device_removed": "Thiết bị đó sẽ không nhận cảnh báo nữa.",
    "flash.push.signed_out": "Hãy đăng nhập lại rồi thử lần nữa.",
```

Run: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_flash_literals.py -q --tb=short -x 2>&1 | tail -5`. Expected: all pass.

**Step 6.** Create `App/tests/test_push_routes.py` with exactly:

```python
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
```

Run: `cd App && .venv/bin/python -m pytest tests/test_push_routes.py -q --tb=short -x 2>&1 | tail -15`. Expected: all pass. Fix code once if needed (never weaken a test); a second failure: STOP.

## 5. Do not touch

Templates and static files (brief 0227 adds the Settings markup and `pwa.js`), `push.KINDS`, everything that calls `push.notify`. Hard rules: no new dependency; never log or audit an endpoint; no em dashes.

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_push_routes.py tests/test_push.py tests/test_passkeys.py tests/test_flash_literals.py tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x`
2. `.venv/bin/python -m pytest tests/test_security*.py tests/test_auth_*.py -q --tb=short -x`
3. From the repo root: `python3 scripts/context_lint.py`

## 7. Acceptance

- [ ] §6 commands pass.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0226-report.md` per TEMPLATE §9; set `Status: review`.

## Risk list (for the reviewer)

`App/app/routes/push.py` (account checks, rate limit), `App/app/routes/admin.py` (context).

## Owner steps

None.
