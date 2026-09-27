"""Host-only invoice tool: a standalone, free-form invoice builder.

An invoice is NOT tied to a stay. Included in main.py after admin.router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from .. import (
    access,
    auth,
    claim,
    codelists,
    config,
    db,
    host_i18n,
    invoice_links,
    invoices,
    mail,
    mail_notify,
    rate_limit,
    security,
)
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


def _entities(request: Request):
    return db.query(
        "SELECT * FROM legal_entity WHERE archived_at IS NULL AND owner_user_id IS ? "
        "ORDER BY name",
        (access.owner_id(request),),
    )


def _chosen_entity(request, entities, form=None):
    if form is not None:
        entity_id = _form_str(form, "legal_entity_id")
        if entity_id.isdigit():
            for entity in entities:
                if str(entity["id"]) == entity_id:
                    return entity
    return entities[0] if entities else None


def _form_context(request, entities, entity, *, errors=None, values=None):
    return {
        "nav": "invoices",
        "entities": entities,
        "entity": entity,
        "next_number": invoices.preview_number(entity) if entity else "",
        "errors": errors or [],
        "values": values or {},
        "countries": codelists.nationality_options(_lang(request)),
    }


def _draft(request, entity, form):
    draft = invoices.build_draft(entity, form, _lang(request), today=claim.prague_today())
    draft.update({"legal_entity_id": entity["id"], "owner_user_id": access.owner_id(request)})
    return draft


def _preview_view(draft) -> dict:
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
        "paid_via_label": invoices.custom_paid_via_label(draft.get("paid_via")),
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
        "stay_label": None,
        "total_haler": draft["total_haler"],
        "corrects_number": None,
        "correction_reason": None,
        "correction_date": None,
    }


@router.get("/invoices")
def invoices_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    rows = db.query(
        "SELECT * FROM invoice WHERE owner_user_id IS ? ORDER BY issue_date DESC, id DESC",
        (access.owner_id(request),),
    )
    return render(request, "invoices.html", {"nav": "invoices", "invoices": rows})


@router.get("/invoices/new")
def invoice_new(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entities = _entities(request)
    entity = _chosen_entity(request, entities)
    context = _form_context(request, entities, entity)
    if not entity:
        context["errors"] = [host_i18n.translate(_lang(request), "invoice.err.no_entity")]
    return render(request, "invoice_form.html", context)


@router.post("/invoices/preview")
async def invoice_preview(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entities = _entities(request)
    form = await request.form()
    entity = _chosen_entity(request, entities, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form)
    pdf = invoices.invoice_pdf.render(
        _preview_view(draft), draft["items"], draft["lang"], preview=True
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="nahled-faktura.pdf"'},
    )


@router.post("/invoices")
async def invoice_issue(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entities = _entities(request)
    form = await request.form()
    entity = _chosen_entity(request, entities, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form)
    issues = invoices.validate_for_issue(draft)
    if issues:
        lang = _lang(request)
        context = _form_context(
            request,
            entities,
            entity,
            errors=[host_i18n.translate(lang, issue.message) for issue in issues],
        )
        return render(request, "invoice_form.html", context, status_code=422)
    invoice_id = invoices.issue(draft, access.owner_id(request))
    number = db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"]
    return _back(f"/invoices/{invoice_id}", msg=_flash(request, "invoice.issued_flash", number=number))


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
    items = db.query(
        "SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY position", (invoice_id,)
    )
    return render(
        request,
        "invoice_detail.html",
        {
            "nav": "invoices",
            "invoice": invoice,
            "items": items,
            "vat_totals": db.query_one(
                "SELECT COALESCE(SUM(base_haler), 0) AS base, "
                "COALESCE(SUM(vat_haler), 0) AS vat "
                "FROM invoice_item WHERE invoice_id = ?",
                (invoice_id,),
            ),
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


@router.post("/invoices/{invoice_id}/send")
async def invoice_send(invoice_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    invoice = _load_invoice(request, invoice_id)
    if not invoice:
        return _back("/invoices", err=_flash(request, "flash.error.no_such_invoice"))
    if not invoice["buyer_email"]:
        return _back(f"/invoices/{invoice_id}", err=_flash(request, "invoice.err.no_email"))
    entity = access.entity(request, invoice["legal_entity_id"])
    token = invoice_links.download_token(invoice_id, invoice["pdf_sha256"] or "")
    url = f"{config.PUBLIC_BASE_URL}/invoice/d/{mail.CLAIM_SECRET_MARKER}"
    content = mail_notify.build_invoice_issued(
        lang=invoice["lang"],
        property_name=entity["name"] if entity else "UbyHost",
        number=invoice["number"],
        total=invoices.invoice_pdf.money(invoice["total_haler"]),
        download_url=url,
        host=mail_notify.host_details(invoice["legal_entity_id"]),
    )
    payload = mail_notify.guest_payload(
        {"legal_entity_id": invoice["legal_entity_id"]}, content, invoice["lang"]
    )
    payload[mail.CLAIM_SECRET_KEY] = db.encrypt_field(token)
    sent_before = db.query_one(
        "SELECT COUNT(*) AS n FROM email_outbox WHERE idempotency_key LIKE ?",
        (f"invoice_issued:{invoice_id}:%",),
    )["n"]
    mail.enqueue(
        kind="invoice_issued",
        idempotency_key=f"invoice_issued:{invoice_id}:{sent_before}",
        to_email=invoice["buyer_email"],
        subject=content["subject"],
        payload=payload,
        owner_user_id=access.owner_id(request),
    )
    db.update("invoice", invoice_id, {"emailed_at": db.utcnow()})
    db.audit("invoice_sent", f"id={invoice_id}", owner_user_id=access.owner_id(request))
    return _back(f"/invoices/{invoice_id}", msg=_flash(request, "invoice.sent_flash"))


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


@router.get("/invoice/d/{token}")
def invoice_download(token: str, request: Request):
    """Public: the token in the e-mail is the only credential the recipient has."""
    key = rate_limit.client_key(request, "invoice_download")
    if rate_limit.blocked("invoice_download", key, 30, 3600):
        return Response("Too many requests", status_code=429)
    rate_limit.record("invoice_download", key)
    invoice_id = invoice_links.read_download_token(token)
    if not invoice_id:
        return Response("Not found", status_code=404)
    pdf = invoices.download_pdf(invoice_id)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
        },
    )
