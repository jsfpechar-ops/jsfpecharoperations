"""Authentication, account security, and user administration routes."""
from __future__ import annotations

import base64
import io

import pyotp
import qrcode
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from .. import auth, config, db, rate_limit, security, turnstile
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = _form_str(form, "username")
    ip_key = rate_limit.client_key(request)
    client_key = rate_limit.client_key(request, username.lower() or "unknown")
    if not turnstile.verify(request, form.get("cf-turnstile-response"), "host_login"):
        return render(
            request,
            "login.html",
            {"error": "Security check failed. Please try again.", "username": username},
            status_code=403,
        )
    if rate_limit.login_blocked(client_key, ip_key):
        return render(
            request,
            "login.html",
            {
                "error": "Too many failed attempts. Wait about 15 minutes and try again.",
                "username": username,
            },
            status_code=429,
        )
    account = auth.authenticate(username, _form_str(form, "password"))
    if not account:
        rate_limit.record_login_failure(client_key, ip_key)
        db.audit("login_failed", request.client.host if request.client else "", actor="anonymous")
        return render(
            request,
            "login.html",
            {
                "error": "That username or password is not correct.",
                "username": username,
            },
            status_code=401,
        )
    target = "/account/password" if account["must_change_password"] else "/"
    next_path = security.safe_local_path(_form_str(form, "next"), "/")
    if not account["must_change_password"]:
        target = next_path
    remember = _form_str(form, "remember") in ("1", "on", "true", "yes")
    if account["totp_enabled"]:
        return render(
            request,
            "two_factor_login.html",
            {
                "pending": auth.issue_two_factor_pending(
                    account["id"], remember=remember, next_path=target
                )
            },
        )
    response = RedirectResponse(target, status_code=303)
    auth.attach_session(
        response,
        auth.issue_session(account["id"], account["session_version"], remember=remember),
        remember=remember,
    )
    db.audit(
        "login",
        detail=(
            f"terms_v{config.TERMS_VERSION} "
            f"privacy_v{config.PRIVACY_VERSION} "
            f"dpa_v{config.DPA_VERSION} accepted"
        ),
        actor=account["username"],
        owner_user_id=account["id"],
    )
    return response


@router.post("/login/2fa")
async def two_factor_login(request: Request):
    form = await request.form()
    pending = auth.read_two_factor_pending(_form_str(form, "pending"))
    if not pending:
        return RedirectResponse("/login", status_code=303)
    account = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1", (pending["uid"],)
    )
    if not account:
        return RedirectResponse("/login", status_code=303)
    client_key = rate_limit.client_key(request, f"{account['username']}:2fa")
    ip_key = rate_limit.client_key(request)
    if rate_limit.login_blocked(client_key, ip_key):
        return render(
            request,
            "two_factor_login.html",
            {"pending": _form_str(form, "pending"), "error": "Too many attempts. Wait about 15 minutes."},
            status_code=429,
        )
    if not auth.verify_second_factor(account, _form_str(form, "code")):
        rate_limit.record_login_failure(client_key, ip_key)
        db.audit("two_factor_failed", actor=account["username"], owner_user_id=account["id"])
        return render(
            request,
            "two_factor_login.html",
            {"pending": _form_str(form, "pending"), "error": "That code is not valid."},
            status_code=401,
        )
    response = RedirectResponse(
        security.safe_local_path(str(pending.get("next") or ""), "/"), status_code=303
    )
    auth.attach_session(
        response,
        auth.issue_session(
            account["id"], account["session_version"], remember=bool(pending.get("rm"))
        ),
        remember=bool(pending.get("rm")),
    )
    db.audit("two_factor_login", actor=account["username"], owner_user_id=account["id"])
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    auth.clear_session(response)
    return response


