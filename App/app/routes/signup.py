"""Self sign-up pages and the admin side of the Google Ads import (WP20).

Every route here answers 404 while ``UBYHOST_SIGNUP_ENABLED`` is off. The
module is included from ``admin.router``, so the host POST CSRF protection
applies to the forms here as well.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from .. import access, auth, db, host_i18n, mail, rate_limit, signup, turnstile
from ..templating import render
from .admin_accounts import _keep_login_language, _require_admin
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter()


def _require_enabled() -> None:
    if not signup.enabled():
        raise HTTPException(status_code=404)


def _form_context(request: Request, attr: dict, consents=None, **extra) -> dict:
    lang = host_i18n.resolve_language(request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE)
    href = signup.signup_href(lang, attr)
    consents = consents or {}
    # One optional box per ad platform the visitor's click came from, and none
    # at all without a click: there is nothing to consent to.
    boxes = [
        {
            "platform": platform,
            "field": signup.CONSENT_FIELDS[platform],
            "checked": bool(consents.get(platform)),
            **signup.consent_label(platform, lang),
        }
        for platform in signup.click_platforms(signup.read_click(attr.get("click")))
    ]
    return {
        "attr": attr,
        "consent_boxes": boxes,
        # The language switch posts back to this address, so the click value
        # and the campaign labels survive a change of language.
        "lang_next": href,
        **extra,
    }


@router.get("/signup")
def signup_form(request: Request):
    _require_enabled()
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    attr = signup.attribution(request.query_params, mint=True)
    return render(request, "signup.html", _form_context(request, attr))


@router.post("/signup")
async def signup_submit(request: Request):
    _require_enabled()
    form = await request.form()
    attr = signup.attribution(form)
    email = mail.normalise_email(_form_str(form, "email"))
    raw_email = _form_str(form, "email")[:254]
    workspace = " ".join(_form_str(form, "workspace").split())
    password = _form_str(form, "password")
    click = signup.read_click(attr.get("click"))
    consents = {
        platform: _form_str(form, signup.CONSENT_FIELDS[platform]) == "1"
        for platform in signup.click_platforms(click)
    }
    onboarding_opt_out = _form_str(form, "onboarding_opt_out") == "1"
    lang = host_i18n.resolve_language(request, default=host_i18n.PUBLIC_DEFAULT_LANGUAGE)

    def again(error: str, status_code: int, field: str = ""):
        return render(
            request,
            "signup.html",
            _form_context(
                request,
                attr,
                consents,
                error=error,
                error_field=field,
                email=raw_email,
                workspace=workspace,
                onboarding_opt_out=onboarding_opt_out,
            ),
            status_code=status_code,
        )

    if not turnstile.verify(request, form.get("cf-turnstile-response"), "host_signup"):
        return again("signup.error.turnstile", 403)
    ip_key = rate_limit.client_key(request)
    if signup.rate_limited(ip_key, email):
        return again("signup.error.rate_limited", 429)
    signup.record_attempt(ip_key, email)
    if not email:
        return again("signup.error.email", 400, "email")
    password_error = auth.password_error(password)
    if password_error:
        return again(password_error, 400, "password")
    if not workspace or len(workspace) > signup.WORKSPACE_MAX:
        return again("signup.error.workspace", 400, "workspace")
    if _form_str(form, "accept") != "1":
        return again("signup.error.accept", 422, "accept")
    signup.register(
        email=email,
        password=password,
        workspace=workspace,
        attr=attr,
        consents=consents,
        onboarding_opt_out=onboarding_opt_out,
        lang=lang,
        request=request,
    )
    # The same page whatever ``register`` found: no account enumeration.
    return render(request, "signup_sent.html", {"email": email})


@router.get("/signup/verify")
def signup_verify_form(request: Request):
    _require_enabled()
    token = request.query_params.get("t", "")
    account = signup.pending_account(token)
    if not account:
        return render(request, "signup_verify.html", {"expired": True}, status_code=410)
    return render(request, "signup_verify.html", {"token": token})


@router.post("/signup/verify")
async def signup_verify_submit(request: Request):
    _require_enabled()
    form = await request.form()
    token = _form_str(form, "t")
    ip_key = rate_limit.client_key(request)
    client_key = rate_limit.client_key(request, "signup_verify")
    if rate_limit.login_blocked(client_key, ip_key):
        return render(
            request,
            "signup_verify.html",
            {"token": token, "error": "signup.verify.locked"},
            status_code=429,
        )
    account = signup.pending_account(token)
    if not account:
        return render(request, "signup_verify.html", {"expired": True}, status_code=410)
    if not auth.verify_password(_form_str(form, "password"), account["password_hash"]):
        rate_limit.record_login_failure(client_key, ip_key)
        return render(
            request,
            "signup_verify.html",
            {"token": token, "error": "signup.verify.error.password"},
            status_code=401,
        )
    if not signup.activate(account):
        return render(request, "signup_verify.html", {"expired": True}, status_code=410)
    refreshed = db.query_one("SELECT * FROM user_account WHERE id = ?", (account["id"],))
    response = RedirectResponse("/", status_code=303)
    auth.attach_session(
        response, auth.issue_session(refreshed["id"], refreshed["session_version"])
    )
    _keep_login_language(request, response)
    db.audit("login", actor=refreshed["username"], owner_user_id=refreshed["id"])
    return response


@router.post("/admin/ads-conversions.csv")
async def ads_conversions_csv(request: Request):
    """The Google Ads click-conversion file. A POST, because it marks rows exported."""
    _require_enabled()
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    again = _form_str(form, "again") == "1"
    body, count = signup.export_conversions(again=again)
    db.audit(
        "ads_conversions_exported",
        detail=f"rows={count}; again={'yes' if again else 'no'}",
        actor=account["username"],
    )
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="ubyhost-ads-conversions.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/admin/users/{user_id}/ads-consent/withdraw")
async def ads_consent_withdraw(user_id: int, request: Request):
    """An admin withdraws consent for a host who asked by e-mail."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    platform = _form_str(form, "platform", signup.GOOGLE)
    if platform not in signup.PLATFORMS:
        raise HTTPException(status_code=400)
    signup.withdraw_consent(user_id, platform, actor=account["username"])
    return _back("/admin/users", msg=_flash(request, f"flash.signup.consent_withdrawn.{platform}"))


@router.post("/settings/privacy/ad-consent")
async def ad_consent_settings(request: Request):
    """Settings > Privacy: the host turns an ad measurement consent off.

    Works whether or not sign-up is switched on: a consent given while it was
    on must stay withdrawable. Turning it back on is not offered, because the
    identifier is deleted the moment it is turned off.
    """
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    platform = _form_str(form, "platform")
    if platform not in signup.PLATFORMS:
        raise HTTPException(status_code=400)
    owner_id = access.owner_id(request)
    if owner_id is not None and _form_str(form, "enabled") != "1":
        account = auth.current_user(request)
        if signup.withdraw_consent(owner_id, platform, actor=account["username"]):
            return _back(
                "/settings#settings-privacy",
                msg=_flash(request, f"flash.signup.consent_withdrawn.{platform}"),
            )
    return _back("/settings#settings-privacy")
