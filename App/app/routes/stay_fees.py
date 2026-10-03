"""Host-only stay-fee overview and per-property detail."""
from __future__ import annotations

import sqlite3
import unicodedata
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from .. import (
    access,
    auth,
    claim,
    db,
    host_i18n,
    list_filter,
    payments,
    security,
    stay_fee,
    stay_fee_adjustment,
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


def _ui_period_label(request: Request, cadence: str, month: date) -> str:
    """Host-language period name. The filed PDF keeps the Czech label."""
    lang = host_i18n.resolve_language(request)
    if cadence == "quarterly":
        return host_i18n.translate(
            lang,
            "stay_fees.quarter",
            n=(month.month - 1) // 3 + 1,
            year=month.year,
        )
    return f"{host_i18n.translate(lang, f'month.{month.month}')} {month.year}"


STAY_FEE_STATUSES = (
    ("attention", "stay_fees.needs_setup"),
    ("waiting", "stay_fees.status.in_progress"),
    ("ready", "stay_fees.status.ready"),
    ("saved", "stay_fees.status.saved"),
)


def _row_status(row: dict) -> str:
    if row["unset"]:
        return "attention"
    if row.get("frozen"):
        return "saved"
    issues = row["issues"] or []
    if issues == ["stay_fees.issue.period_running"]:
        return "waiting"
    if issues:
        return "attention"
    return "ready"


def _detail_filter(selected_month: date, today: date, apartment_id: int) -> dict:
    """The detail page uses the same control, month only."""
    view = list_filter.ListFilter(selected_month, None, "", "", selected_month)
    return {
        "month_key": stay_fee.month_key(selected_month),
        **list_filter.context(
            view,
            action=f"/stay-fees/{apartment_id}",
            today=today,
            period_label_key="stay_fees.filter.period",
            properties=(),
            statuses=(),
        ),
    }


@router.get("/stay-fees")
def stay_fees_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    owner_id = access.owner_id(request)
    apartments = db.query(
        "SELECT * FROM apartment WHERE owner_user_id IS ? AND archived_at IS NULL "
        "AND active = 1 ORDER BY internal_name, id",
        (owner_id,),
    )
    view = list_filter.parse(
        request.query_params,
        today=today,
        statuses=[value for value, _ in STAY_FEE_STATUSES],
        default_month=_default_month(today),
        apartment_ids=[row["id"] for row in apartments],
    )
    selected_month = view.month
    rows = []
    for period in stay_fee.owner_periods(owner_id, selected_month):
        apartment = period["apartment"]
        group = stay_fee.report_group(apartment, selected_month, period=period)
        issues = stay_fee.report_issues(group, today)
        if not period.get("frozen") and period.get("first") and stay_fee.unsigned_stays(
            apartment["id"], period["first"], period["last"]
        ):
            issues.append("stay_fees.issue.unsigned")
        rows.append({
            **period,
            "total_display": stay_fee.format_czk(period["total_czk"]),
            "issues": issues,
            "unset": False,
        })
    configured = {row["apartment"]["id"] for row in rows}
    for apartment in apartments:
        if apartment["id"] not in configured:
            rows.append({"apartment": apartment, "unset": True, "issues": []})
    for row in rows:
        row["status"] = _row_status(row)
    rows = [
        row for row in rows
        if (view.apartment_id is None or row["apartment"]["id"] == view.apartment_id)
        and (not view.status or row["status"] == view.status)
    ]
    rows.sort(key=lambda row: (row["apartment"]["internal_name"] or "", row["apartment"]["id"]))

    return render(request, "stay_fees.html", {
        "nav": "stay_fees",
        "periods": rows,
        "selected_month": selected_month,
        "has_properties": bool(apartments),
        **list_filter.context(
            view,
            action="/stay-fees",
            today=today,
            period_label_key="stay_fees.filter.period",
            properties=apartments,
            statuses=STAY_FEE_STATUSES,
        ),
    })


def _fee_values(form) -> dict:
    rate = stay_fee.clamp_rate(_form_str(form, "stay_fee_rate_czk", "0"))
    cadence = _form_str(form, "stay_fee_cadence", "monthly")
    values = {
        "stay_fee_rate_czk": rate,
        "stay_fee_cadence": cadence if cadence in stay_fee.CADENCES else "monthly",
        "stay_fee_vs": (
            "".join(ch for ch in _form_str(form, "stay_fee_vs") if ch.isdigit())[:10] or None
        ),
        "stay_fee_authority_name": _form_str(form, "stay_fee_authority_name")[:200].strip() or None,
        "stay_fee_authority_address": _form_str(form, "stay_fee_authority_address")[:200].strip() or None,
        "stay_fee_authority_contact": _form_str(form, "stay_fee_authority_contact")[:200].strip() or None,
        "stay_fee_payee": _form_str(form, "stay_fee_payee")[:60].strip() or None,
        "stay_fee_instruction": _form_str(form, "stay_fee_instruction")[:500].strip() or None,
    }
    raw = None
    if any(key in form for key in ("account_prefix", "account_number", "account_bank")):
        prefix = _form_str(form, "account_prefix")
        number = _form_str(form, "account_number")
        bank = _form_str(form, "account_bank")
        existing = _form_str(form, "_stay_fee_account_existing")
        if payments.preserve_iban_only_account(existing, prefix, number, bank):
            return values
        raw = payments.compose_czech_account(prefix, number, bank)
    else:
        raw = _form_str(form, "stay_fee_council_account")
    if raw is not None:
        if raw.strip():
            account, iban = payments.normalise_account(raw)
            values["stay_fee_council_account"] = account
            values["stay_fee_council_iban"] = iban
        else:
            values["stay_fee_council_account"] = None
            values["stay_fee_council_iban"] = None
    return values


@router.get("/stay-fees/{apartment_id}/setup")
def stay_fee_setup(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment or apartment["archived_at"] or not apartment["active"]:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    return render(request, "stay_fee_setup.html", {
        "nav": "stay_fees",
        "apartment": apartment,
        "account": payments.czech_account_parts(apartment["stay_fee_council_account"] or ""),
    })


@router.post("/stay-fees/{apartment_id}/setup")
async def stay_fee_setup_save(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    try:
        values = _fee_values(form)
    except ValueError:
        return _back(
            f"/stay-fees/{apartment_id}/setup",
            err=_flash(request, "flash.stay_fees.account_invalid"),
        )
    db.update("apartment", apartment_id, values)
    db.audit("stay_fee_setup", f"apartment_id={apartment_id}")
    month = stay_fee.month_key(_default_month(claim.prague_today()))
    if values["stay_fee_rate_czk"] <= 0:
        return _back("/stay-fees", msg=_flash(request, "flash.stay_fees.saved"))
    return _back(
        f"/stay-fees/{apartment_id}?month={month}",
        msg=_flash(request, "flash.stay_fees.saved"),
    )


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
    if not apartment or (
        not stay_fee.is_active(apartment)
        and not stay_fee_filing.covering(apartment["id"], selected_month)
    ):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))

    correcting = request.query_params.get("correct") == "1"
    sealed = stay_fee_filing.covering(apartment["id"], selected_month) if correcting else None
    if correcting and sealed:
        period = stay_fee.property_period(
            apartment,
            stay_fee_filing.period_anchor(sealed),
            live_only=True,
            cadence=sealed["cadence"],
            rate=sealed["rate_czk"],
        )
    else:
        period = stay_fee.property_period(apartment, selected_month, live_only=correcting)
    group = stay_fee.report_group(
        apartment, selected_month, live_only=correcting, period=period
    )
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
        **_detail_filter(selected_month, today, apartment_id),
        "period": period,
        "group": group,
        "ui_period": _ui_period_label(request, group["cadence"], selected_month),
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
        if "res_country" in line:
            guest = line
        else:
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
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"
    row = stay_fee_filing.covering(apartment["id"], selected_month) if apartment else None
    if not apartment or (not row and not stay_fee.is_active(apartment)):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    if not row:
        return _back(back_path, err=_flash(request, "flash.stay_fees.not_saved"))
    pdf = stay_fee_filing.pdf_bytes(row)
    db.audit(
        "stay_fee_pdf",
        f"apartment_id={apartment['id']} period={row['period_key']} total={row['total_due_czk']}",
    )
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="hlaseni-poplatek-z-pobytu-{row["period_key"]}-'
                f'{stay_fee.vs_of(apartment)}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get("/stay-fees/{apartment_id}/csv")
def stay_fee_csv_download(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    # The register CSV lists every guest's document number.
    if not access.identity_visible(request):
        return _back(
            f"/stay-fees/{apartment_id}",
            err=_flash(request, "flash.error.identity_hidden_export"),
        )

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
    back_path = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(selected_month)}"
    row = stay_fee_filing.covering(apartment["id"], selected_month) if apartment else None
    if not apartment or (not row and not stay_fee.is_active(apartment)):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    if not row:
        return _back(back_path, err=_flash(request, "flash.stay_fees.not_saved"))
    data = stay_fee_filing.csv_bytes(row)
    db.audit("stay_fee_csv", f"apartment_id={apartment['id']} period={row['period_key']} sealed=1")
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="evidencni-kniha-{row["period_key"]}-{apartment_id}.csv"'
            ),
            "Cache-Control": "no-store",
        },
    )


