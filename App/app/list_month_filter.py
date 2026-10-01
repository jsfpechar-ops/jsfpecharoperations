"""Shared month picker navigation for host list pages (stay fees, invoices)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from . import stay_fee


def month_bounds(month: date) -> tuple[date, date]:
    """First and last calendar day of the month containing ``month``."""
    return stay_fee.period_bounds("monthly", month.replace(day=1))


def parse_month_param(value: Optional[str]) -> Optional[date]:
    return stay_fee.parse_month(value)


def month_filter_nav(
    selected_month: Optional[date],
    today: date,
    *,
    month_required: bool,
) -> dict:
    """Template context for ``_host_month_filter.html``."""
    max_month = today.replace(day=1)
    anchor = selected_month if selected_month is not None else max_month
    prev_key = stay_fee.month_key(stay_fee.shift_month(anchor, -1))
    next_month = stay_fee.shift_month(anchor, 1)
    if selected_month is None:
        next_key = None
    elif next_month <= max_month:
        next_key = stay_fee.month_key(next_month)
    else:
        next_key = None
    return {
        "month_key": stay_fee.month_key(selected_month) if selected_month else "",
        "max_month_key": stay_fee.month_key(max_month),
        "prev_month_key": prev_key,
        "next_month_key": next_key,
        "filter_active": selected_month is not None,
        "month_required": month_required,
    }
