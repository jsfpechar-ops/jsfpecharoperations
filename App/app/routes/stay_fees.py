"""Host-only stay-fee overview and per-property detail."""
from __future__ import annotations

import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from .. import (
    access,
    auth,
    claim,
    db,
    list_month_filter,
    security,
    stay_fee,
    stay_fee_filing,
    validation,
)
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


def _month_filter_template(
    selected_month: date,
    today: date,
    *,
    form_action: str = "/stay-fees",
    filter_id: str = "stay-fee-period",
) -> dict:
    return {
        "filter_id": filter_id,
        "form_action": form_action,
        "period_label_key": "stay_fees.filter.period",
        "hint_label_key": "stay_fees.filter.hint",
        **list_month_filter.month_filter_nav(
            selected_month, today, month_required=True
        ),
    }


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

    return render(request, "stay_fees.html", {
        "nav": "stay_fees",
        "periods": rows,
        "selected_month": selected_month,
        **_month_filter_template(selected_month, today),
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

    correcting = request.query_params.get("correct") == "1"
    live = correcting
    period = stay_fee.property_period(apartment, selected_month, live_only=live)
    group = stay_fee.report_group(apartment, selected_month, live_only=live)
    frozen = bool(period and period.get("frozen") and not correcting)
    issues: list[str] = []
    if not frozen:
        issues = stay_fee.report_issues(group, today)
        if stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"]):
            issues.append("stay_fees.issue.unsigned")
        issues = list(dict.fromkeys(issues))
    pay = stay_fee.payment_details(group) if frozen else None
    return render(request, "stay_fee_detail.html", {
        "nav": "stay_fees",
        "apartment": apartment,
        **_month_filter_template(
            selected_month,
            today,
            form_action=f"/stay-fees/{apartment_id}",
            filter_id="stay-fee-detail-period",
        ),
        "period": period,
        "group": group,
        "issues": issues,
        "pay": pay,
        "others": [],
        "key": _period_key(group["cadence"], selected_month),
        "lines": _guest_lines(apartment, period) if period else [],
        "total_display": stay_fee.format_czk(group["total_czk"]),
        "frozen": frozen,
        "correcting": correcting,
        "filing_version": period.get("version") if period else None,
        "exempt_categories": stay_fee.EXEMPT_CATEGORIES,
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
        rate = period.get("rate_czk", 0)
        amount = line.get("amount_czk", line.get("liable_nights", 0) * rate)
        lines.append({
            **line,
            "amount_czk": amount,
            "status_key": status_key,
            "amount_display": stay_fee.format_czk(amount),
            "local_hint": local_hint,
            "review": bool(line.get("auto_minor") or local_hint),
        })
    return lines


@router.get("/stay-fees/{apartment_id}/pdf")
def stay_fee_pdf_download(apartment_id: int, request: Request):
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
            f"/stay-fees/{apartment_id}/pdf?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))

    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"
    key = _period_key(stay_fee.cadence_of(apartment), selected_month)
    row = stay_fee_filing.latest(apartment["id"], key)
    if not row:
        return _back(back_path, err=_flash(request, "flash.stay_fees.not_saved"))
    pdf = stay_fee_filing.pdf_bytes(row)
    group = stay_fee.report_group(apartment, selected_month)
    db.audit(
        "stay_fee_pdf",
        f"apartment_id={apartment['id']} period={key} total={group['total_czk']}",
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="hlaseni-poplatek-z-pobytu-{key}-{group["vs"]}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/stay-fees/{apartment_id}/csv")
def stay_fee_csv_download(apartment_id: int, request: Request):
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
            f"/stay-fees/{apartment_id}/csv?month={stay_fee.month_key(default_month)}",
            status_code=303,
        )

    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))

    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"
    key = _period_key(stay_fee.cadence_of(apartment), selected_month)
    row = stay_fee_filing.latest(apartment["id"], key)
    if not row:
        return _back(back_path, err=_flash(request, "flash.stay_fees.not_saved"))
    data = stay_fee_filing.csv_bytes(row)
    db.audit("stay_fee_csv", f"apartment_id={apartment['id']} period={key} sealed=1")
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="evidencni-kniha-{key}-{apartment_id}.csv"'
            ),
            "Cache-Control": "no-store",
        },
    )


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
    reservation = access.reservation(request, guest["reservation_id"]) if guest else None
    if not apartment or not guest or not reservation or reservation["apartment_id"] != apartment["id"]:
        return _back(back_path, err=_flash(request, "flash.error.no_such_guest"))

    decision = _form_str(form, "decision")
    if decision not in ("",) + stay_fee.DECISIONS:
        decision = ""
    reason = _form_str(form, "reason")[:stay_fee.REASON_MAX].strip()
    reference = _form_str(form, "reason_reference")[:200].strip()
    if decision == "exempt":
        if reason not in stay_fee.EXEMPT_CATEGORIES:
            return _back(back_path, err=_flash(request, "flash.stay_fees.reason_required"))
        if reason == "local_rule" and len(reference) < 3:
            return _back(back_path, err=_flash(request, "flash.stay_fees.reason_required"))
    else:
        reason = ""
        reference = ""

    db.update("guest", guest["id"], {
        "fee_host_decision": decision or None,
        "fee_host_reason": (reason if decision == "exempt" else None),
        "fee_host_reason_enc": (
            db.encrypt_field(reason) if decision == "exempt" else None
        ),
        "fee_host_reason_reference": (reference if decision == "exempt" else None),
        "updated_at": db.utcnow(),
    })
    # The reason stays out of the audit row: the register keeps it, the log does not.
    db.audit("stay_fee_decision", f"guest_id={guest['id']} decision={decision or 'auto'}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.saved"))


