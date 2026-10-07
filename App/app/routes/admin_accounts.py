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
from starlette.background import BackgroundTask, BackgroundTasks

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
    login_link,
    mail,
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


def _dev_link_visible() -> bool:
    """Show the login link on the page instead of only mailing it.

    Only on a local development run with the console mail backend, where no
    mail is delivered. Never on staging: that site is public, and a link on the
    page would let anyone who knows an address log in as that account. Staging
    writes link mails to its own (access-controlled) log instead.
    """
    return config.DEPLOYMENT == "local" and mail.backend_name() == "console"


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    raw_email = _form_str(form, "email")[:254]
    email = mail.normalise_email(raw_email)
    next_path = security.safe_local_path(_form_str(form, "next"), "/")
    # Every successful e-mail link login gets a persistent session; re-auth is
    # still one link away, and session_version invalidates stolen cookies.
    remember = True
    lang = host_i18n.resolve_language(request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE)

    def again(error: str, status_code: int):
        return render(
            request,
            "login.html",
            {"error": error, "email": raw_email, "next": next_path},
            status_code=status_code,
        )

    if not turnstile.verify(request, form.get("cf-turnstile-response"), "host_login"):
        return again("auth.error.turnstile", 403)
    if not email:
        return again("auth.error.email_invalid", 400)
    ip_key = rate_limit.client_key(request)
    if login_link.request_blocked(ip_key, email):
        return again("auth.error.link_rate_limited", 429)
    login_link.record_request(ip_key, email)
    background = BackgroundTasks()
    context = {"email": email, "remember": remember, "next": next_path}
    account = auth.account_by_email(email)
    if account:
        token = login_link.issue(
            account, purpose=login_link.LOGIN, remember=remember, next_path=next_path
        )
        outbox_id = mail_notify.link_mail(
            kind="login_link",
            user_id=account["id"],
            to_email=email,
            token=token,
            minutes=login_link.TTL_SECONDS[login_link.LOGIN] // 60,
            lang=lang,
        )
        background.add_task(mail.send_now, outbox_id)
        db.audit("login_link_sent", actor="anonymous", owner_user_id=account["id"])
        if _dev_link_visible():
            context["dev_link"] = f"/login/link?t={token}"
    # The same page whether or not the address has an account: the form must
    # not tell anyone who uses UbyHost.
    response = render(request, "login_sent.html", context)
    response.background = background
    return response


def _link_page(request: Request, context: dict, status_code: int = 200):
    """The page a link opens: never cached, and it sends no Referer onward."""
    response = render(request, "login_link.html", context, status_code=status_code)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/login/link")
def login_link_form(request: Request):
    """Show a "Log in" button. Opening the link spends nothing (mail scanners)."""
    token = request.query_params.get("t", "")
    row = login_link.peek(token)
    if not row or not login_link.account_for(row):
        return _link_page(request, {"expired": True}, status_code=410)
    return _link_page(request, {"token": token, "invite": row["purpose"] == login_link.INVITE})


def _finish_login(
    request: Request, account, *, remember: bool, next_path: str, method: str,
    action: str = "login",
):
    """Start the session once the login proved who this is."""
    response = RedirectResponse(security.safe_local_path(next_path, "/"), status_code=303)
    auth.attach_session(
        response,
        auth.issue_session(account["id"], account["session_version"], remember=remember),
        remember=remember,
    )
    _keep_login_language(request, response)
    db.execute("UPDATE user_account SET last_login_at = ? WHERE id = ?", (db.utcnow(), account["id"]))
    db.audit(action, f"method={method}", actor=account["username"], owner_user_id=account["id"])
    return response


