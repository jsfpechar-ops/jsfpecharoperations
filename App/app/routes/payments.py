"""Host-facing payments section: connect card, request form, request list.

Brief 0429 (payments P1.5). Everything behind the host CSRF dependency; the
Stripe calls themselves stay in app/stripe_connect.py and its routes — this
module reads the mirror and writes drafts into payment_request. The card and
QR rails (briefs 0435/0436) light the Send buttons up; until then the toggle
explains why, in one sentence each (rule 9).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from .. import access, auth, config, db, payment_request, security, stripe_connect
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

REASON_KEYS = {
    "repair": "payments.reason.repair",
    "extra_guest": "payments.reason.extra_guest",
    "late_checkout": "payments.reason.late_checkout",
    "cleaning": "payments.reason.cleaning",
    "damage": "payments.reason.damage",
    "custom": "payments.reason.custom",
}


def _off() -> bool:
    return config.STRIPE_MODE not in ("test", "live")


def _connect_state(owner_id: int) -> Dict[str, Any]:
    row = stripe_connect.account_for_owner(owner_id)
    return dict(row) if row else {"onboarding_state": "none", "stripe_account_id": None}


def _stays(owner_id: int) -> List[Dict[str, Any]]:
    return [
        dict(r)
        for r in db.query(
            "SELECT r.id, r.summary, r.date_from, r.date_to, a.internal_name"
            " FROM reservation r JOIN apartment a ON a.id = r.apartment_id"
            " WHERE a.owner_user_id = ? AND r.status = 'active'"
            " ORDER BY r.date_from DESC, r.id DESC LIMIT 200",
            (owner_id,),
        )
    ]


def _stay_label(stay: Dict[str, Any]) -> str:
    name = (stay["summary"] or "").strip() or (stay["internal_name"] or "").strip()
    return f"{name} ({stay['date_from']} → {stay['date_to']})"


@router.get("/payments")
def payments_page(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    state = _connect_state(owner_id)
    return render(
        request,
        "payments.html",
        {
            "nav": "payments",
            "how_key": "payments",
            "connect_state": state,
            "stripe_off": _off(),
            "requests": payment_request.for_owner(owner_id),
            "reasons": list(payment_request.REASONS),
            "stays": [
                {"id": s["id"], "label": _stay_label(s)} for s in _stays(owner_id)
            ],
        },
    )


@router.post("/payments/requests/new")
async def payment_request_new(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    owner_id = access.owner_id(request)
    back = _back("/payments", err=_flash(request, "payments.err.invalid"))
    reason = str(form.get("reason") or "").strip()
    if reason not in payment_request.REASONS:
        return back
    raw_amount = str(form.get("amount_czk") or "").strip()
    if not raw_amount.isdigit() or int(raw_amount) < 1:
        return _back("/payments", err=_flash(request, "payments.err.amount"))
    stay_raw = str(form.get("reservation_id") or "").strip()
    reservation_id: int | None = None
    if stay_raw.isdigit():
        stay = db.query_one(
            "SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id"
            " WHERE r.id = ? AND a.owner_user_id = ?",
            (int(stay_raw), owner_id),
        )
        if stay is None:
            return back
        reservation_id = int(stay["id"])
    from datetime import date, timedelta

    expires = (date.today() + timedelta(days=30)).isoformat()
    payment_request.create(
        owner_id,
        reservation_id=reservation_id,
        reason=reason,
        amount_czk=int(raw_amount),
        rail="card",
        expires_at=expires,
        guest_email=(str(form.get("guest_email") or "").strip() or None),
        guest_note=(str(form.get("guest_note") or "").strip() or None),
    )
    return _back("/payments", msg=_flash(request, "payments.draft_saved"))
