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
