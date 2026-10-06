"""Passkey routes (task 0004): add, rename and remove a passkey, and log in.

The two ceremonies (add, log in) need the browser's WebAuthn API, so they are
JSON endpoints called by ``static/passkeys.js`` with the CSRF token in the
``X-CSRF-Token`` header. Everything else is a plain form that works without
JavaScript. The e-mail link stays the way in that never needs any of this.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .. import auth, db, host_i18n, mail, mail_notify, passkeys, rate_limit, security
from .admin_accounts import _finish_login
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter()

_SECURITY = "/settings#settings-security"
# A WebAuthn answer is a few kilobytes; anything far bigger is not one.
_MAX_BODY = 64 * 1024


def _text(request: Request, key: str, **params) -> str:
    return host_i18n.translate(host_i18n.lang_from_request(request), key, **params)


def _error(request: Request, key: str, status_code: int) -> JSONResponse:
    response = JSONResponse({"error": _text(request, key)}, status_code=status_code)
    response.headers["Cache-Control"] = "no-store"
    return response


def _json(payload: str) -> JSONResponse:
    response = JSONResponse(json.loads(payload))
    response.headers["Cache-Control"] = "no-store"
    return response


async def _body(request: Request) -> dict:
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        return {}
    try:
        data = json.loads(raw or b"{}")
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _owner(request: Request):
    """The signed-in account managing its own passkeys, never a previewed one.

    An admin previewing a host's workspace must not add a way into that
    host's account, so these routes always act on the real account.
    """
    account = auth.current_user(request)
    if not account:
        return None
    return db.query_one("SELECT * FROM user_account WHERE id = ? AND active = 1", (account["id"],))


_DEVICES = (
    (r"iPhone", "iPhone"),
    (r"iPad", "iPad"),
    (r"Android", "Android"),
    (r"Macintosh|Mac OS X", "Mac"),
    (r"Windows", "Windows"),
    (r"CrOS", "Chromebook"),
    (r"Linux", "Linux"),
)


def device_label(user_agent: str, lang: str) -> str:
    """A first name for a new passkey from the browser that made it ("iPhone").

    Only a coarse device family, never the full User-Agent string, is kept.
    The host can rename it.
    """
    for pattern, label in _DEVICES:
        if re.search(pattern, user_agent or ""):
            return label
    return host_i18n.translate(lang, "passkeys.default_name")


# --- adding, renaming, removing ----------------------------------------------


@router.post("/account/passkeys/options")
async def passkey_register_options(request: Request):
    account = _owner(request)
    if not account:
        return _error(request, "passkeys.error.signed_out", 401)
    if not passkeys.available():
        return _error(request, "passkeys.error.unavailable", 409)
    if not auth.session_is_fresh(request):
        return _error(request, "auth.error.recent_login", 403)
    if passkeys.count_for(account["id"]) >= passkeys.MAX_PER_ACCOUNT:
        return _error(request, "passkeys.error.too_many", 409)
    ip_key = rate_limit.client_key(request)
    if passkeys.options_blocked(ip_key):
        return _error(request, "passkeys.error.rate_limited", 429)
    passkeys.record_options(ip_key)
    return _json(passkeys.registration_options(account))


@router.post("/account/passkeys")
async def passkey_register(request: Request, background: BackgroundTasks):
    account = _owner(request)
    if not account:
        return _error(request, "passkeys.error.signed_out", 401)
    if not auth.session_is_fresh(request):
        return _error(request, "auth.error.recent_login", 403)
    data = await _body(request)
    credential = data.get("credential")
    if not isinstance(credential, dict):
        return _error(request, "passkeys.error.failed", 400)
    lang = host_i18n.lang_from_request(request)
    name = passkeys.clean_name(
        data.get("name") or "", device_label(request.headers.get("user-agent", ""), lang)
    )
    try:
        passkey_id = passkeys.register(account, credential, name)
    except passkeys.PasskeyError as exc:
        db.audit(
            "passkey_add_failed", f"reason={exc.reason}",
            actor=account["username"], owner_user_id=account["id"],
        )
        key = "passkeys.error.too_many" if exc.reason == "too_many" else "passkeys.error.failed"
        return _error(request, key, 400)
    # A second way in counts as "secured": the one-time prompt is done.
    db.execute(
        "UPDATE user_account SET two_factor_prompted_at = ? WHERE id = ? "
        "AND two_factor_prompted_at IS NULL",
        (db.utcnow(), account["id"]),
    )
    db.audit("passkey_added", f"passkey={passkey_id}", actor=account["username"],
             owner_user_id=account["id"])
    outbox_id = mail_notify.passkey_added(
        user_id=account["id"], to_email=account["email"], passkey_id=passkey_id, name=name
    )
    if outbox_id:
        background.add_task(mail.send_now, outbox_id)
    target = _back(_SECURITY, msg=_flash(request, "flash.passkeys.added"))
    response = JSONResponse({"redirect": target.headers["location"]})
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/account/passkeys/{passkey_id}/rename")
async def passkey_rename(request: Request, passkey_id: int):
    account = _owner(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    name = passkeys.clean_name(_form_str(form, "name"), "")
    if not name or not passkeys.rename(account["id"], passkey_id, name):
        return _back(_SECURITY, err=_flash(request, "flash.passkeys.not_found"))
    db.audit("passkey_renamed", f"passkey={passkey_id}", actor=account["username"],
             owner_user_id=account["id"])
    return _back(_SECURITY, msg=_flash(request, "flash.passkeys.renamed"))


@router.post("/account/passkeys/{passkey_id}/delete")
async def passkey_delete(request: Request, passkey_id: int):
    account = _owner(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    if not auth.session_is_fresh(request):
        return _back(_SECURITY, err=_flash(request, "auth.error.recent_login"))
    if passkeys.remove(account["id"], passkey_id) is None:
        return _back(_SECURITY, err=_flash(request, "flash.passkeys.not_found"))
    db.audit("passkey_removed", f"passkey={passkey_id}", actor=account["username"],
             owner_user_id=account["id"])
    return _back(_SECURITY, msg=_flash(request, "flash.passkeys.removed"))


# --- logging in --------------------------------------------------------------


@router.post("/login/passkey/options")
async def passkey_login_options(request: Request):
    if not passkeys.available():
        return _error(request, "passkeys.error.unavailable", 409)
    ip_key = rate_limit.client_key(request)
    if passkeys.options_blocked(ip_key) or passkeys.failures_blocked(ip_key):
        return _error(request, "passkeys.error.rate_limited", 429)
    passkeys.record_options(ip_key)
    return _json(passkeys.authentication_options())


@router.post("/login/passkey")
async def passkey_login(request: Request):
    ip_key = rate_limit.client_key(request)
    if passkeys.failures_blocked(ip_key):
        return _error(request, "passkeys.error.rate_limited", 429)
    data = await _body(request)
    credential = data.get("credential")
    if not isinstance(credential, dict):
        passkeys.record_failure(ip_key)
        return _error(request, "passkeys.error.login_failed", 400)
    try:
        account, row = passkeys.authenticate(credential)
    except passkeys.PasskeyError as exc:
        passkeys.record_failure(ip_key)
        if exc.reason == "sign_count":
            # Probably a cloned authenticator: tell the owner's audit log.
            owner = db.query_one(
                "SELECT p.id, u.id AS uid, u.username FROM passkey p "
                "JOIN user_account u ON u.id = p.user_account_id WHERE p.credential_id = ?",
                (passkeys.normalise_credential_id(credential.get("rawId")),),
            )
            if owner:
                db.audit("passkey_clone_suspected", f"passkey={owner['id']}",
                         actor=owner["username"], owner_user_id=owner["uid"])
        else:
            db.audit("passkey_login_failed", f"reason={exc.reason}", actor="anonymous")
        return _error(request, "passkeys.error.login_failed", 401)
    next_path = security.safe_local_path(str(data.get("next") or ""), "/")
    redirect = _finish_login(
        request,
        account,
        remember=bool(data.get("remember")),
        next_path=next_path,
        method=f"passkey:{row['id']}",
    )
    response = JSONResponse({"redirect": redirect.headers["location"]})
    response.headers["Cache-Control"] = "no-store"
    for name, value in redirect.raw_headers:
        if name.lower() == b"set-cookie":
            response.raw_headers.append((name, value))
    return response
