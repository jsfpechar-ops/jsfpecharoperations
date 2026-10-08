"""Host-only invoice tool: every new invoice belongs to one stay.

Included in main.py after admin.router.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

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
    list_filter,
    mail,
    mail_notify,
    payments,
    rate_limit,
    security,
    stay_fee,
    validation,
)

VAT_STATUSES = ("non_payer", "identified", "payer")
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])


def _lang(request: Request) -> str:
    return host_i18n.lang_from_request(request)


@lru_cache(maxsize=1)
def _invoice_columns() -> str:
    """Every invoice column except the stored PDF, which only downloads read."""
    names = [row["name"] for row in db.query("PRAGMA table_info(invoice)")]
    return ", ".join(name for name in names if name != "pdf_blob")


def _load_invoice(request: Request, invoice_id: int):
    return db.query_one(
        f"SELECT {_invoice_columns()} FROM invoice WHERE id = ? AND {db.null_safe_eq('owner_user_id')}",
        (invoice_id, access.owner_id(request)),
    )


def _entities(request: Request):
    return db.query(
        f"SELECT * FROM legal_entity WHERE archived_at IS NULL AND {db.null_safe_eq('owner_user_id')} "
        "ORDER BY name",
        (access.owner_id(request),),
    )


def _chosen_entity(request, entities, form=None):
    wanted = ""
    if form is not None:
        wanted = _form_str(form, "legal_entity_id")
    if not wanted:
        wanted = (request.query_params.get("entity") or "").strip()
    if wanted.isdigit():
        for entity in entities:
            if str(entity["id"]) == wanted:
                return entity
    return entities[0] if entities else None


def _settings_next(request, form, entity) -> str:
    """Where ?next= on the settings page points; the builder keeps the operator."""
    raw = _form_str(form, "next") if form is not None else ""
    return security.safe_local_path(raw, f"/invoices/new?entity={entity['id']}")


def _stay_for(request: Request, raw_id) -> Optional[Dict[str, Any]]:
    """The host's own stay, shaped for invoices.build_draft, or None."""
    text = str(raw_id or "").strip()
    if not text.isdigit():
        return None
    row = access.reservation(
        request,
        int(text),
        columns="r.*, a.legal_entity_id AS apartment_entity_id, a.internal_name, a.uby_name",
    )
    if not row:
        return None
    name = (row["internal_name"] or "").strip() or (row["uby_name"] or "").strip()
    return {"reservation": row, "property_name": name, "entity_id": row["apartment_entity_id"]}


def _entity_for_stay(request, entities, stay, form=None):
    """The property's operator when it has one; otherwise the host's pick."""
    if stay and stay["entity_id"]:
        for entity in entities:
            if entity["id"] == stay["entity_id"]:
                return entity
    return _chosen_entity(request, entities, form)


def _stay_options(request: Request):
    """Stays the host can invoice, newest check-in first, for the picker."""
    today = claim.prague_today()
    rows = db.query(
        "SELECT r.id, r.date_from, r.date_to, a.internal_name, a.uby_name "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {db.null_safe_eq('a.owner_user_id')} AND r.status != 'cancelled' "
        "AND r.date_to > r.date_from AND r.date_to >= ? AND r.date_from <= ? "
        "ORDER BY r.date_from DESC, r.id DESC LIMIT 200",
        (
            access.owner_id(request),
            (today - timedelta(days=invoices.STAY_PAST_DAYS)).isoformat(),
            (today + timedelta(days=invoices.STAY_FUTURE_DAYS)).isoformat(),
        ),
    )
    options = []
    for row in rows:
        name = (row["internal_name"] or "").strip() or (row["uby_name"] or "").strip()
        dates = validation.fmt_date_range(row["date_from"], row["date_to"])
        options.append({"id": row["id"], "label": f"{name}, {dates}"})
    return options


