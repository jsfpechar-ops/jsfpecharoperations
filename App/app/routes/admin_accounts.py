"""Authentication, account security, and user administration routes."""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from starlette.background import BackgroundTask

from .. import (
    acceptance,
    access,
    admin_funnel,
    admin_ops,
    auth,
    config,
    db,
    host_i18n,
    incidents,
    lifecycle_mail,
    mail_notify,
    rate_limit,
    security,
    signup,
    turnstile,
    workspace_export,
)
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter()


def _keep_login_language(request: Request, response) -> None:
    """Carry the login page's language into the signed-in pages.

    Signed-out pages fall back to Czech and signed-in pages to English, so
    without this a host who never touched the switch reads Czech, logs in, and
    lands in English. A POST never renders, so the language is resolved here
    with the signed-out default the login page itself used.
    """
    chosen = host_i18n.supported_language(getattr(request.state, "lang", None))
    lang = chosen or host_i18n.resolve_language(
        request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE
    )
    if request.cookies.get(host_i18n.LANG_COOKIE) != lang:
        host_i18n.remember_language(response, lang)


@router.get("/login")
def login_form(request: Request):
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = _form_str(form, "username")
    # Read once, up front, so a failed attempt re-renders the form still holding
    # the deep link the host arrived with instead of dropping them on the dashboard.
    next_path = security.safe_local_path(_form_str(form, "next"), "/")
    ip_key = rate_limit.client_key(request)
    client_key = rate_limit.client_key(request, username.lower() or "unknown")
    if not turnstile.verify(request, form.get("cf-turnstile-response"), "host_login"):
        return render(
            request,
            "login.html",
            {"error": "auth.error.turnstile", "username": username, "next": next_path},
            status_code=403,
        )
    if rate_limit.login_blocked(client_key, ip_key):
        return render(
            request,
            "login.html",
            {
                "error": "auth.error.locked",
                "username": username,
                "next": next_path,
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
                "error": "auth.error.bad_credentials",
                "username": username,
                "next": next_path,
            },
            status_code=401,
        )
    target = "/account/password" if account["must_change_password"] else "/"
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
    _keep_login_language(request, response)
    # Acceptance is now its own audited event (BE-1); the login row no longer
    # carries the versions as free text.
    db.audit("login", actor=account["username"], owner_user_id=account["id"])
    return response


@router.get("/login/2fa")
def two_factor_login_get():
    """The 2FA page is a POST response. A stray GET must not show raw JSON."""
    return RedirectResponse("/login?notice=2fa_expired", status_code=303)


