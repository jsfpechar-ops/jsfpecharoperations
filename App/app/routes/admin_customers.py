"""Admin-only customer overview; all financial actions remain on existing pages."""
from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from .. import admin_customers, billing, billing_analytics, billing_order, config, validation
from ..templating import render
from .admin_accounts import _require_admin
from .admin_helpers import back as _back
from .admin_helpers import flash as _flash

router = APIRouter()
PAGE = "/admin/customers"
STATUSES = ("trial_pending", "trialing", "active", "overdue", "canceling", "paused")


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
        "account": billing.account(user_id),
        "quote": _quote_for(customer),
        "kc": _kc,
    })


def _quote_for(customer):
    if not customer.get("plan"):
        return None
    return billing.quote(
        customer["apartments_billed"] or 0, customer["plan"],
        customer["billing_interval"] or "month",
        ttlock=bool(customer.get("addon_ttlock")),
        whitelabel=bool(customer.get("addon_whitelabel")),
        founder=bool(customer.get("founder")),
        discount_percent=int(customer.get("discount_percent") or 0),
    )


def _kc(haler: int) -> str:
    return f"{int(haler) // 100:,}".replace(",", " ")


@router.post(PAGE + "/{user_id}/sleva")
async def customer_discount(request: Request, user_id: int):
    """0443: set or clear the operator's discount; unpaid invoices are reissued (D1)."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    try:
        percent = int(str(form.get("percent") or "0").strip())
    except ValueError:
        return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.discount.bad_percent"))
    reason = str(form.get("reason") or "").strip()[:200]
    try:
        result = billing.apply_discount(
            user_id, percent, reason=reason,
            actor=f"operator:{account['username']}")
    except ValueError as exc:
        key = f"billing.admin.discount.{exc}"
        return _back(f"{PAGE}/{user_id}", err=_flash(request, key))
    if result["reissued_invoice_ids"]:
        return _back(f"{PAGE}/{user_id}", msg=_flash(request, "billing.admin.discount.done_reissued"))
    return _back(f"{PAGE}/{user_id}", msg=_flash(request, "billing.admin.discount.done"))


@router.post(PAGE + "/{user_id}/plan")
async def customer_plan(request: Request, user_id: int):
    """0442/0444: one plan change for the customer, same engine the host uses."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    field = str(form.get("field") or "").strip()
    if field not in billing.CHANGE_COLUMNS:
        return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.plan.bad_field"))
    raw = str(form.get("value") or "").strip()
    if field in ("apartments", "addon_ttlock", "addon_whitelabel"):
        try:
            value: object = int(raw)
        except ValueError:
            return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.plan.bad_value"))
        if field != "apartments":
            value = int(bool(value))
    elif field in ("plan", "billing_interval"):
        value = raw
    else:
        return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.plan.bad_field"))
    try:
        result = billing_order.change(user_id, field, value, confirm=True,
                                      today=date.today())
    except ValueError:
        return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.plan.refused"))
    billing_analytics.write_month_snapshot()
    return _back(f"{PAGE}/{user_id}", msg=_flash(request, "billing.admin.plan.done"))


@router.post(PAGE + "/{user_id}/stav")
async def customer_status(request: Request, user_id: int):
    """0442: status change through the existing state machine, no bypass."""
    account, guard = _require_admin(request)
    if guard:
        return guard
    form = await request.form()
    new = str(form.get("status") or "").strip()
    if new not in STATUSES:
        return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.status.bad"))
    if new == "canceling":
        ok = billing_order.cancel(user_id)
    elif new == "active":
        acc = billing.account(user_id)
        ok = billing_order.resume(user_id) if acc and acc["status"] == "canceling" \
            else billing.set_status(user_id, "active", actor=f"operator:{account['username']}")
    else:
        ok = billing.set_status(user_id, new, actor=f"operator:{account['username']}")
    if not ok:
        return _back(f"{PAGE}/{user_id}", err=_flash(request, "billing.admin.status.refused"))
    billing_analytics.write_month_snapshot()
    return _back(f"{PAGE}/{user_id}", msg=_flash(request, "billing.admin.status.done"))