@router.post("/stay-fees/{apartment_id}/scope-ruling")
async def stay_fee_scope_ruling(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    rule = _form_str(form, "rule")
    reference = _form_str(form, "reference")[:200].strip()
    if rule not in stay_fee.SCOPE_RULES or len(reference) < 3:
        return _back(back_path, err=_flash(request, "flash.stay_fees.scope_invalid"))
    db.update("apartment", apartment["id"], {
        "stay_fee_scope_rule": rule,
        "stay_fee_scope_reference": reference,
    })
    db.audit("stay_fee_scope", f"apartment_id={apartment['id']} rule={rule}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.saved"))


@router.post("/stay-fees/{apartment_id}/finalize")
async def stay_fee_finalize(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    today = claim.prague_today()
    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(today)
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    correcting = _form_str(form, "correct") == "1"
    period = stay_fee.property_period(apartment, month, live_only=True)
    group = stay_fee.report_group(apartment, month, live_only=True)
    issues = stay_fee.report_issues(group, today)
    if stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"]):
        issues.append("stay_fees.issue.unsigned")
    if issues:
        return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
    key = stay_fee_filing.period_key(group["cadence"], month)
    if stay_fee_filing.latest(apartment["id"], key) and not correcting:
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    rate = stay_fee.clamp_rate(_form_str(form, "rate_czk") or apartment["stay_fee_rate_czk"])
    collected: dict[int, int] = {}
    if period:
        for line in period["lines"]:
            field = f"collected_{line['guest_id']}"
            raw = _form_str(form, field)
            collected[line["guest_id"]] = int(raw) if raw.isdigit() else line["amount_czk"]
        if period["lines"] and _form_str(form, "confirm_collected") != "1":
            return _back(back_path, err=_flash(request, "flash.stay_fees.confirm_collected"))
    if correcting:
        stay_fee_filing.start_correction(apartment["id"], key)
    version = stay_fee_filing.latest_version(apartment["id"], key) + 1
    stay_fee_filing.save(
        apartment, month, rate_czk=rate, collected=collected, issued_on=today, version=version,
    )
    db.audit("stay_fee_finalize", f"apartment_id={apartment['id']} period={key} v={version}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.period_saved"))
