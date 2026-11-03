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
from fastapi.responses import RedirectResponse, Response

from .. import access, auth, config, db, host_i18n, i18n, mail, payment_links, payment_request, payment_services, payments_consent, security, stripe_connect
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


def _setup(owner_id: int, state: Dict[str, Any]) -> Dict[str, Any]:
    """The 4 guided setup steps (0729) and which one the primary button opens."""
    consent = payments_consent.accepted(owner_id)
    entity = stripe_connect.legal_entity_for_owner(owner_id)
    has_details = bool(entity and (entity.get("name") or "").strip())
    onboarding = state.get("onboarding_state") or "none"
    stripe_status = {"pending": "waiting", "action_required": "attention"}.get(onboarding, "todo")
    steps = [
        {"key": "consent", "status": "done" if consent else "todo"},
        {"key": "details", "status": "done" if has_details else "todo",
        "href": f"/entities?edit={entity['id']}" if entity else "/entities"},
        {"key": "stripe", "status": stripe_status},
        {"key": "live", "status": "todo"},
    ]
    if not consent:
        next_step = "consent"
    elif not has_details:
        next_step = "details"
    else:
        next_step = "stripe"
    return {"steps": steps, "next": next_step, "entity": entity if has_details else None}


@router.get("/payments")
def payments_page(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner_id = access.owner_id(request)
    state = _connect_state(owner_id)
    raw_stay = str(request.query_params.get("reservation_id") or "")
    selected_reservation_id = int(raw_stay) if raw_stay.isdigit() else None
    services = payment_services.list_for(owner_id)
    prefill = payment_services.get(owner_id, str(request.query_params.get("service") or ""))
    return render(
        request,
        "payments.html",
        {
            "nav": "payments",
            "how_key": "payments",
            "connect_state": state,
            "setup": _setup(owner_id, state),
            "stripe_off": _off(),
            "requests": payment_request.for_owner(owner_id),
            "reasons": list(payment_request.REASONS),
            "stays": [
                {"id": s["id"], "label": _stay_label(s)} for s in _stays(owner_id)
            ],
            "selected_reservation_id": selected_reservation_id,
            "services": services,
            "prefill": prefill,
        },
    )


@router.post("/payments/services")
async def payment_service_add(request: Request):
    """0762: save one extra (name + price)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    form = await request.form()
    raw_amount = str(form.get("amount_czk") or "").strip()
    if not raw_amount.isdigit():
        return _back("/payments", err=_flash(request, "payments.err.amount"))
    try:
        payment_services.add(access.owner_id(request), str(form.get("name") or ""), int(raw_amount))
    except ValueError:
        return _back("/payments", err=_flash(request, "payments.services.err"))
    return _back("/payments", msg=_flash(request, "payments.services.saved"))


@router.post("/payments/services/{service_id}/delete")
async def payment_service_delete(request: Request, service_id: str):
    guard = auth.require_login(request)
    if guard:
        return guard
    payment_services.remove(access.owner_id(request), service_id)
    return _back("/payments", msg=_flash(request, "payments.services.removed"))


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


_OPEN_CARD = ("draft", "sent", "awaiting_payment")


def _own_card_request(request: Request, request_id: int):
    """The owner's open card request, or None."""
    row = payment_request.get(request_id)
    if row is None or int(row["owner_user_id"]) != access.owner_id(request):
        return None
    if row["rail"] != "card" or row["status"] not in _OPEN_CARD:
        return None
    return row


@router.post("/payments/requests/{request_id}/link")
async def payment_request_link(request: Request, request_id: int):
    """0761: make (or reuse) the card link without an e-mail, then show the
    share page. Never redirect this POST off-site (CSP form-action, 0730)."""
    guard = auth.require_login(request)
    if guard:
        return guard
    row = _own_card_request(request, request_id)
    if row is None:
        return _back("/payments", err=_flash(request, "payments.err.invalid"))
    try:
        link = payment_links.send(request_id) or ""
    except stripe_connect.StripeOff:
        return _back("/payments", err=_flash(request, "payments.err.stripe_off"))
    if not link:
        return _back("/payments", err=_flash(request, "payments.err.not_ready"))
    if row["status"] == "draft":
        from datetime import date

        payment_request.set_status(request_id, "sent", today=date.today())
    return RedirectResponse(f"/payments/requests/{request_id}/share", status_code=303)


@router.get("/payments/requests/{request_id}/share")
def payment_request_share(request: Request, request_id: int):
    """0761: the link, Copy, WhatsApp and e-mail. Reached only after the POST."""
    guard = auth.require_login(request)
    if guard:
        return guard
    row = _own_card_request(request, request_id)
    if row is None or not row.get("stripe_payment_link_id"):
        return _back("/payments", err=_flash(request, "payments.err.invalid"))
    try:
        link = payment_links.send(request_id) or ""
    except stripe_connect.StripeOff:
        return _back("/payments", err=_flash(request, "payments.err.stripe_off"))
    if not link:
        return _back("/payments", err=_flash(request, "payments.err.not_ready"))
    from urllib.parse import quote

    lang = host_i18n.lang_from_request(request)
    reason = host_i18n.translate(lang, f"payments.reason.{row['reason']}")
    message = host_i18n.translate(
        lang, "payments.share.message", reason=reason, amount=row["amount_czk"], link=link
    )
    subject = host_i18n.translate(lang, "payments.share.subject")
    email = (row.get("guest_email") or "").strip()
    return render(
        request,
        "payments_share.html",
        {
            "nav": "payments",
            "how_key": "payments",
            "req": row,
            "link": link,
            "whatsapp_url": "https://wa.me/?text=" + quote(message),
            "mailto_url": f"mailto:{quote(email)}?subject={quote(subject)}&body={quote(message)}",
        },
    )


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
        link = f"{config.app_base_url()}/pay/{request_id}/{payment_request.guest_token(row)}"
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
        {"nav": "payments", "request": row, "qr_payload": payload, "show_nav": False, "png_url": f"/payments/qr/{row['id']}.png"},
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


# --- booking site setup (brief 0819) ---------------------------------------------


def _bsite_apartment(request: Request, apartment_id: int):
    owner_id = access.owner_id(request)
    row = db.query_one(
        "SELECT id, internal_name FROM apartment WHERE id = ? AND owner_user_id = ?",
        (apartment_id, owner_id),
    )
    return row, owner_id


@router.get("/apartments/{apartment_id}/booking-site")
def booking_site_setup(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_manage, booking_setup, booking_site, property_page as pp
    from .. import payments as payments_mod

    context: Dict[str, Any] = {
        "nav": "properties", "apartment": apartment,
        "allowed": booking_site.site_allowed(owner_id),
    }
    if context["allowed"]:
        lang = host_i18n.lang_from_request(request)
        s = booking_site.settings(apartment_id)
        slug = pp.ensure_slug(apartment_id)["slug"]
        page_url = f"{config.PUBLIC_BASE_URL.rstrip('/')}/p/{slug}"
        rows = booking_setup.steps(apartment_id, owner_id)
        context.update(
            s=s,
            steps=rows,
            steps_done=sum(1 for row in rows if row["done"]),
            can_publish=booking_setup.can_publish(rows),
            published=any(row["key"] == "publish" and row["done"] for row in rows),
            page_url=page_url,
            ical_url=f"{page_url}/{booking_site.ical_token(apartment_id)}.ics",
            qr=payments_mod.qr_data_uri(page_url),
            notice_value=booking_setup.notice_value(s),
            notice_options=[
                (value, host_i18n.translate(lang, "bsite.notice." + value.replace(":", "_")))
                for value in booking_setup.NOTICE_OPTIONS
            ],
            policies=booking_site.POLICIES,
            bookings=booking_manage.host_rows(apartment_id),
        )
    return render(request, "booking_site_setup.html", context)


@router.post("/apartments/{apartment_id}/booking-site")
async def booking_site_save(request: Request, apartment_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_setup, booking_site, property_page as pp

    here = f"/apartments/{apartment_id}/booking-site"
    if not booking_site.site_allowed(owner_id):
        return _back(here, err=_flash(request, "bsite.err.not_max"))
    form = await request.form()
    if "ical_done" in form:
        booking_setup.mark_calendar_done(apartment_id)
        return _back(here, msg=_flash(request, "bsite.flash.ical_done"))
    if "publish" in form or "unpublish" in form:
        if "publish" in form and not booking_setup.can_publish(booking_setup.steps(apartment_id, owner_id)):
            return _back(here, err=_flash(request, "bsite.err.publish_not_ready"))
        pp.publish_page(apartment_id, published="publish" in form)
        key = "bsite.flash.published" if "publish" in form else "bsite.flash.unpublished"
        return _back(here, msg=_flash(request, key))
    try:
        booking_site.save_settings(apartment_id, booking_setup.parse_form(form))
    except ValueError as exc:
        err_key = "bsite.err." + booking_setup.error_field(exc)
        return _back(here + "#rules", err=_flash(request, err_key))
    return _back(here, msg=_flash(request, "payments.page.saved"))


@router.post("/apartments/{apartment_id}/booking-site/cancel")
async def booking_site_cancel(request: Request, apartment_id: int):
    """0821: the host cancels a site booking; the guest is refunded in full."""
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment, owner_id = _bsite_apartment(request, apartment_id)
    if apartment is None:
        return Response(status_code=404)
    from .. import booking_cancel, booking_site

    here = f"/apartments/{apartment_id}/booking-site"
    form = await request.form()
    raw = str(form.get("booking_id") or "")
    booking = booking_site.get(int(raw)) if raw.isdigit() else None
    if booking is None or int(booking["apartment_id"]) != apartment_id or int(booking["owner_user_id"]) != owner_id:
        return Response(status_code=404)
    result = booking_cancel.cancel(int(booking["id"]), by_host=True)
    if result["error"] == "refund_failed":
        return _back(here, err=_flash(request, "bsite.err.cancel_failed"))
    if result["error"]:
        return _back(here, err=_flash(request, "bsite.err.not_cancellable"))
    return _back(here, msg=_flash(request, "bsite.flash.cancelled"))


# --- one-time payments consent (0624) ------------------------------------------


@router.get("/payments/consent")
def payments_consent_page(request: Request):
    """The plain-language summary a host accepts once before Stripe."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if _off():
        return Response(status_code=404)
    return render(request, "payments_consent.html", {"nav": "payments", "how_key": "payments"})


@router.post("/payments/consent")
async def payments_consent_accept(request: Request):
    """Record the tick, then go straight on to Stripe onboarding."""
    guard = auth.require_login(request)
    if guard:
        return guard
    if _off():
        return Response(status_code=404)
    workspace = auth.workspace_user(request)
    if not workspace:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    if str(form.get("agree") or "") != "1":
        return _back("/payments/consent", err=_flash(request, "payments.err.consent"))
    payments_consent.record(int(workspace["id"]))
    # 0730: never redirect a form POST to Stripe. The CSP form-action 'self'
    # blocks a form whose redirect chain leaves our origin (blank page). Back
    # to /payments, where "Open Stripe" is a plain link.
    return _back("/payments", msg=_flash(request, "payments.consent.saved"))


# --- public guest QR page (0763) ----------------------------------------------


def _guest_qr_row(request_id: int, token: str):
    row = payment_request.get(request_id)
    if row is None or row["rail"] != "qr" or row["status"] == "cancelled":
        return None
    if not payment_request.guest_token_ok(row, token):
        return None
    return row


@router.get("/pay/{request_id:int}/{token}.png")
def guest_qr_png(request_id: int, token: str):
    row = _guest_qr_row(request_id, token)
    if row is None:
        return Response(status_code=404)
    try:
        _, png = payment_request.qr_payload(row)
    except ValueError:
        return Response(status_code=404)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.get("/pay/{request_id:int}/{token}")
def guest_qr_page(request: Request, request_id: int, token: str):
    """0763: the guest's bank-transfer page; no login, token-checked."""
    row = _guest_qr_row(request_id, token)
    if row is None:
        return Response(status_code=404)
    try:
        payload, _ = payment_request.qr_payload(row)
    except ValueError:
        return Response(status_code=404)
    response = render(
        request,
        "payments_qr.html",
        {
            "request": row,
            "qr_payload": payload,
            "show_nav": False,
            "png_url": f"/pay/{request_id}/{token}.png",
        },
    )
    response.headers["X-Robots-Tag"] = "noindex"
    return response
