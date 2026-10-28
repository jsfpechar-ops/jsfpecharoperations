"""Host-facing payments section: connect card, request form, request list.

Brief 0429 (payments P1.5). Everything behind the host CSRF dependency; the
Stripe calls themselves stay in app/stripe_connect.py and its routes — this
module reads the mirror and writes drafts into payment_request. The card and
QR rails (briefs 0435/0436) light the Send buttons up; until then the toggle
explains why, in one sentence each (rule 9).
"""
from __future__ import annotations

from typing import Any, Dict, List

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from .. import access, auth, config, db, host_i18n, i18n, mail, payment_links, payment_request, security, stripe_connect
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
    rail = str(form.get("rail") or "card").strip()
    if rail not in payment_request.RAILS:
        return back
    payment_request.create(
        owner_id,
        reservation_id=reservation_id,
        reason=reason,
        amount_czk=int(raw_amount),
        rail=rail,
        expires_at=expires,
        guest_email=(str(form.get("guest_email") or "").strip() or None),
        guest_note=(str(form.get("guest_note") or "").strip() or None),
    )
    return _back("/payments", msg=_flash(request, "payments.draft_saved"))


def _host_reply_to(row) -> str:
    """Guest mails answer the host, never UbyHost support (mail.py contract)."""
    from .. import db as _db

    entity = _db.query_one(
        "SELECT le.contact_email FROM legal_entity le"
        " JOIN apartment a ON a.legal_entity_id = le.id"
        " WHERE a.owner_user_id = ? LIMIT 1",
        (int(row["owner_user_id"]),),
    )
    if entity is None:
        entity = _db.query_one(
            "SELECT contact_email FROM legal_entity WHERE owner_user_id = ? LIMIT 1",
            (int(row["owner_user_id"]),),
        )
    return str(entity["contact_email"] or "") if entity else ""


@router.post("/payments/requests/{request_id}/send")
async def payment_request_send(request: Request, request_id: int):
    """0435/0436: send the request to the guest (card link or QR page)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    row = payment_request.get(request_id)
    if row is None or int(row["owner_user_id"]) != owner_id:
        return _back("/payments", err=_flash(request, "payments.err.invalid"))
    if row["status"] not in ("draft", "sent"):
        return _back("/payments", err=_flash(request, "payments.err.cannot_send"))
    resend = row["status"] == "sent"
    guest_email = (row["guest_email"] or "").strip()
    if not guest_email:
        return _back("/payments", err=_flash(request, "payments.err.no_email"))
    lang = "cs"
    link: str
    if row["rail"] == "card":
        try:
            link = payment_links.send(request_id) or ""
        except stripe_connect.StripeOff:
            return _back("/payments", err=_flash(request, "payments.err.stripe_off"))
        if not link:
            return _back("/payments", err=_flash(request, "payments.err.not_ready"))
    else:
        link = f"/payments/qr/{request_id}"
    if not resend:
        payment_request.set_status(request_id, "sent", today=__import__("datetime").date.today())
    translate = i18n.translator(lang)
    reason_label = host_i18n.translate(lang, f"payments.reason.{row['reason']}")
    mail.enqueue(
        kind="payment_request",
        idempotency_key=f"payment_request:{request_id}:sent:v{2 if resend else 1}",
        to_email=guest_email,
        subject=translate(
            "mail_payment_request_subject",
            amount=row["amount_czk"],
        ),
        payload={"text": translate(
            "mail_payment_request_text",
            amount=row["amount_czk"],
            reason=reason_label,
            link=link,
        ), "lang": lang, "reply_to": _host_reply_to(row), "apartment": None},
        reservation_id=row["reservation_id"],
        owner_user_id=owner_id,
    )
    return _back("/payments", msg=_flash(request, "payments.sent"))


@router.get("/payments/qr/{request_id:int}.png")
def payment_request_qr_png(request: Request, request_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    row = payment_request.get(request_id)
    if row is None or int(row["owner_user_id"]) != owner_id or row["rail"] != "qr":
        return Response(status_code=404)
    try:
        _, png = payment_request.qr_payload(row)
    except ValueError:
        return Response(status_code=404)
    return Response(content=png, media_type="image/png")


@router.get("/payments/qr/{request_id}")
def payment_request_qr(request: Request, request_id: int):
    """0436: the guest's SPAYD page (public via token later; host preview now)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    row = payment_request.get(request_id)
    if row is None or int(row["owner_user_id"]) != owner_id or row["rail"] != "qr":
        return _back("/payments", err=_flash(request, "payments.err.invalid"))
    try:
        payload, png = payment_request.qr_payload(row)
    except ValueError:
        return _back("/payments", err=_flash(request, "payments.err.no_iban"))
    return render(
        request,
        "payments_qr.html",
        {"nav": "payments", "request": row, "qr_payload": payload, "show_nav": False},
    )




# --- property page review screen (brief 0431) -------------------------------


@router.get("/apartments/{apartment_id}/page")
def property_page_review(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    apartment = db.query_one(
        "SELECT id, internal_name FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id),
    )
    if apartment is None:
        return Response(status_code=404)
    from .. import property_page as pp

    page = pp.page_for(apartment_id)
    slug_row = pp.ensure_slug(apartment_id)
    return render(
        request,
        "property_page_review.html",
        {
            "nav": "properties",
            "apartment": apartment,
            "page": page,
            "page_photos": json.loads(page["photos_json"] or "[]"),
            "slug": slug_row["slug"],
            "published": bool(page["published"]),
        },
    )


@router.post("/apartments/{apartment_id}/page")
async def property_page_save(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    apartment = db.query_one(
        "SELECT id FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id),
    )
    if apartment is None:
        return Response(status_code=404)
    from .. import property_page as pp

    form = await request.form()
    if "search_save" in form:
        db.execute(
            "UPDATE property_page SET hide_from_search = ?, updated_at = ? WHERE apartment_id = ?",
            (1 if form.get("hide_from_search") else 0, db.utcnow(), apartment_id),
        )
        return _back(f"/apartments/{apartment_id}/page", msg=_flash(request, "payments.page.saved"))
    if "publish" in form or "unpublish" in form:
        pp.publish_page(apartment_id, published="publish" in form)
        msg = "payments.page.published" if "publish" in form else "payments.page.unpublished"
        return _back(f"/apartments/{apartment_id}/page", msg=_flash(request, msg))
    pp.save_page(
        apartment_id,
        description=str(form.get("description") or "").strip(),
        amenities=[
            ln.strip()
            for ln in str(form.get("amenities") or "").splitlines()
            if ln.strip()
        ],
    )
    return _back(f"/apartments/{apartment_id}/page", msg=_flash(request, "payments.page.saved"))


@router.post("/apartments/{apartment_id}/page/photo-delete")
async def property_page_photo_delete(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    apartment = db.query_one(
        "SELECT id FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id),
    )
    if apartment is None:
        return Response(status_code=404)
    form = await request.form()
    from .. import property_page as pp

    pp.delete_photo(apartment_id, str(form.get("path") or ""))
    return _back(f"/apartments/{apartment_id}/page", msg=_flash(request, "payments.page.saved"))
