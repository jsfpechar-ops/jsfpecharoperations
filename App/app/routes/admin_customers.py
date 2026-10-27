"""Admin-only customer overview; all financial actions remain on existing pages."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from .. import admin_customers, billing, config, validation
from ..templating import render
from .admin_accounts import _require_admin

router = APIRouter()
PAGE = "/admin/customers"


def _cursor(value: str) -> int:
    return int(value) if value.isascii() and value.isdigit() and len(value) <= 18 else 0


@router.get(PAGE)
def customer_list(request: Request, q: str = "", state: str = "", plan: str = "",
                  after: str = "", before: str = ""):
    _account, guard = _require_admin(request)
    if guard:
        return guard
    day = datetime.now(ZoneInfo(config.TIMEZONE)).date()
    values = admin_customers.filters(q, state, plan)
    rows = admin_customers.customers(values, after=_cursor(after), before=_cursor(before), today=day)

    def href(**extra):
        return PAGE + "?" + urlencode({**values, **extra})

    customers = rows["customers"]
    return render(request, "admin_customers.html", {
        **rows, **values, "states": admin_customers.STATES,
        "summary": admin_customers.summary(day), "href": href,
        "older_url": href(after=customers[-1]["id"]) if rows["older"] else "",
        "newer_url": href(before=customers[0]["id"]) if rows["newer"] else "",
        "today": day.isoformat(), "billing_enabled": billing.enabled(),
    })


@router.get(PAGE + "/{user_id}")
def customer_detail(request: Request, user_id: int):
    _account, guard = _require_admin(request)
    if guard:
        return guard
    customer = admin_customers.detail(user_id)
    if customer is None:
        raise HTTPException(status_code=404)
    return render(request, "admin_customer.html", {
        "customer": customer, "fmt_date": validation.fmt_date,
        "billing_enabled": billing.enabled(),
    })
