"""Stripe Connect routes (brief 0426).

``POST /stripe/webhook`` is the one public Stripe-facing endpoint: Stripe
cannot send our CSRF token, so it takes no session; the raw-body signature
verification (``whsec``) is the authentication. It only exists while
``UBYHOST_STRIPE_MODE`` is test/live — otherwise the route 404s.

``POST /stripe/onboarding/start`` is host-authenticated and redirects to a
single-use Stripe-hosted onboarding link. Account-link URLs are never e-mailed
(Stripe's rule: they grant access to the holder's personal-information form).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .. import auth, config, security, stripe_connect

router = APIRouter()




@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not config.stripe_enabled():
        raise HTTPException(status_code=404)
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe_connect.verify_and_parse(payload, sig)
    except Exception:
        # Bad signature or malformed payload: refuse, let Stripe retry.
        return JSONResponse({"error": "invalid signature"}, status_code=400)
    stripe_connect.handle_event(event)
    # 2xx fast: heavy work must never slow the delivery response.
    return JSONResponse({"received": True})


host_router = APIRouter(dependencies=[Depends(security.protect_host_post)])


@host_router.post("/stripe/onboarding/start")
async def stripe_onboarding_start(request: Request):
    if not config.stripe_enabled():
        raise HTTPException(status_code=404)
    account = auth.current_user(request)
    if account is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    owner_user_id = int(account["id"])
    base = config.app_base_url().rstrip("/")
    try:
        url = stripe_connect.onboarding_link(
            owner_user_id,
            return_url=f"{base}/stripe/onboarding/return",
            refresh_url=f"{base}/stripe/onboarding/start",
        )
    except stripe_connect.StripeDisabledError:
        raise HTTPException(status_code=503)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url, status_code=303)


@host_router.get("/stripe/onboarding/return")
async def stripe_onboarding_return(request: Request):
    """Stripe lands the host here after the flow — it does NOT mean verified."""
    if not config.stripe_enabled():
        raise HTTPException(status_code=404)
    account = auth.current_user(request)
    if account is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    try:
        stripe_connect.sync_account(int(account["id"]))
    except (ValueError, stripe_connect.StripeDisabledError):
        pass
    return RedirectResponse("/dashboard", status_code=303)