def _adjustment_bed_days(form) -> int:
    mode = _form_str(form, "mode")
    if mode == "people":
        people = int(_form_str(form, "people") or "0")
        nights = int(_form_str(form, "nights") or "0")
        if people < 1 or people > 99 or nights < 1 or nights > 366:
            raise ValueError("range")
        return people * nights
    days = int(_form_str(form, "bed_days") or "0")
    if days < 1 or days > 9999:
        raise ValueError("range")
    return days


@router.post("/stay-fees/{apartment_id}/adjustment")
async def stay_fee_adjustment_add(apartment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not stay_fee.is_active(apartment):
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    back = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    correcting = _form_str(form, "correct") == "1"
    period = stay_fee.property_period(apartment, month, live_only=correcting)
    if period and period.get("frozen") and not correcting:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_frozen"))
    direction = _form_str(form, "direction")
    mode = _form_str(form, "mode")
    reason = _form_str(form, "reason").strip()
    if direction not in ("add", "remove") or mode not in ("people", "bed_days") or len(reason) < 3:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_invalid"))
    try:
        days = _adjustment_bed_days(form)
    except ValueError:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_invalid"))
    key = _period_key(stay_fee.cadence_of(apartment), month)
    current = stay_fee_adjustment.net_bed_days(apartment_id, key)
    guest_nights = int((period or {}).get("guest_liable_nights") or 0)
    delta = days if direction == "add" else -days
    if guest_nights + current + delta < 0:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_negative"))
    stay_fee_adjustment.add(
        apartment_id=apartment_id,
        period_key=key,
        direction=direction,
        mode=mode,
        people_count=int(_form_str(form, "people") or "0") if mode == "people" else 0,
        nights=int(_form_str(form, "nights") or "0") if mode == "people" else 0,
        bed_days=days,
        reason=reason[:200],
        created_by=access.owner_id(request),
    )
    db.audit(
        "stay_fee_adjustment",
        f"apartment_id={apartment_id} period={key} direction={direction} days={days}",
    )
    return _back(back, msg=_flash(request, "flash.stay_fees.saved"))


@router.post("/stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo")
async def stay_fee_adjustment_undo(apartment_id: int, adjustment_id: int, request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    apartment = access.apartment(request, apartment_id)
    if not apartment:
        return _back("/stay-fees", err=_flash(request, "flash.error.no_such_apartment"))
    form = await request.form()
    month = stay_fee.parse_month(_form_str(form, "month")) or _default_month(claim.prague_today())
    row = db.query_one(
        "SELECT * FROM stay_fee_adjustment WHERE id = ? AND apartment_id = ?",
        (adjustment_id, apartment_id),
    )
    back = f"/stay-fees/{apartment_id}?month={stay_fee.month_key(month)}"
    if row and row["filing_id"]:
        return _back(back, err=_flash(request, "flash.stay_fees.adjust_sealed"))
    if row and not row["reversed_at"]:
        stay_fee_adjustment.reverse(adjustment_id, access.owner_id(request))
        db.audit("stay_fee_adjustment_undo", f"id={adjustment_id}")
        return _back(back, msg=_flash(request, "flash.stay_fees.saved"))
    return _back(back)


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
    sealed = stay_fee_filing.covering(apartment["id"], month)
    if correcting:
        if not sealed:
            return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
        cadence = sealed["cadence"]
        calc_month = stay_fee_filing.period_anchor(sealed)
    else:
        cadence = stay_fee.cadence_of(apartment)
        calc_month = month
    period = stay_fee.property_period(
        apartment, calc_month, live_only=True, cadence=cadence,
        rate=sealed["rate_czk"] if correcting else None,
    )
    group = stay_fee.report_group(
        apartment, calc_month, live_only=True, period=period, cadence=cadence
    )
    issues = stay_fee.report_issues(group, today)
    if stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"]):
        issues.append("stay_fees.issue.unsigned")
    if issues:
        return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
    key = stay_fee_filing.period_key(group["cadence"], group["first"])
    if stay_fee_filing.latest(apartment["id"], key) and not correcting:
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    # The stored rate must be the one the total was calculated with.
    rate = period["rate_czk"] if period else stay_fee.clamp_rate(apartment["stay_fee_rate_czk"])
    collected: dict[int, int] = {}
    if period:
        for line in period["lines"]:
            field = f"collected_{line['guest_id']}"
            raw = _form_str(form, field)
            parsed = stay_fee.parse_czk_int(raw) if raw else None
            if raw and parsed is None:
                return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
            collected[line["guest_id"]] = parsed if parsed is not None else line["amount_czk"]
        if period["lines"] and _form_str(form, "confirm_collected") != "1":
            return _back(back_path, err=_flash(request, "flash.stay_fees.confirm_collected"))
    try:
        stay_fee_filing.save(
            apartment,
            group["first"],
            rate_czk=rate,
            collected=collected,
            issued_on=today,
            cadence=group["cadence"],
            replacing_id=sealed["id"] if correcting else None,
        )
    except ValueError:
        return _back(back_path, err=_flash(request, "flash.stay_fees.report_blocked"))
    except sqlite3.IntegrityError:
        return _back(back_path, err=_flash(request, "flash.stay_fees.already_saved"))
    db.audit("stay_fee_finalize", f"apartment_id={apartment['id']} period={key}")
    return _back(back_path, msg=_flash(request, "flash.stay_fees.period_saved"))
