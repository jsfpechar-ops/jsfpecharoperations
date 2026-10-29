"""Stripe Connect onboarding routes and the webhook endpoint (brief 0428).

The onboarding link is only ever served inside the authenticated dashboard
(redirect from a signed-in session; it is never emailed). Hosts visit
Stripe's hosted form exactly once; returning does not mean verified — the
account is re-retrieved and its requirements mirrored, and the dashboard
shows the state from the mirror, not from Stripe.

The webhook is public on purpose: it carries no session, and its only
credential is the Stripe-Signature header verified against the whsec secret
over the raw body. It is rate-limited like every public POST and always
answers 2xx fast when the event is valid or already seen, so Stripe stops
retrying; a bad signature is 400 and a missing secret in test/live mode is a
loud 500 (ENVIRONMENT.md "Connect payments").
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from .. import auth, config, rate_limit, security, stripe_connect

log = logging.getLogger("ubyhost.stripe")

router = APIRouter()

# Stripe retries for days; a generous public limit only blunts abuse.
_WEBHOOK_LIMIT = 600
_WEBHOOK_WINDOW = 3600


def _off() -> bool:
    return config.STRIPE_MODE not in ("test", "live")


async def _signed_in(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    return None


def _workspace(request: Request):
    """The workspace owner (None while an admin previews: connect acts on the
    host's own account, never on the admin's)."""
    workspace = auth.workspace_user(request)
    return int(workspace["id"]) if workspace else None


@router.get("/payments/connect/start")
async def connect_start(request: Request):
    """The refresh target: regenerate a single-use link and redirect to it."""
    guard = await _signed_in(request)
    if guard:
        return guard
    if _off():
        return Response(status_code=404)
    owner_id = _workspace(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    try:
        # Deterministic https base (config.app_base_url(): the env-configured
        # public URL). request.base_url behind the TLS-terminating proxy is
        # http:// — and an http refresh/return URL drops the host's Secure
        # session cookie on the bounce, landing them on the login page (0440).
        url = stripe_connect.onboarding_link(owner_id, base_url=config.app_base_url())
    except (stripe_connect.StripeOff, ValueError) as exc:
        log.warning("connect start failed: %s", exc)
        return RedirectResponse("/", status_code=303)
    return RedirectResponse(url, status_code=303)


@router.post("/payments/connect/start", dependencies=[Depends(security.protect_host_post)])
async def connect_start_post(request: Request):
    """The one-time 'connect payments' button lands here (CSRF-protected)."""
    return await connect_start(request)


@router.get("/payments/connect/return")
async def connect_return(request: Request):
    """Stripe redirects here after the hosted form; return ≠ verified."""
    guard = await _signed_in(request)
    if guard:
        return guard
    if _off():
        return Response(status_code=404)
    owner_id = _workspace(request)
    if owner_id is None:
        return RedirectResponse("/", status_code=303)
    try:
        stripe_connect.handle_return(owner_id)
    except (stripe_connect.StripeOff, ValueError, KeyError) as exc:
        log.warning("connect return failed: %s", exc)
    # The dashboard reads the state from the mirror; the visible copy and the
    # ? popover explaining "return is not verified" arrive with the payments
    # dashboard (plan P1.5).
    return RedirectResponse("/", status_code=303)


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Verify the raw body, dedupe by event id, answer 2xx fast."""
    scope = "stripe_webhook"
    key = rate_limit.client_key(request, scope)
    if rate_limit.blocked(key=key, scope=scope, max_events=_WEBHOOK_LIMIT, window=_WEBHOOK_WINDOW):
        return PlainTextResponse("slow down", status_code=429)
    rate_limit.record(scope, key)
    raw = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    if _off() or not config.STRIPE_WEBHOOK_SECRET:
        # ENVIRONMENT.md contract: logged-and-ignored while off or in tests;
        # a missing secret in test/live mode fails loudly, never silently.
        if not _off():
            log.error("webhook secret unset while UBYHOST_STRIPE_MODE=%s", config.STRIPE_MODE)
            return PlainTextResponse("webhook secret not configured", status_code=500)
        log.info("stripe webhook ignored (mode off): sig=%s bytes=%d", bool(sig), len(raw))
        return PlainTextResponse("ignored", status_code=200)
    try:
        event = stripe_connect.verify_event(raw, sig)
    except stripe_connect.StripeOff:
        log.error("webhook arrived with no API budget or key; UBYHOST_STRIPE_MODE=%s", config.STRIPE_MODE)
        return PlainTextResponse("not configured", status_code=500)
    except ValueError as exc:
        log.warning("stripe webhook signature rejected: %s", exc)
        return PlainTextResponse("bad signature", status_code=400)
    stripe_connect.process_event(event)
    return PlainTextResponse("ok", status_code=200)