@router.post("/login/link")
async def login_link_submit(request: Request):
    form = await request.form()
    token = _form_str(form, "t")
    ip_key = rate_limit.client_key(request)
    if login_link.consume_blocked(ip_key):
        return _link_page(request, {"expired": True, "locked": True}, status_code=429)
    row = login_link.consume(token)
    account = login_link.account_for(row)
    if not account:
        login_link.record_consume_failure(ip_key)
        return _link_page(request, {"expired": True}, status_code=410)
    if not account["email_verified_at"]:
        db.execute(
            "UPDATE user_account SET email_verified_at = ? WHERE id = ?",
            (db.utcnow(), account["id"]),
        )
    if account["role"] == "admin" and row["purpose"] == login_link.INVITE:
        # The bootstrap link has done its job; nothing on disk should still
        # hold a working one.
        try:
            (config.DATA_DIR / "initial_admin_login").unlink(missing_ok=True)
        except OSError:
            pass
    remember = bool(row["remember"])
    next_path = row["next_path"] or "/"
    if account["totp_enabled"]:
        response = render(
            request,
            "two_factor_login.html",
            {
                "pending": auth.issue_two_factor_pending(
                    account["id"], remember=remember, next_path=next_path
                )
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    return _finish_login(request, account, remember=remember, next_path=next_path, method="link")


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
    return _finish_login(
        request,
        account,
        remember=bool(pending.get("rm")),
        next_path=str(pending.get("next") or "/"),
        method="link+totp",
        action="two_factor_login",
    )


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
        return render(request, "two_factor_setup.html", context, status_code=400)
    recovery_codes = auth.new_recovery_codes()
    auth.enable_totp(account["id"], secret, recovery_codes)
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    context = {"recovery_codes": recovery_codes}
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
    """Re-enrol the authenticator app on a new phone.

    The old phone has to prove itself one last time with a code (or a
    recovery code). Setup then runs again and mints fresh recovery codes,
    because the old ones were written down beside the old device.
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
    if not auth.verify_second_factor(account, _form_str(form, "code")):
        rate_limit.record_account_2fa_failure(account["id"])
        db.audit("two_factor_move_failed", actor=account["username"], owner_user_id=account["id"])
        return _back("/settings", err=_flash(request, "auth.error.code_invalid"))
    auth.reset_totp(account["id"])
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    db.audit("two_factor_moved", actor=account["username"], owner_user_id=account["id"])
    response = RedirectResponse("/account/2fa/setup?moved=1", status_code=303)
    # reset_totp bumps session_version, so the cookie that sent this POST is stale.
    remember = auth.session_remembers(request)
    auth.attach_session(
        response,
        auth.issue_session(refreshed["id"], refreshed["session_version"], remember=remember),
        remember=remember,
    )
    return response


@router.post("/account/2fa/disable")
async def two_factor_disable(request: Request):
    """Switch the authenticator app off. A current code proves the phone is here."""
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    if not account["totp_enabled"]:
        return _back("/settings#settings-security")
    form = await request.form()
    if rate_limit.account_2fa_blocked(account["id"]):
        return _back("/settings#settings-security", err=_flash(request, "auth.error.code_locked"))
    if not auth.verify_second_factor(account, _form_str(form, "code")):
        rate_limit.record_account_2fa_failure(account["id"])
        db.audit("two_factor_disable_failed", actor=account["username"], owner_user_id=account["id"])
        return _back("/settings#settings-security", err=_flash(request, "auth.error.code_invalid"))
    auth.reset_totp(account["id"])
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    db.audit("two_factor_disabled", actor=account["username"], owner_user_id=account["id"])
    response = _back("/settings#settings-security", msg=_flash(request, "flash.accounts.twofa_disabled"))
    remember = auth.session_remembers(request)
    auth.attach_session(
        response,
        auth.issue_session(refreshed["id"], refreshed["session_version"], remember=remember),
        remember=remember,
    )
    return response


@router.post("/account/email")
async def account_email_request(request: Request):
    """Ask to log in with a new address: a link to that address confirms it."""
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    if auth.impersonating(request):
        return _back("/settings#settings-account", err=_flash(request, "auth.error.admins_only"))
    if not auth.session_is_fresh(request):
        return _back("/settings#settings-account", err=_flash(request, "auth.error.recent_login"))
    form = await request.form()
    email = mail.normalise_email(_form_str(form, "email"))
    if not email:
        return _back("/settings#settings-account", err=_flash(request, "users.email.error.invalid"))
    if email == (account["email"] or "").strip().lower():
        return _back("/settings#settings-account", msg=_flash(request, "users.email.unchanged"))
    ip_key = rate_limit.client_key(request)
    if login_link.request_blocked(ip_key, email):
        return _back("/settings#settings-account", err=_flash(request, "auth.error.link_rate_limited"))
    login_link.record_request(ip_key, email)
    # A taken address gets the same answer and no mail: the form must not tell
    # a host which addresses other accounts use.
    background = BackgroundTasks()
    if not auth.email_taken(email, except_user_id=account["id"]):
        token = login_link.issue(account, purpose=login_link.EMAIL_CHANGE, email=email)
        outbox_id = mail_notify.link_mail(
            kind="email_confirm",
            user_id=account["id"],
            to_email=email,
            token=token,
            minutes=login_link.TTL_SECONDS[login_link.EMAIL_CHANGE] // 60,
            lang=host_i18n.lang_from_request(request),
        )
        background.add_task(mail.send_now, outbox_id)
        db.audit("email_change_requested", f"to={mail.mask_email(email)}", owner_user_id=account["id"])
    response = _back(
        "/settings#settings-account",
        msg=_flash(request, "settings.account.email_sent", email=email),
    )
    response.background = background
    return response


def _email_confirm_page(request: Request, context: dict, status_code: int = 200):
    response = render(request, "account_email_confirm.html", context, status_code=status_code)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/account/email/confirm")
def account_email_confirm_form(request: Request):
    token = request.query_params.get("t", "")
    row = login_link.peek(token, (login_link.EMAIL_CHANGE,))
    if not row or not login_link.account_for(row):
        return _email_confirm_page(request, {"expired": True}, status_code=410)
    return _email_confirm_page(request, {"token": token, "email": row["email"]})


@router.post("/account/email/confirm")
async def account_email_confirm_submit(request: Request):
    form = await request.form()
    token = _form_str(form, "t")
    ip_key = rate_limit.client_key(request)
    if login_link.consume_blocked(ip_key):
        return _email_confirm_page(request, {"expired": True}, status_code=429)
    row = login_link.consume(token, (login_link.EMAIL_CHANGE,))
    account = login_link.account_for(row)
    if not account or auth.email_taken(row["email"], except_user_id=account["id"]):
        login_link.record_consume_failure(ip_key)
        return _email_confirm_page(request, {"expired": True}, status_code=410)
    old_email = (account["email"] or "").strip().lower()
    try:
        auth.set_account_email(account["id"], row["email"])
    except Exception as exc:
        if db.is_unique_violation(exc):
            return _email_confirm_page(request, {"expired": True}, status_code=410)
        raise
    # The new address just proved itself.
    db.execute(
        "UPDATE user_account SET email_verified_at = ? WHERE id = ?", (db.utcnow(), account["id"])
    )
    db.audit(
        "email_changed",
        f"from={mail.mask_email(old_email)} to={mail.mask_email(row['email'])} by=self",
        actor=account["username"],
        owner_user_id=account["id"],
    )
    mail_notify.email_changed(
        user_id=account["id"],
        old_email=old_email,
        new_email=row["email"],
        stamp=db.utcnow(),
        by="self",
        notify_new=False,
    )
    # Every session ended with the change; the host logs in again with the new
    # address.
    response = RedirectResponse("/login?notice=email_changed", status_code=303)
    auth.clear_session(response)
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
        "u.created_at, u.last_login_at, "
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
            "missing_email_count": sum(
                1 for user in users if user["active"] and not (user["email"] or "").strip()
            ),
            "signup_enabled": config.SIGNUP_ENABLED,
            "ads_export_days": signup.GOOGLE_EXPORT_DAYS,
            **extra,
        },
    )


def _send_invite(request: Request, target) -> None:
    """Mail ``target`` a link that logs them in, valid for three days."""
    token = login_link.issue(target, purpose=login_link.INVITE, remember=True)
    outbox_id = mail_notify.link_mail(
        kind="account_invite",
        user_id=target["id"],
        to_email=target["email"],
        token=token,
        minutes=login_link.TTL_SECONDS[login_link.INVITE] // 60,
    )
    mail.send_now(outbox_id)


@router.post("/admin/users")
async def user_create(request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    email = mail.normalise_email(_form_str(form, "email"))
    if not email:
        return _back("/admin/users", err=_flash(request, "users.email.error.invalid"))
    if auth.email_taken(email):
        return _back("/admin/users", err=_flash(request, "users.email.error.taken"))
    try:
        user_id = auth.create_account(email, _form_str(form, "display_name"), role="host")
    except ValueError as exc:
        # ``auth`` raises catalogue keys, so the message travels as a key and is
        # resolved in the language the host is reading the page in.
        return _back("/admin/users", err=_flash(request, str(exc)))
    except Exception as exc:
        if db.is_unique_violation(exc):
            return _back("/admin/users", err=_flash(request, "users.email.error.taken"))
        raise
    db.audit(
        "user_created", f"user={user_id}", actor=account["username"], owner_user_id=user_id
    )
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    _send_invite(request, target)
    return _back("/admin/users", msg=_flash(request, "users.invite.sent", email=email))


@router.post("/admin/users/{user_id}/invite")
def user_invite(user_id: int, request: Request):
    """Send a fresh invitation link, for a host who never used theirs."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    target = db.query_one("SELECT * FROM user_account WHERE id = ? AND active = 1", (user_id,))
    if not target or not (target["email"] or "").strip():
        return _back("/admin/users", err=_flash(request, "users.invite.no_email"))
    _send_invite(request, target)
    db.audit("invite_sent", actor=account["username"], owner_user_id=user_id)
    return _back("/admin/users", msg=_flash(request, "users.invite.sent", email=target["email"]))


@router.post("/admin/users/{user_id}/email")
async def user_email_set(user_id: int, request: Request):
    """Set or change the address an account logs in with (task 0002).

    Setting a first address needs no reason. Changing one does: it is the
    support step for a host who lost their mailbox, so the audit row says why,
    both addresses get a notice, and every session of the account ends.
    """
    account, guard = _require_admin(request)
    if guard:
        return guard
    target = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    if not target:
        return _back("/admin/users", err=_flash(request, "users.email.error.not_found"))
    form = await request.form()
    email = mail.normalise_email(_form_str(form, "email"))
    if not email:
        return _back("/admin/users", err=_flash(request, "users.email.error.invalid"))
    old_email = (target["email"] or "").strip().lower()
    if email == old_email:
        return _back("/admin/users", msg=_flash(request, "users.email.unchanged"))
    reason = ""
    if old_email:
        reason = auth.support_reason(_form_str(form, "reason")) or ""
        if not reason:
            return _back("/admin/users", err=_flash(request, "users.email.error.reason"))
    if auth.email_taken(email, except_user_id=user_id):
        return _back("/admin/users", err=_flash(request, "users.email.error.taken"))
    try:
        auth.set_account_email(user_id, email)
    except Exception as exc:
        if db.is_unique_violation(exc):
            return _back("/admin/users", err=_flash(request, "users.email.error.taken"))
        raise
    detail = f"to={mail.mask_email(email)}"
    if old_email:
        detail = f"from={mail.mask_email(old_email)} {detail} reason={reason}"
    db.audit(
        "email_changed" if old_email else "email_set",
        detail,
        actor=account["username"],
        owner_user_id=user_id,
    )
    if old_email:
        mail_notify.email_changed(
            user_id=user_id, old_email=old_email, new_email=email, stamp=db.utcnow()
        )
    response = _back("/admin/users", msg=_flash(request, "users.email.saved"))
    if old_email and user_id == account["id"]:
        # The change ended every session of this account, the admin's own
        # included; hand this browser a fresh one.
        refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        remember = auth.session_remembers(request)
        auth.attach_session(
            response,
            auth.issue_session(refreshed["id"], refreshed["session_version"], remember=remember),
            remember=remember,
        )
    return response


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
