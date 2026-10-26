"""The operator's billing page /admin/fakturace (brief 0419). Admins only.

The month's invoices, what is unpaid, payments waiting for a decision, the
ČSOB statement upload, mark paid by hand, storno, and the accountant's ZIP.
Works without JavaScript: every action is a plain form post.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from starlette.datastructures import UploadFile

from .. import bank_import, billing_admin, billing_invoices, security, validation
from ..templating import render
from .admin_accounts import _require_admin
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash

router = APIRouter(dependencies=[Depends(security.protect_host_post)])

PAGE = "/admin/fakturace"
STATEMENT_MAX_BYTES = 5 * 1024 * 1024


def _kc(haler: int) -> str:
    return f"{int(haler) // 100:,}".replace(",", " ")


@router.get(PAGE)
def billing_admin_page(request: Request, mesic: str = ""):
    account, guard = _require_admin(request)
    if guard:
        return guard
    month = billing_admin.month_or_current(mesic)
    rows = billing_admin.invoices(month)
    unpaid = billing_admin.unpaid()
    return render(request, "admin_billing.html", {
        "month": month,
        "invoices": rows,
        "unpaid": unpaid,
        "unpaid_total": _kc(sum(int(r["total_haler"]) for r in unpaid)),
        "payments": bank_import.unmatched(),
        "accounts": billing_admin.accounts_by_status(),
        "kc": _kc,
        "fmt_date": validation.fmt_date,
        "today": date.today().isoformat(),
    })


@router.post(f"{PAGE}/vypis")
async def billing_admin_statement(request: Request):
    account, guard = _require_admin(request)
    if guard:
        return guard
    upload = (await request.form()).get("statement")
    if not (isinstance(upload, UploadFile) and upload.filename):
        return _back(PAGE, err=_flash(request, "billing.admin.statement.missing"))
    data = await upload.read(STATEMENT_MAX_BYTES + 1)
    if len(data) > STATEMENT_MAX_BYTES:
        return _back(PAGE, err=_flash(request, "billing.admin.statement.unreadable"))
    try:
        counts = bank_import.import_statement(data, actor=account["username"])
    except bank_import.StatementError:
        return _back(PAGE, err=_flash(request, "billing.admin.statement.unreadable"))
    return _back(PAGE, msg=_flash(request, "billing.admin.statement.done", **counts))


@router.post(PAGE + "/{invoice_id}/zaplaceno")
async def billing_admin_mark_paid(request: Request, invoice_id: int):
    account, guard = _require_admin(request)
    if guard:
        return guard
    paid_on = str((await request.form()).get("paid_on") or "").strip()
    try:
        date.fromisoformat(paid_on)
    except ValueError:
        return _back(PAGE, err=_flash(request, "billing.admin.paid.bad_date"))
    if not bank_import.mark_paid_manually(invoice_id, paid_on=paid_on, actor=account["username"]):
        return _back(PAGE, err=_flash(request, "billing.admin.paid.not_open"))
    return _back(PAGE, msg=_flash(request, "billing.admin.paid.done"))


@router.post(PAGE + "/{invoice_id}/storno")
async def billing_admin_storno(request: Request, invoice_id: int):
    account, guard = _require_admin(request)
    if guard:
        return guard
    reason = str((await request.form()).get("reason") or "").strip()[:200]
    if not reason:
        return _back(PAGE, err=_flash(request, "billing.admin.storno.reason_missing"))
    try:
        # Not mailed: the invoice mail asks for payment. The host sees the storno on /predplatne.
        billing_invoices.storno(invoice_id, reason=reason, today=date.today())
    except ValueError as exc:
        return _back(PAGE, err=_flash(request, f"billing.admin.storno.refused_{exc}"))
    return _back(PAGE, msg=_flash(request, "billing.admin.storno.done"))


@router.get(PAGE + "/{invoice_id}.pdf")
def billing_admin_pdf(request: Request, invoice_id: int):
    account, guard = _require_admin(request)
    if guard:
        return guard
    row = billing_invoices.get(invoice_id)
    if row is None:
        return _back(PAGE)
    return Response(billing_invoices.pdf_bytes(invoice_id), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{row["number"]}.pdf"'})


@router.get(PAGE + "/export")
def billing_admin_export(request: Request, mesic: str = ""):
    account, guard = _require_admin(request)
    if guard:
        return guard
    month = billing_admin.month_or_current(mesic)
    return Response(billing_admin.export_zip(month), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="ubyhost-faktury-{month}.zip"'})