@router.get("/account/password")
def account_password_form(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return render(request, "account_password.html", {})


def _totp_qr_data(uri: str) -> str:
    image = qrcode.make(uri)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


@router.get("/account/2fa/setup")
def two_factor_setup_form(request: Request):
    account = auth.current_user(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    if account["totp_enabled"]:
        return _back("/settings", msg=_flash(request, "flash.accounts.twofa_enabled"))
    try:
        secret = db.decrypt_secret(account["totp_secret_enc"]) if account["totp_secret_enc"] else ""
    except Exception:
        secret = ""
    if not secret:
        secret = auth.new_totp_secret()
        auth.stage_totp(account["id"], secret)
    uri = auth.totp_uri(secret, account["username"])
    return render(
        request,
        "two_factor_setup.html",
        {"secret": secret, "qr_data": _totp_qr_data(uri)},
    )


@router.post("/account/2fa/setup")
async def two_factor_setup_submit(request: Request):
    account = auth.current_user(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    try:
        secret = db.decrypt_secret(account["totp_secret_enc"])
    except Exception:
        secret = ""
    if not secret or not pyotp.TOTP(secret).verify(_form_str(form, "code"), valid_window=1):
        uri = auth.totp_uri(secret, account["username"]) if secret else ""
        return render(
            request,
            "two_factor_setup.html",
            {"secret": secret, "qr_data": _totp_qr_data(uri) if uri else "", "error": "That code is not valid."},
            status_code=400,
        )
    recovery_codes = auth.new_recovery_codes()
    auth.enable_totp(account["id"], secret, recovery_codes)
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    response = render(request, "two_factor_recovery.html", {"recovery_codes": recovery_codes})
    auth.attach_session(response, auth.issue_session(refreshed["id"], refreshed["session_version"]))
    db.audit("two_factor_enabled", actor=account["username"], owner_user_id=account["id"])
    return response


@router.post("/account/password")
async def account_password_update(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    form = await request.form()
    if not auth.verify_password(_form_str(form, "current_password"), account["password_hash"]):
        return render(
            request, "account_password.html", {"error": "Current password is wrong."},
            status_code=400,
        )
    new_password = _form_str(form, "new_password")
    if new_password != _form_str(form, "confirm_password"):
        return render(
            request, "account_password.html", {"error": "The new passwords do not match."},
            status_code=400,
        )
    try:
        auth.set_account_password(account["id"], new_password)
    except ValueError as exc:
        return render(request, "account_password.html", {"error": str(exc)}, status_code=400)
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    if account["must_change_password"]:
        try:
            (config.DATA_DIR / "initial_admin_credentials").unlink(missing_ok=True)
        except OSError:
            pass
    response = _back("/", msg=_flash(request, "flash.accounts.password_changed"))
    auth.attach_session(response, auth.issue_session(refreshed["id"], refreshed["session_version"]))
    db.audit("password_changed", actor=account["username"], owner_user_id=account["id"])
    return response


def _require_admin(request: Request):
    guard = auth.require_login(request)
    if guard:
        return None, guard
    account = auth.current_user(request)
    if not account or account["role"] != "admin":
        return None, Response("Administrators only.", status_code=403)
    return account, None


@router.get("/admin/users")
def users_admin(request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    return _render_users(request)


def _render_users(request: Request, **extra):
    users = db.query(
        "SELECT u.id, u.username, u.display_name, u.role, u.active, "
        "u.must_change_password, u.created_at, u.last_login_at, "
        "(SELECT COUNT(*) FROM apartment a WHERE a.owner_user_id = u.id "
        "AND a.archived_at IS NULL) AS apartment_count FROM user_account u ORDER BY u.username"
    )
    return render(request, "users.html", {"users": users, **extra})


@router.post("/admin/users")
async def user_create(request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    password = _form_str(form, "password") or auth.generate_password()
    username = _form_str(form, "username")
    try:
        user_id = auth.create_account(
            username,
            password,
            _form_str(form, "display_name"),
            role="host",
            must_change_password=True,
        )
    except ValueError as exc:
        return _back("/admin/users", err=str(exc))
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return _back("/admin/users", err="That username is already in use.")
        raise
    db.audit(
        "user_created", f"user={user_id}", actor=account["username"], owner_user_id=user_id
    )
    return _render_users(
        request,
        new_credential={"username": username, "password": password},
    )


@router.post("/admin/users/{user_id}/password")
async def user_password_reset(user_id: int, request: Request):
    account, guard = _require_admin(request)
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if guard or not target:
        return guard or Response("Administrators only.", status_code=403)
    if user_id == account["id"]:
        return _back("/account/password", err="Change your own password from your account page.")
    form = await request.form()
    password = _form_str(form, "password") or auth.generate_password()
    try:
        auth.set_account_password(user_id, password, must_change=True)
        auth.reset_totp(user_id)
    except ValueError as exc:
        return _back("/admin/users", err=str(exc))
    db.audit("password_reset", actor=account["username"], owner_user_id=user_id)
    return _render_users(
        request,
        new_credential={"username": target["username"], "password": password, "reset": True},
    )


@router.post("/admin/users/{user_id}/impersonate")
def user_impersonate(user_id: int, request: Request):
    account, guard = _require_admin(request)
    target = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1", (user_id,)
    )
    if guard or not target:
        return guard or Response("Administrators only.", status_code=403)
    response = RedirectResponse("/", status_code=303)
    auth.attach_session(
        response,
        auth.issue_session(account["id"], account["session_version"], workspace_user_id=user_id),
    )
    db.audit(
        "impersonation_started",
        f"admin={account['username']}",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return response


@router.post("/admin/users/{user_id}/toggle")
def user_toggle(user_id: int, request: Request):
    account, guard = _require_admin(request)
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if guard or not target:
        return guard or Response("Administrators only.", status_code=403)
    if user_id == account["id"]:
        return _back("/admin/users", err="You cannot disable your own administrator account.")
    active = 0 if target["active"] else 1
    db.execute(
        "UPDATE user_account SET active = ?, session_version = session_version + 1 WHERE id = ?",
        (active, user_id),
    )
    db.audit(
        "user_enabled" if active else "user_disabled",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return _back(
        "/admin/users",
        msg=_flash(
            request,
            "flash.accounts.enabled" if active else "flash.accounts.disabled",
            username=target["username"],
        ),
    )


@router.post("/admin/stop-impersonating")
def stop_impersonating(request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    response = RedirectResponse("/admin/users", status_code=303)
    auth.attach_session(response, auth.issue_session(account["id"], account["session_version"]))
    db.audit("impersonation_stopped", actor=account["username"], owner_user_id=account["id"])
    return response
