"""The host's plan page /predplatne (brief 0416): order, change one thing, cancel.

Invoices only. The order form works without JavaScript; the ARES button posts
the form back with the blanks filled in, like the invoice buyer form does.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from .. import access, ares, auth, billing, billing_invoices, billing_order, host_i18n, security, validation
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

# The one change each small form on the page sends (billing.CHANGE_COLUMNS).
_CHANGE_VALUES = {
    "plan": billing.PLANS,
    "billing_interval": billing.INTERVALS,
    "addon_ttlock": ("0", "1"),
    "addon_whitelabel": ("0", "1"),
}
_ARES_MAP = {"buyer_name": "name", "buyer_street": "street", "buyer_city": "city",
             "buyer_zip": "zip", "buyer_dic": "dic"}


def _kc(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def _page(request: Request, owner: int, values: Dict[str, Any], *, errors=None, note: str = "",
          preview: Optional[Dict[str, Any]] = None, status_code: int = 200):
    acc = billing.account(owner)
    ok = values.get("plan") in billing.PLANS and values.get("billing_interval") in billing.INTERVALS
    quote = billing_order.quote(owner, values) if ok else None
    return render(request, "billing_plan.html", {
        "acc": acc,
        "values": values,
        "errors": errors or {},
        "note": note,
        "preview": preview,
        "quote": {k: _kc(v) for k, v in (quote or {}).items()},
        "apartments": billing_order.apartments(owner),
        "founder_offer": billing_order.founder_offer(owner),
        "orderable": bool(acc) and acc["status"] in billing_order.ORDERABLE,
        "trial_ends": validation.fmt_date((acc or {}).get("trial_ends_at") or ""),
        "period_end": validation.fmt_date((acc or {}).get("period_end") or ""),
        "invoices": billing_invoices.for_owner(owner) if acc else [],
    }, status_code=status_code)


def _owner(request: Request) -> Optional[int]:
    return access.owner_id(request)


@router.get("/predplatne")
def plan_page(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner = _owner(request)
    if not billing.enabled() or owner is None:
        return RedirectResponse("/settings", status_code=303)
    query = {"plan": request.query_params.get("plan", ""),
             "interval": request.query_params.get("interval", "")}
    return _page(request, owner, billing_order.form_values(owner, query))


@router.post("/predplatne")
async def plan_order(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner = _owner(request)
    if not billing.enabled() or owner is None:
        return RedirectResponse("/settings", status_code=303)
    form = dict((await request.form()).items())
    values, errors = billing_order.read_form({k: str(v) for k, v in form.items()})
    lang = host_i18n.lang_from_request(request)
    if form.get("do") == "ares":
        note = _ares_fill(owner, values, lang)
        return _page(request, owner, values, note=note)
    if errors:
        return _page(request, owner, values, errors=errors, status_code=400)
    try:
        result = billing_order.place(owner, values)
    except ValueError:
        return _back("/predplatne", err=_flash(request, "billing.order.error.state"))
    key = {"now": "billing.order.done_now"}.get(result["starts"]) or (
        "billing.order.done_trial" if result["date"] else "billing.order.done_pending"
    )
    return _back("/predplatne", msg=_flash(request, key, date=validation.fmt_date(result["date"])))


def _ares_fill(owner: int, values: Dict[str, Any], lang: str) -> str:
    """Fill the blank buyer fields from ARES; the note says what happened."""
    if ares.rate_limited(owner):
        return host_i18n.translate(lang, "ares.rate_limited")
    if not validation.ico_ok(values.get("buyer_ico") or ""):
        return host_i18n.translate(lang, "ares.failure")
    ares.record_lookup(owner)
    data = ares.lookup(values["buyer_ico"])
    if not data:
        return host_i18n.translate(lang, "ares.failure")
    for field, key in _ARES_MAP.items():
        if not str(values.get(field) or "").strip() and data.get(key):
            values[field] = data[key]
    return host_i18n.translate(lang, "billing.order.ares_done")


@router.post("/predplatne/zmena")
async def plan_change(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner = _owner(request)
    acc = billing.account(owner) if owner is not None and billing.enabled() else None
    if acc is None or acc["plan"] is None or acc["status"] not in ("active", "overdue"):
        return _back("/predplatne", err=_flash(request, "billing.order.error.state"))
    form = await request.form()
    field = str(form.get("field") or "")
    value = str(form.get("value") or "")
    if value not in _CHANGE_VALUES.get(field, ()):
        return _back("/predplatne", err=_flash(request, "billing.order.error.state"))
    typed: Any = int(value) if field.startswith("addon_") else value
    confirm = form.get("confirm") == "1"
    result = billing_order.change(owner, field, typed, confirm=confirm)
    if not confirm:
        preview = {**result, "field": field, "value": value,
                   "before": _kc(result["period_total_before"]), "after": _kc(result["period_total_after"]),
                   "supplementary": _kc(result["supplementary_czk"])}
        return _page(request, owner, billing_order.form_values(owner), preview=preview)
    return _back("/predplatne", msg=_flash(request, f"billing.change.saved_{result['when']}"))


@router.post("/predplatne/zrusit")
async def plan_cancel(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner = _owner(request)
    if owner is None or not billing.enabled() or not billing_order.cancel(owner):
        return _back("/predplatne", err=_flash(request, "billing.order.error.state"))
    return _back("/predplatne", msg=_flash(request, "billing.cancel.done"))


@router.post("/predplatne/obnovit")
async def plan_resume(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner = _owner(request)
    if owner is None or not billing.enabled() or not billing_order.resume(owner):
        return _back("/predplatne", err=_flash(request, "billing.order.error.state"))
    return _back("/predplatne", msg=_flash(request, "billing.resume.done"))


@router.get("/predplatne/faktury/{invoice_id}.pdf")
def plan_invoice_pdf(request: Request, invoice_id: int):
    guard = auth.require_login(request)
    if guard:
        return guard
    owner = _owner(request)
    row = billing_invoices.get(invoice_id)
    if row is None or owner is None or row["owner_user_id"] != owner:
        return RedirectResponse("/predplatne", status_code=303)
    from fastapi.responses import Response

    return Response(
        billing_invoices.pdf_bytes(invoice_id), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{row["number"]}.pdf"'},
    )