@router.post("/login/2fa")
async def two_factor_login(request: Request):
    form = await request.form()
    pending = auth.read_two_factor_pending(_form_str(form, "pending"))
    if not pending:
        # The pending token lives 10 minutes, which is shorter than the 15-minute
        # lockout the host was just told to wait out. Say so instead of dropping
        # them on a bare login form with no explanation.
        return RedirectResponse("/login?notice=2fa_expired", status_code=303)
    account = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1", (pending["uid"],)
    )
    if not account:
        return RedirectResponse("/login", status_code=303)
    client_key = rate_limit.client_key(request, f"{account['username']}:2fa")
    ip_key = rate_limit.client_key(request)
    if rate_limit.login_blocked(client_key, ip_key) or rate_limit.account_2fa_blocked(account["id"]):
        return render(
            request,
            "two_factor_login.html",
            {"pending": _form_str(form, "pending"), "error": "auth.error.code_locked"},
            status_code=429,
        )
    if not auth.verify_second_factor(account, _form_str(form, "code")):
        rate_limit.record_login_failure(client_key, ip_key)
        rate_limit.record_account_2fa_failure(account["id"])
        db.audit("two_factor_failed", actor=account["username"], owner_user_id=account["id"])
        return render(
            request,
            "two_factor_login.html",
            {"pending": _form_str(form, "pending"), "error": "auth.error.code_invalid"},
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
    _keep_login_language(request, response)
    db.audit("two_factor_login", actor=account["username"], owner_user_id=account["id"])
    return response


@router.post("/logout")
def logout(request: Request):
    # Cookies are signed, not stored, so clearing this browser's copy alone
    # would leave a copied cookie valid. Log out ends the account's sessions
    # everywhere (the real account, also when an admin is impersonating).
    account = auth.current_user(request)
    if account:
        auth.end_all_sessions(account["id"])
        db.audit("logout", actor=account["username"], owner_user_id=account["id"])
    response = RedirectResponse("/login?notice=logged_out", status_code=303)
    auth.clear_session(response)
    return response


@router.post("/account/onboarding-emails")
async def onboarding_emails_submit(request: Request):
    """The Settings toggle "Setup tips by e-mail" (WP12, legal position 2).

    Only the account holder changes it: an admin previewing a workspace does
    not choose for the host.
    """
    account = auth.current_user(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    workspace = auth.workspace_user(request)
    if account["role"] != "host" or (workspace and workspace["id"] != account["id"]):
        return _back("/settings#settings-account")
    form = await request.form()
    wanted = str(form.get("enabled", "")) == "1"
    if wanted:
        lifecycle_mail.resubscribe(int(account["id"]), actor=account["username"])
        key = "flash.accounts.onboarding_emails_on"
    else:
        lifecycle_mail.set_opt_out(int(account["id"]), True, actor=account["username"])
        key = "flash.accounts.onboarding_emails_off"
    return _back("/settings#settings-account", msg=_flash(request, key))


def _pending_doc_rows(docs) -> list:
    versions = acceptance.current_versions()
    return [
        {"key": doc, "version": versions[doc], "href": f"/{doc}"}
        for doc in docs
    ]


@router.get("/account/accept")
def account_accept_form(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    docs = acceptance.pending(account["id"])
    next_path = security.safe_local_path(request.query_params.get("next"), "/")
    if not docs:
        return RedirectResponse(next_path, status_code=303)
    return render(
        request,
        "account_accept.html",
        {"pending_docs": _pending_doc_rows(docs), "next": next_path},
    )


@router.post("/account/accept")
async def account_accept_submit(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    form = await request.form()
    next_path = security.safe_local_path(_form_str(form, "next"), "/")
    docs = acceptance.pending(account["id"])
    if not docs:
        return RedirectResponse(next_path, status_code=303)
    if _form_str(form, "accept") != "1":
        return render(
            request,
            "account_accept.html",
            {
                "pending_docs": _pending_doc_rows(docs),
                "next": next_path,
                "error": "auth.error.accept_required",
            },
            status_code=422,
        )
    acceptance.record(account["id"], docs, "clickwrap", request)
    return RedirectResponse(next_path, status_code=303)


@router.get("/account/password")
def account_password_form(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    return render(request, "account_password.html", _first_run_step(account, 1))


def _first_run_step(account: dict, step: int) -> dict:
    """Context for the forced first-run sequence: password → 2FA → recovery codes.

    In production 2FA is mandatory, so a host who has not switched it on yet is
    walked through all three screens with no way to skip. Only there do the
    screens number themselves; anywhere else the ledes read as plain sentences.
    Step 3 is the screen right after 2FA is switched on, so ``totp_enabled`` is
    already set by then.
    """
    if config.DEPLOYMENT != "production":
        return {}
    if step < 3 and account["totp_enabled"]:
        return {}
    return {"first_run_step": step}


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
    context = {"secret": secret, "qr_data": _totp_qr_data(uri), "totp_uri": uri}
    if request.query_params.get("moved") == "1":
        context["moved"] = True
    context.update(_first_run_step(account, 2))
    return render(request, "two_factor_setup.html", context)


@router.post("/account/2fa/setup")
async def two_factor_setup_submit(request: Request):
    account = auth.current_user(request)
    if not account:
        return RedirectResponse("/login", status_code=303)
    # A reload, or the browser's "resubmit form?", would otherwise mint a second
    # set of recovery codes and silently kill the ones already written down.
    if account["totp_enabled"]:
        return _back("/settings", msg=_flash(request, "flash.accounts.twofa_enabled"))
    remember = auth.session_remembers(request)
    form = await request.form()
    # Authenticator apps show the code as "123 456", so a pasted one arrives
    # with a space in it; the login route strips spaces the same way.
    code = _form_str(form, "code").replace(" ", "")
    try:
        secret = db.decrypt_secret(account["totp_secret_enc"])
    except Exception:
        secret = ""
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        uri = auth.totp_uri(secret, account["username"]) if secret else ""
        context = {
            "secret": secret,
            "qr_data": _totp_qr_data(uri) if uri else "",
            "totp_uri": uri,
            "error": "auth.error.setup_code_invalid",
        }
        context.update(_first_run_step(account, 2))
        return render(request, "two_factor_setup.html", context, status_code=400)
    recovery_codes = auth.new_recovery_codes()
    auth.enable_totp(account["id"], secret, recovery_codes)
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    context = {"recovery_codes": recovery_codes}
    context.update(_first_run_step(refreshed, 3))
    response = render(request, "two_factor_recovery.html", context)
    auth.attach_session(
        response,
        auth.issue_session(refreshed["id"], refreshed["session_version"], remember=remember),
        remember=remember,
    )
    db.audit("two_factor_enabled", actor=account["username"], owner_user_id=account["id"])
    return response


@router.post("/account/2fa/move")
async def two_factor_move(request: Request):
    """Re-enrol the second factor on a new phone.

    The old phone is gone or going, so both factors have to prove themselves one
    last time: the password and a code the old device can still produce. Setup
    then runs again and mints fresh recovery codes, because the old ones were
    written down beside the old device.
    """
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    if not account["totp_enabled"]:
        return _back("/account/2fa/setup")
    form = await request.form()
    if rate_limit.account_2fa_blocked(account["id"]):
        return _back("/settings", err=_flash(request, "auth.error.code_locked"))
    if not auth.verify_password(_form_str(form, "current_password"), account["password_hash"]):
        rate_limit.record_account_2fa_failure(account["id"])
        db.audit("two_factor_move_failed", actor=account["username"], owner_user_id=account["id"])
        return _back("/settings", err=_flash(request, "auth.error.current_password_wrong"))
    if not auth.verify_second_factor(account, _form_str(form, "code")):
        rate_limit.record_account_2fa_failure(account["id"])
        db.audit("two_factor_move_failed", actor=account["username"], owner_user_id=account["id"])
        return _back("/settings", err=_flash(request, "auth.error.code_invalid"))
    auth.reset_totp(account["id"])
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    db.audit("two_factor_moved", actor=account["username"], owner_user_id=account["id"])
    response = RedirectResponse("/account/2fa/setup?moved=1", status_code=303)
    # reset_totp bumps session_version, so the cookie that sent this POST is stale.
    auth.attach_session(response, auth.issue_session(refreshed["id"], refreshed["session_version"]))
    return response


def _password_error(key: str) -> dict:
    """A password error together with the field it belongs under.

    The message used to sit in one alert above the form, with nothing tying it
    to the input that caused it, so a screen reader read three identical-looking
    fields and no clue which one to fix.
    """
    if key in ("auth.error.temp_password_wrong", "auth.error.current_password_wrong"):
        field = "current_password"
    elif key == "auth.error.passwords_mismatch":
        field = "confirm_password"
    else:
        field = "new_password"
    return {"error": key, "error_field": field}


@router.post("/account/password")
async def account_password_update(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    form = await request.form()
    if not auth.verify_password(_form_str(form, "current_password"), account["password_hash"]):
        key = (
            "auth.error.temp_password_wrong"
            if account["must_change_password"]
            else "auth.error.current_password_wrong"
        )
        return render(request, "account_password.html", _password_error(key), status_code=400)
    new_password = _form_str(form, "new_password")
    if new_password != _form_str(form, "confirm_password"):
        return render(
            request,
            "account_password.html",
            _password_error("auth.error.passwords_mismatch"),
            status_code=400,
        )
    try:
        auth.set_account_password(account["id"], new_password)
    except ValueError as exc:
        return render(request, "account_password.html", _password_error(str(exc)), status_code=400)
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    if account["must_change_password"]:
        try:
            (config.DATA_DIR / "initial_admin_credentials").unlink(missing_ok=True)
        except OSError:
            pass
    # The forced first-login branch carries on to 2FA setup; the in-app change
    # came from Settings, so it goes back there.
    target = "/" if account["must_change_password"] else "/settings#settings-account"
    remember = auth.session_remembers(request)
    response = _back(target, msg=_flash(request, "flash.accounts.password_changed"))
    auth.attach_session(
        response,
        auth.issue_session(refreshed["id"], refreshed["session_version"], remember=remember),
        remember=remember,
    )
    db.audit("password_changed", actor=account["username"], owner_user_id=account["id"])
    return response


def _require_admin(request: Request):
    guard = auth.require_login(request)
    if guard:
        return None, guard
    account = auth.current_user(request)
    if not account or account["role"] != "admin":
        return None, Response(_flash(request, "auth.error.admins_only"), status_code=403)
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
        "u.email, u.email_verified_at, u.signup_at, u.signup_source, "
        "(SELECT COUNT(*) FROM ad_click c WHERE c.user_account_id = u.id "
        "AND c.platform = 'google' AND c.withdrawn_at IS NULL) AS google_consent, "
        "(SELECT COUNT(*) FROM ad_click c WHERE c.user_account_id = u.id "
        "AND c.platform = 'meta' AND c.withdrawn_at IS NULL) AS meta_consent, "
        "(SELECT COUNT(*) FROM apartment a WHERE a.owner_user_id = u.id "
        "AND a.archived_at IS NULL) AS apartment_count FROM user_account u ORDER BY u.username"
    )
    return render(
        request,
        "users.html",
        {
            "users": users,
            "signup_enabled": config.SIGNUP_ENABLED,
            "ads_export_days": signup.GOOGLE_EXPORT_DAYS,
            **extra,
        },
    )


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
        # ``auth`` raises catalogue keys, so the message travels as a key and is
        # resolved in the language the host is reading the page in.
        return _back("/admin/users", err=_flash(request, str(exc)))
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return _back("/admin/users", err=_flash(request, "auth.error.username_taken"))
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
        return guard or Response(_flash(request, "auth.error.admins_only"), status_code=403)
    if user_id == account["id"]:
        return _back("/account/password", err=_flash(request, "auth.error.own_password"))
    form = await request.form()
    password = _form_str(form, "password") or auth.generate_password()
    try:
        auth.set_account_password(user_id, password, must_change=True)
        auth.reset_totp(user_id)
    except ValueError as exc:
        return _back("/admin/users", err=_flash(request, str(exc)))
    db.audit("password_reset", actor=account["username"], owner_user_id=user_id)
    return _render_users(
        request,
        new_credential={"username": target["username"], "password": password, "reset": True},
    )


@router.post("/admin/users/{user_id}/impersonate")
async def user_impersonate(user_id: int, request: Request):
    account, guard = _require_admin(request)
    target = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1", (user_id,)
    )
    if guard or not target:
        return guard or Response(_flash(request, "auth.error.admins_only"), status_code=403)
    form = await request.form()
    reason = auth.impersonation_audit_reason(_form_str(form, "reason"))
    response = RedirectResponse("/", status_code=303)
    auth.attach_session(
        response,
        auth.issue_session(account["id"], account["session_version"], workspace_user_id=user_id),
    )
    db.audit(
        "impersonation_started",
        f"admin={account['username']} reason={reason}",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return response


@router.post("/admin/users/{user_id}/toggle")
def user_toggle(user_id: int, request: Request):
    account, guard = _require_admin(request)
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if guard or not target:
        return guard or Response(_flash(request, "auth.error.admins_only"), status_code=403)
    if user_id == account["id"]:
        return _back("/admin/users", err=_flash(request, "auth.error.own_disable"))
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
    workspace = auth.workspace_user(request)
    response = RedirectResponse("/admin/users", status_code=303)
    auth.attach_session(response, auth.issue_session(account["id"], account["session_version"]))
    # The host sees the end of a support session in their own Settings audit,
    # not only the start; the admin's own workspace keeps its copy too.
    owners = [account["id"]]
    if workspace and workspace["id"] != account["id"]:
        owners.insert(0, workspace["id"])
    for owner_id in owners:
        db.audit(
            "impersonation_stopped",
            "exit",
            actor=account["username"],
            owner_user_id=owner_id,
        )
    return response


@router.get("/admin/incidents")
def incidents_admin(request: Request):
    """The platform-admin security incident register (BE-13)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    rows = [
        {"incident": incident, "draft": incidents.controller_notification_draft(incident)}
        for incident in incidents.list_all()
    ]
    return render(
        request,
        "admin_incidents.html",
        {
            "rows": rows,
            "review_alerts": incidents.open_review_alerts(),
            "owners": db.query(
                "SELECT id, username FROM user_account ORDER BY username"
            ),
        },
    )


@router.get("/admin/operations")
def operations_admin(request: Request):
    """Read-only cross-workspace health: filings, calendars, jobs, mail (WP10).

    No guest field is read, so nothing on the page identifies a guest.
    """
    account, guard = _require_admin(request)
    if guard:
        return guard
    return render(request, "admin_operations.html", {"ops": admin_ops.overview()})


@router.get("/admin/funnel")
def funnel_admin(request: Request):
    """One row per host account: how far each got, from existing rows (WP11)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    return render(request, "admin_funnel.html", {"funnel": admin_funnel.rows()})


@router.get("/admin/funnel.csv")
def funnel_admin_csv(request: Request):
    """The funnel table as CSV, for pasting into a CRM. Host accounts only."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    data = admin_funnel.rows()
    db.audit("export_funnel_csv", f"rows={len(data['rows'])}", actor=account["username"])
    stamp = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        admin_funnel.iter_csv(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="funnel-{stamp}.csv"'},
    )


@router.post("/admin/incidents")
async def incident_create(request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    summary = _form_str(form, "summary").strip()
    if not summary:
        return _back("/admin/incidents", err=_flash(request, "flash.error.incident_summary"))
    approx = _form_str(form, "approx_subjects").strip()
    incident_id = incidents.create(
        detected_at=_form_str(form, "detected_at") or db.utcnow(),
        summary=summary,
        reported_by=_form_str(form, "reported_by"),
        data_categories=_form_str(form, "data_categories"),
        owner_ids=[int(value) for value in form.getlist("owner_ids") if str(value).isdigit()],
        approx_subjects=int(approx) if approx.isdigit() else None,
        risk_level=_form_str(form, "risk_level"),
        notes=_form_str(form, "notes"),
    )
    db.audit("incident_created", f"incident={incident_id}", actor=account["username"])
    return _back("/admin/incidents", msg=_flash(request, "flash.incidents.created"))


@router.post("/admin/incidents/{incident_id}")
async def incident_update(incident_id: int, request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    if not incidents.get(incident_id):
        return _back("/admin/incidents", err=_flash(request, "flash.error.no_such_incident"))
    form = await request.form()
    action = _form_str(form, "action")
    if action in incidents.TIMESTAMP_FIELDS:
        incidents.mark_timestamp(incident_id, action)
    values = {}
    for field in ("summary", "data_categories", "risk_level", "notes"):
        if field in form:
            values[field] = _form_str(form, field)
    if "approx_subjects" in form:
        raw = _form_str(form, "approx_subjects").strip()
        values["approx_subjects"] = int(raw) if raw.isdigit() else None
    if values:
        incidents.update(incident_id, values)
    db.audit("incident_updated", f"incident={incident_id}", actor=account["username"])
    return _back("/admin/incidents", msg=_flash(request, "flash.incidents.saved"))


# G-D11: return a ZIP on request and delete 30 days after termination, once the
# host confirms they hold their six-year copy. Counsel must confirm the timing.
WORKSPACE_DELETION_DAYS = 30


@router.post("/admin/users/{user_id}/export")
def user_workspace_export(user_id: int, request: Request):
    """Stream a ZIP of the workspace, then delete the temp file (BE-10)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if not target:
        return _back("/admin/users", err=_flash(request, "flash.error.no_such_user"))
    if not access.identity_visible(request):
        # Inside a host's workspace the ZIP is as blocked here as in Settings.
        return _back("/", err=_flash(request, "flash.error.identity_hidden_export"))
    path = workspace_export.build_workspace_zip(user_id)
    db.audit(
        "workspace_exported",
        f"user={user_id}",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"workspace-{user_id}.zip",
        background=BackgroundTask(os.unlink, path),
    )


@router.post("/admin/users/{user_id}/schedule-deletion")
async def user_schedule_deletion(user_id: int, request: Request):
    """Disable the account and set the deletion date (BE-10, G-D11)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if not target:
        return _back("/admin/users", err=_flash(request, "flash.error.no_such_user"))
    form = await request.form()
    if _form_str(form, "confirm") != target["username"]:
        return _back("/admin/users", err=_flash(request, "flash.error.confirm_username"))
    due = (
        datetime.now(timezone.utc) + timedelta(days=WORKSPACE_DELETION_DAYS)
    ).replace(microsecond=0).isoformat()
    db.update("user_account", user_id, {"deletion_due_at": due})
    mail_notify.workspace_deletion(user_id, due, "scheduled")
    db.audit(
        "workspace_deletion_scheduled",
        f"user={user_id} due={due}",
        actor=account["username"],
        owner_user_id=user_id,
    )
    return _back(
        "/admin/users",
        msg=_flash(request, "flash.users.deletion_scheduled", date=due),
    )