def _form_state(request, form, entity) -> Dict[str, Any]:
    """Reshape a failed POST so the 422 render loses nothing the host typed."""
    state = {key: _form_str(form, key) for key in (
        "stay_price", "stay_vat_rate", "reservation_id",
        "buyer_name", "buyer_street", "buyer_city", "buyer_zip", "buyer_country",
        "buyer_ico", "buyer_dic", "buyer_email", "paid_via", "paid_via_custom",
        "due_date", "duzp", "note",
        "legal_entity_id",
    )}
    state["already_paid"] = "1" if form.get("already_paid") else "0"
    state["lang"] = _form_str(form, "lang")
    state["item_rows"] = [
        {key: row[key] for key in (
            "kind", "description", "quantity", "unit", "unit_price", "vat_rate"
        )}
        for row in invoices.form_item_rows(form)
    ]
    return state


def _form_context(request, entities, entity, *, errors=None, values=None, stay=None):
    values = dict(values or {})
    if stay and not values and stay["reservation"]["guest_email"]:
        values["buyer_email"] = stay["reservation"]["guest_email"]
    lang = "cs" if _lang(request) == "cs" else "en"
    return {
        "nav": "invoices",
        "entities": entities,
        "entity": entity,
        "next_number": invoices.preview_number(entity) if entity else "",
        "errors": errors or [],
        "values": values,
        "countries": codelists.nationality_options(_lang(request)),
        "stay": stay,
        "stay_label": invoices.stay_label(stay["property_name"], stay["reservation"], lang) if stay else "",
        "extra_kinds": invoices.EXTRA_KINDS,
    }


def _draft(request, entity, form, stay=None):
    draft = invoices.build_draft(
        entity, form, _lang(request), today=claim.prague_today(), stay=stay
    )
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
        "note": draft.get("note"),
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


INVOICE_STATUSES = (
    ("unpaid", "invoice.state.unpaid"),
    ("paid", "invoice.state.paid"),
    ("correction", "invoices.filter.corrections"),
)
_CANCELLED = (
    "EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = invoice.id "
    "AND c.kind = 'storno')"
)
_PAID = "(paid_on IS NOT NULL OR marked_paid_at IS NOT NULL)"
_STATUS_SQL = {
    "unpaid": f"kind = 'invoice' AND NOT {_PAID} AND NOT {_CANCELLED}",
    "paid": f"kind = 'invoice' AND {_PAID}",
    "correction": "kind IN ('storno', 'corrective')",
}


