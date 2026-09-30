"""Host-only stay-fee overview."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from .. import access, auth, claim, security, stay_fee
from ..templating import render

router = APIRouter(dependencies=[Depends(security.protect_host_post)])


@router.get("/stay-fees")
def stay_fees_list(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard

    today = claim.prague_today()
    default_month = stay_fee.previous_month(today)
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
