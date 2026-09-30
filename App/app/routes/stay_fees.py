"""Host-only stay-fee overview and per-property detail."""
from __future__ import annotations

import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from .. import access, auth, claim, db, security, stay_fee, validation
from ..templating import render
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash
from .admin_helpers import form_str as _form_str

router = APIRouter(dependencies=[Depends(security.protect_host_post)])


def _period_key(cadence: str, month: date) -> str:
    """'2026-08' for a monthly property, '2026-Q3' for a quarterly one."""
    if cadence == "quarterly":
        return f"{month.year:04d}-Q{(month.month - 1) // 3 + 1}"
    return stay_fee.month_key(month)


def _fold_place(value) -> str:
    """A place name with case and diacritics removed, so 'Praha 3' matches 'praha 3'."""
    plain = unicodedata.normalize("NFKD", (value or "").strip())
    return "".join(ch for ch in plain if not unicodedata.combining(ch)).casefold()


def _default_month(today: date) -> date:
    return stay_fee.previous_month(today)


@router.get("/stay-fees")
def stay_fees_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    default_month = _default_month(today)
    selected_month = stay_fee.parse_month(request.query_params.get("month"))
    if selected_month is None:
        selected_month = default_month
    elif selected_month > today.replace(day=1):
        return RedirectResponse(
            f"/stay-fees?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    periods = stay_fee.owner_periods(access.owner_id(request), selected_month)
    rows = []
    for period in periods:
        apartment = period["apartment"]
        group = stay_fee.report_group(apartment, selected_month)
        rows.append({
            **period,
            "total_display": stay_fee.format_czk(period["total_czk"]),
            "issues": stay_fee.report_issues(group, today),
        })

    current_month = today.replace(day=1)
    chip_end = (
        current_month
        if selected_month >= stay_fee.shift_month(current_month, -2)
        else selected_month
    )
    return render(request, "stay_fees.html", {
        "nav": "stay_fees",
        "periods": rows,
        "selected_month": selected_month,
        "month_chips": [
            stay_fee.shift_month(chip_end, offset)
            for offset in (-3, -2, -1, 0)
        ],
    })


@router.get("/stay-fees/{apartment_id}")
def stay_fee_detail(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    default_month = _default_month(today)
    selected_month = stay_fee.parse_month(request.query_params.get("month"))
    if selected_month is None:
        selected_month = default_month
    elif selected_month > today.replace(day=1):
        return RedirectResponse(
            f"/stay-fees/{apartment_id}?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))

    period = stay_fee.property_period(apartment, selected_month)
    group = stay_fee.report_group(apartment, selected_month)
    issues = stay_fee.report_issues(group, today)
    pay = stay_fee.payment_details(group)
    others = [
        item["apartment"]["internal_name"]
        for item in group["periods"]
        if item["apartment"]["id"] != apartment["id"]
    ]
    return render(request, "stay_fee_detail.html", {
        "nav": "stay_fees",
        "apartment": apartment,
        "month_key": stay_fee.month_key(selected_month),
        "period": period,
        "group": group,
        "issues": issues,
        "pay": pay,
        "others": others,
        "key": _period_key(group["cadence"], selected_month),
        "lines": _guest_lines(apartment, period),
        "total_display": stay_fee.format_czk(group["total_czk"]),
    })


def _guest_lines(apartment, period):
    """The property's own guest rows, with the status and the local-resident hint."""
    lines = []
    for line in period["lines"]:
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (line["guest_id"],))
        local_hint = bool(
            guest
            and (guest["res_country"] or "").upper() == validation.CZECH_CODE
            and _fold_place(guest["res_city"])
            and _fold_place(guest["res_city"]) == _fold_place(apartment["addr_obec"])
        )
        if line["status"] == "liable":
            status_key = "stay_fees.status.liable"
        elif line["auto_minor"]:
            status_key = "stay_fees.status.under_18"
        elif line["status"] == "exempt":
            status_key = "stay_fees.status.exempt"
        else:
            status_key = "stay_fees.status.not_subject"
        lines.append({
            **line,
            "status_key": status_key,
            "amount_display": stay_fee.format_czk(line["amount_czk"]),
            "local_hint": local_hint,
            "review": bool(line["auto_minor"] or local_hint),
        })
    return lines


@router.post("/stay-fees/guest-decision")
async def stay_fee_guest_decision(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    form = await request.form()
    apartment_id = _form_str(form, "apartment_id")
    apartment = (
        access.apartment(request, int(apartment_id)) if apartment_id.isdigit() else None
    )
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(
        claim.prague_today()
    )
    back_path = (
        f"/stay-fees/{apartment['id']}?month={stay_fee.month_key(month)}#guests"
        if apartment else "/stay-fees"
    )

    guest_id = _form_str(form, "guest_id")
    guest = access.guest(request, int(guest_id)) if guest_id.isdigit() else None
    if not guest:
        return _back(back_path, err=_flash(request, "flash.error.no_such_guest"))

    decision = _form_str(form, "decision")
    if decision not in ("",) + stay_fee.DECISIONS:
        decision = ""
    reason = _form_str(form, "reason")[:stay_fee.REASON_MAX].strip()
    if decision == "exempt" and len(reason) < 3:
        return _back(back_path, err=_flash(request, "flash.stay_fees.reason_required"))

    db.update("guest", guest["id"], {
        "fee_host_decision": decision or None,
        "fee_host_reason": (reason if decision == "exempt" else None),
        "updated_at": db.utcnow(),
    })
    # The reason stays out of the audit row: the register keeps it, the log does not.
    db.audit("stay_fee_decision", f"guest_id={guest['id']} decision={decision or 'auto'}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.saved"))