@router.get("/invoices")
def invoices_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    owner_id = access.owner_id(request)
    properties = db.query(
        f"SELECT id, internal_name FROM apartment WHERE {db.null_safe_eq('owner_user_id')} AND archived_at IS NULL "
        "ORDER BY internal_name, id",
        (owner_id,),
    )
    view = list_filter.parse(
        request.query_params,
        today=today,
        statuses=_STATUS_SQL,
        default_month=None,
        apartment_ids=[row["id"] for row in properties],
    )
    page_size = 50
    try:
        page_no = max(int(request.query_params.get("page") or "1"), 1)
    except ValueError:
        page_no = 1
    where, params = [f"{db.null_safe_eq('owner_user_id')}"], [owner_id]
    if view.month:
        first, last = stay_fee.period_bounds("monthly", view.month)
        where.append("issue_date >= ? AND issue_date <= ?")
        params += [first.isoformat(), last.isoformat()]
    if view.apartment_id is not None:
        where.append("apartment_id = ?")
        params.append(view.apartment_id)
    if view.status:
        where.append(_STATUS_SQL[view.status])
    if view.q:
        where.append("(instr(lower(number), ?) > 0 OR instr(lower(buyer_name), ?) > 0)")
        params += [view.q.lower(), view.q.lower()]
    clause = " AND ".join(where)
    total = int(db.query_one(f"SELECT COUNT(*) AS n FROM invoice WHERE {clause}", params)["n"])
    rows = db.query(
        "SELECT id, number, issue_date, buyer_name, kind, total_haler, "
        f"CASE WHEN kind != 'invoice' THEN 'correction' WHEN {_PAID} THEN 'paid' "
        f"WHEN {_CANCELLED} THEN 'cancelled' ELSE 'unpaid' END AS state "
        f"FROM invoice WHERE {clause} ORDER BY issue_date DESC, id DESC LIMIT ? OFFSET ?",
        (*params, page_size, (page_no - 1) * page_size),
    )
    pages = max((total + page_size - 1) // page_size, 1)
    query = view.query()
    page_href = "/invoices?" + (query + "&" if query else "") + "page="
    return render(
        request,
        "invoices.html",
        {
            "nav": "invoices",
            "invoices": rows,
            "invoice_page": page_no,
            "invoice_pages": pages,
            "page_href": page_href,
            **list_filter.context(
                view,
                action="/invoices",
                today=today,
                period_label_key="invoices.filter.period",
                properties=properties,
                statuses=INVOICE_STATUSES,
                search=True,
            ),
        },
    )


@router.get("/invoices/new")
def invoice_new(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    raw_stay = request.query_params.get("reservation_id")
    if not raw_stay:
        return render(
            request, "invoice_stay_picker.html", {"nav": "invoices", "stays": _stay_options(request)}
        )
    stay = _stay_for(request, raw_stay)
    if not stay:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_stay"))
    problem = invoices.stay_problem(stay["reservation"], claim.prague_today())
    if problem:
        return _back("/invoices/new", err=_flash(request, problem))
    reservation_id = stay["reservation"]["id"]
    active = invoices.active_invoice_for_stay(reservation_id)
    if active:
        return _back(f"/invoices/{active['id']}", err=_flash(request, "invoice.err.stay_has_invoice"))
    entities = _entities(request)
    entity = _entity_for_stay(request, entities, stay)
    if entity and request.query_params.get("entity") != str(entity["id"]):
        # Pin the operator in the URL once, so the details page returns here.
        return RedirectResponse(
            f"/invoices/new?reservation_id={reservation_id}&entity={entity['id']}", status_code=303
        )
    if entity and stay["entity_id"] == entity["id"]:
        entities = [entity]  # the property names its operator: no other choice
    context = _form_context(request, entities, entity, stay=stay)
    if not entity:
        context["errors"] = [host_i18n.translate(_lang(request), "invoice.err.no_entity")]
    return render(request, "invoice_form.html", context)


@router.get("/invoices/settings")
def invoice_settings(request: Request):
    """Invoice details of one operator: the fields the printed document uses.

    Registered before ``/invoices/{invoice_id}`` so "settings" is never read
    as an invoice number.
    """
    guard = auth.require_login(request)
    if guard:
        return guard
    entities = _entities(request)
    entity = _chosen_entity(request, entities)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    return render(request, "invoice_settings.html", {
        "nav": "invoices",
        "entity": entity,
        "entities": entities,
        "bank_parts": payments.czech_account_parts(entity["bank_account"] or ""),
        "next": security.safe_local_path(
            request.query_params.get("next") or "",
            f"/invoices/new?entity={entity['id']}",
        ),
    })


@router.post("/invoices/settings")
async def invoice_settings_save(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entities = _entities(request)
    form = await request.form()
    entity = _chosen_entity(request, entities, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    redirect = _settings_next(request, form, entity)
    detail = _settings_detail_payload(form)
    if any(key in form for key in ("account_prefix", "account_number", "account_bank")):
        prefix = _form_str(form, "account_prefix")
        number = _form_str(form, "account_number")
        bank = _form_str(form, "account_bank")
        existing = entity["bank_account"] or entity.get("iban") or ""
        if not payments.preserve_iban_only_account(existing, prefix, number, bank):
            detail["bank_account"] = payments.compose_czech_account(prefix, number, bank)
    if "bank_account" in detail:
        account = detail["bank_account"]
        if account:
            try:
                detail["bank_account"], detail["iban"] = payments.normalise_account(
                    account
                )
            except ValueError:
                return _back(
                    f"/invoices/settings?entity={entity['id']}",
                    err=_flash(request, "entities.bank.invalid"),
                )
        else:
            detail["bank_account"] = None
            detail["iban"] = None
    db.update("legal_entity", entity["id"], detail)
    db.audit("entity_invoice_details_saved", f"id={entity['id']}",
             owner_user_id=access.owner_id(request))
    return _back(redirect, msg=_flash(request, "flash.entities.saved"))


def _settings_detail_payload(form) -> Dict[str, Any]:
    """Presence-checked invoice details: sent = update (blank clears), absent = keep."""
    detail: Dict[str, Any] = {}
    if "bank_account" in form:
        detail["bank_account"] = _form_str(form, "bank_account")
    if "bic" in form:
        detail["bic"] = _form_str(form, "bic").replace(" ", "").upper() or None
    if "vat_status" in form:
        vat = _form_str(form, "vat_status")
        detail["vat_status"] = vat if vat in VAT_STATUSES else "non_payer"
    if "registry_entry" in form:
        detail["registry_entry"] = _form_str(form, "registry_entry") or None
    if "invoice_prefix" in form:
        prefix = (
            "".join(ch for ch in _form_str(form, "invoice_prefix").upper() if ch.isalnum())
        )[:6]
        detail["invoice_prefix"] = prefix or None
    if "invoice_next_number" in form:
        next_no = _form_str(form, "invoice_next_number").strip()
        if next_no.isdigit() and int(next_no) > 0:
            detail["invoice_next_number"] = int(next_no)
            detail["invoice_next_number_year"] = date.today().year
        else:
            detail["invoice_next_number"] = None
            detail["invoice_next_number_year"] = None
    if "invoice_due_days" in form:
        due_raw = _form_str(form, "invoice_due_days")
        due = int(due_raw) if due_raw.isdigit() else 14
        detail["invoice_due_days"] = max(0, min(due, 365))
    return detail


@router.post("/invoices/preview")
async def invoice_preview(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    entities = _entities(request)
    form = await request.form()
    stay = _stay_for(request, _form_str(form, "reservation_id"))
    if not stay or invoices.stay_problem(stay["reservation"], claim.prague_today()):
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_stay"))
    entity = _entity_for_stay(request, entities, stay, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form, stay)
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
    stay = _stay_for(request, _form_str(form, "reservation_id"))
    if not stay:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_stay"))
    problem = invoices.stay_problem(stay["reservation"], claim.prague_today())
    if problem:
        return _back("/invoices/new", err=_flash(request, problem))
    entity = _entity_for_stay(request, entities, stay, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form, stay)
    issues = invoices.validate_for_issue(draft)
    if not issues and invoices.invoice_pdf.too_long(_preview_view(draft), draft["items"], draft["lang"]):
        issues = [invoices.validation.Issue("note", "invoice.err.too_long")]
    if issues:
        lang = _lang(request)
        context = _form_context(
            request,
            entities,
            entity,
            errors=[host_i18n.translate(lang, issue.message) for issue in issues],
            values=_form_state(request, form, entity),
            stay=stay,
        )
        return render(request, "invoice_form.html", context, status_code=422)
    try:
        invoice_id = invoices.issue(draft, access.owner_id(request))
    except invoices.StayLimit as limit:
        if limit.invoice_id:
            return _back(f"/invoices/{limit.invoice_id}", err=_flash(request, limit.key))
        return _back(f"/reservations/{stay['reservation']['id']}", err=_flash(request, limit.key))
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


def _stay_property_name(invoice) -> str:
    """The guest-facing name of the property of the stay this invoice is for.

    Empty when the invoice is not linked to a stay. Same order as the guest
    pages: the host's own name, then the police-register name.
    """
    if not invoice["reservation_id"]:
        return ""
    row = db.query_one(
        "SELECT a.internal_name, a.uby_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (invoice["reservation_id"],),
    )
    if not row:
        return ""
    return (row["internal_name"] or "").strip() or (row["uby_name"] or "").strip()


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
        stay_property=_stay_property_name(invoice),
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
