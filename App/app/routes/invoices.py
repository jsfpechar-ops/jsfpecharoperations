"""Host-only invoice routes: list, issue, preview, detail, PDF, paid, cancel.

A guest never reaches this module (see the SCOPE DECISION in
docs/plans/PLAN_GUEST_INVOICE_FEATURE.md). Included in main.py after admin.router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from .. import access, auth, claim, codelists, db, host_i18n, invoices, security, stay_fee
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])


def _lang(request: Request) -> str:
    return host_i18n.lang_from_request(request)


def _load_invoice(request: Request, invoice_id: int):
    return db.query_one(
        "SELECT * FROM invoice WHERE id = ? AND owner_user_id IS ?",
        (invoice_id, access.owner_id(request)),
    )


def _reservation_with_apartment(request: Request, reservation_id: int):
    reservation = access.reservation(
        request,
        reservation_id,
        "r.*, a.internal_name, a.legal_entity_id, a.permalink_token",
    )
    if not reservation:
        return None, None
    apartment = access.apartment(request, reservation["apartment_id"])
    return reservation, apartment


def _form_context(request, reservation, apartment, entity, *, errors=None, values=None):
    fee = stay_fee.stay_summary(reservation, apartment) if apartment else None
    fee_total = fee["total_czk"] if fee else 0
    return {
        "nav": "invoices",
        "reservation": reservation,
        "apartment": apartment,
        "entity": entity,
        "next_number": invoices.preview_number(entity) if entity else "",
        "errors": errors or [],
        "values": values or {},
        "countries": codelists.nationality_options("en"),
        "stay_fee_total": fee_total,
        "stay_fee_paid": bool(fee and fee["paid_at"]),
        "invoices_for_stay": db.query(
            "SELECT * FROM invoice WHERE reservation_id = ? AND owner_user_id IS ? "
            "ORDER BY id DESC",
            (reservation["id"], access.owner_id(request)),
        ),
    }


def _build_draft(request, reservation, apartment, entity, form):
    today = claim.prague_today()
    draft = invoices.build_draft(reservation, entity, form, _lang(request), today=today)
    draft.update(
        {
            "legal_entity_id": entity["id"],
            "apartment_id": apartment["id"],
            "reservation_id": reservation["id"],
            "owner_user_id": access.owner_id(request),
        }
    )
    return draft


@router.get("/invoices")
def invoices_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        "SELECT * FROM invoice WHERE owner_user_id IS ? "
        "ORDER BY issue_date DESC, id DESC",
        (access.owner_id(request),),
    )
    return render(request, "invoices.html", {"nav": "invoices", "invoices": rows})


@router.get("/reservations/{reservation_id}/invoice/new")
def invoice_new(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation, apartment = _reservation_with_apartment(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    entity = access.entity(request, apartment["legal_entity_id"]) if apartment and apartment["legal_entity_id"] else None
    context = _form_context(request, reservation, apartment, entity)
    if not entity:
        context["errors"] = [
            host_i18n.translate(_lang(request), "invoice.err.no_entity")
        ]
    return render(request, "invoice_form.html", context)


@router.post("/reservations/{reservation_id}/invoice/preview")
async def invoice_preview(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation, apartment = _reservation_with_apartment(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    entity = access.entity(request, apartment["legal_entity_id"]) if apartment and apartment["legal_entity_id"] else None
    if not entity:
        return _back(f"/reservations/{reservation_id}", err=_flash(request, "flash.error.no_such_entity"))
    form = await request.form()
    draft = _build_draft(request, reservation, apartment, entity, form)
    view = _preview_view(draft)
    pdf = invoices.invoice_pdf.render(view, draft["items"], draft["lang"], preview=True)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="nahled-faktura.pdf"'},
    )


@router.post("/reservations/{reservation_id}/invoice")
async def invoice_issue(reservation_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    reservation, apartment = _reservation_with_apartment(request, reservation_id)
    if not reservation:
        return _back("/reservations", err=_flash(request, "flash.error.no_such_stay"))
    entity = access.entity(request, apartment["legal_entity_id"]) if apartment and apartment["legal_entity_id"] else None
    if not entity:
        return _back(f"/reservations/{reservation_id}", err=_flash(request, "flash.error.no_such_entity"))
    form = await request.form()
    draft = _build_draft(request, reservation, apartment, entity, form)
    issues = invoices.validate_for_issue(draft)
    if issues:
        lang = _lang(request)
        context = _form_context(
            request,
            reservation,
            apartment,
            entity,
            errors=[host_i18n.translate(lang, issue.message) for issue in issues],
        )
        return render(request, "invoice_form.html", context, status_code=422)
    invoice_id = invoices.issue(draft, access.owner_id(request))
    number = db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"]
    return _back(
        f"/invoices/{invoice_id}",
        msg=_flash(request, "invoice.issued_flash", number=number),
    )


def _preview_view(draft) -> dict:
    """A stand-in invoice row for the preview render (no number allocated yet)."""
    seller = draft["seller"]
    buyer = draft["buyer"]
    return {
        "number": "—",
        "vs": "—",
        "kind": draft["kind"],
        "vat_status": draft["vat_status"],
        "issue_date": draft["issue_date"],
        "duzp": draft.get("duzp"),
        "due_date": draft.get("due_date"),
        "paid_on": draft.get("paid_on"),
        "paid_via_label": None,
        "seller_name": seller["name"],
        "seller_seat": seller["seat"],
        "seller_ico": seller["ico"],
        "seller_dic": seller["dic"],
        "seller_registry": seller["registry"],
        "seller_bank_account": seller["bank_account"],
        "seller_iban": seller["iban"],
        "seller_bic": seller["bic"],
        "seller_email": seller["email"],
        "seller_phone": seller["phone"],
        "buyer_name": buyer["name"],
        "buyer_street": buyer["street"],
        "buyer_city": buyer["city"],
        "buyer_zip": buyer["zip"],
        "buyer_country": buyer["country"],
        "buyer_country_name": "",
        "buyer_ico": buyer["ico"],
        "buyer_dic": buyer["dic"],
        "buyer_email": buyer["email"],
        "stay_label": draft.get("stay_label"),
        "total_haler": draft["total_haler"],
        "corrects_number": None,
        "correction_reason": None,
        "correction_date": None,
    }


@router.get("/invoices/{invoice_id}.pdf")
def invoice_pdf_download(invoice_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    invoice = _load_invoice(request, invoice_id)
    if not invoice:
        return _back("/invoices", err=_flash(request, "flash.error.no_such_invoice"))
    pdf = invoices.download_pdf(invoice_id)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="faktura-{invoice["number"]}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    invoice = _load_invoice(request, invoice_id)
    if not invoice:
        return _back("/invoices", err=_flash(request, "flash.error.no_such_invoice"))
    return render(
        request,
        "invoice_detail.html",
        {
            "nav": "invoices",
            "invoice": invoice,
            "issued": request.query_params.get("issued") == "1",
        },
    )


@router.post("/invoices/{invoice_id}/paid")
async def invoice_mark_paid(invoice_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    invoice = _load_invoice(request, invoice_id)
    if not invoice:
        return _back("/invoices", err=_flash(request, "flash.error.no_such_invoice"))
    db.update("invoice", invoice_id, {"marked_paid_at": db.utcnow()})
    db.audit("invoice_marked_paid", f"id={invoice_id}", owner_user_id=access.owner_id(request))
    return _back(f"/invoices/{invoice_id}", msg=_flash(request, "invoice.marked_paid_flash"))


@router.post("/invoices/{invoice_id}/cancel")
async def invoice_cancel(invoice_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    invoice = _load_invoice(request, invoice_id)
    if not invoice:
        return _back("/invoices", err=_flash(request, "flash.error.no_such_invoice"))
    form = await request.form()
    reason = _form_str(form, "reason")
    correction_date = _form_str(form, "correction_date") or None
    try:
        new_id = invoices.cancel(
            invoice_id, reason, correction_date, access.owner_id(request),
            today=claim.prague_today(),
        )
    except ValueError as exc:
        key = str(exc)
        message = host_i18n.translate(
            _lang(request),
            "invoice.err.reason_required" if key == "reason_required" else "invoice.err.not_cancellable",
        )
        return _back(f"/invoices/{invoice_id}", err=message)
    return _back(f"/invoices/{new_id}", msg=_flash(request, "invoice.cancelled_flash"))
