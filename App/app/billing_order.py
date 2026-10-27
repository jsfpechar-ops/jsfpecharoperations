"""Ordering and changing a plan (brief 0416): the rules behind /predplatne.

Invoices only: the host orders, UbyHost invoices, the host pays by bank
transfer. Nothing here knows about a card or a payment gateway.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Tuple

from . import billing, billing_invoices, billing_trial, db, mail, signup_selection, validation

BUYER_FIELDS = (
    "buyer_name", "buyer_street", "buyer_city", "buyer_zip", "buyer_ico", "buyer_dic", "buyer_email",
)
# Statuses in which the host orders a plan; after that, changes go through apply_change.
ORDERABLE = ("trial_pending", "trialing", "paused")


def apartments(owner_user_id: int) -> int:
    """Billed apartments: the active ones, at least one."""
    return max(1, billing.apartment_count(owner_user_id))


def form_values(owner_user_id: int, query: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """What the order form starts with: the saved order, else the host's first legal entity.

    ``query`` may carry ``plan`` and ``interval`` from the /cenik buttons.
    """
    acc = billing.account(owner_user_id) or {}
    # Preferences prefill an unordered account only. The actual property count
    # remains the sole source for quotes and invoices.
    selected = signup_selection.for_owner(owner_user_id) if not acc.get("plan") else {}
    query = {**selected, **{k: v for k, v in (query or {}).items() if v}}
    plan = query.get("plan") if query.get("plan") in billing.PLANS else acc.get("plan") or "standard"
    interval = (
        query.get("interval") if query.get("interval") in billing.INTERVALS
        else acc.get("billing_interval") or "year"
    )
    values: Dict[str, Any] = {
        "plan": plan,
        "billing_interval": interval,
        "addon_ttlock": bool(acc.get("addon_ttlock")) if acc.get("plan") else query.get("ttlock") == "1",
        "addon_whitelabel": bool(acc.get("addon_whitelabel")),
    }
    for field in BUYER_FIELDS:
        values[field] = acc.get(field) or ""
    if not values["buyer_name"]:
        entity = db.query_one(
            "SELECT name, ico, dic, contact_email FROM legal_entity WHERE owner_user_id = ? ORDER BY id LIMIT 1",
            (owner_user_id,),
        )
        if entity:
            values.update(buyer_name=entity["name"] or "", buyer_ico=entity["ico"] or "",
                          buyer_dic=entity["dic"] or "", buyer_email=entity["contact_email"] or "")
    if not values["buyer_email"]:
        row = db.query_one("SELECT email FROM user_account WHERE id = ?", (owner_user_id,))
        values["buyer_email"] = (row["email"] or "") if row else ""
    return values


def read_form(form: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """The posted order and its errors as ``{field: copy key}``."""
    values: Dict[str, Any] = {
        "plan": form.get("plan", ""),
        "billing_interval": form.get("billing_interval", ""),
        "addon_ttlock": form.get("addon_ttlock") == "1",
        "addon_whitelabel": form.get("addon_whitelabel") == "1",
    }
    for field in BUYER_FIELDS:
        values[field] = (form.get(field) or "").strip()
    values["buyer_zip"] = values["buyer_zip"].replace(" ", "")
    errors: Dict[str, str] = {}
    if values["plan"] not in billing.PLANS:
        errors["plan"] = "billing.order.error.plan"
    if values["billing_interval"] not in billing.INTERVALS:
        errors["billing_interval"] = "billing.order.error.plan"
    for field in ("buyer_name", "buyer_street", "buyer_city"):
        if not values[field]:
            errors[field] = "billing.order.error.required"
    if not (len(values["buyer_zip"]) == 5 and values["buyer_zip"].isdigit()):
        errors["buyer_zip"] = "billing.order.error.zip"
    if values["buyer_ico"] and not validation.ico_ok(values["buyer_ico"]):
        errors["buyer_ico"] = "billing.order.error.ico"
    email = mail.normalise_email(values["buyer_email"])
    if not email:
        errors["buyer_email"] = "billing.order.error.email"
    values["buyer_email"] = email or values["buyer_email"]
    return values, errors


def founder_offer(owner_user_id: int) -> bool:
    """The founder price can apply: the host holds a slot, or one is still free."""
    acc = billing.account(owner_user_id) or {}
    return bool(acc.get("founder")) or billing.founder_slots_left() > 0


def quote(owner_user_id: int, values: Dict[str, Any]) -> Dict[str, int]:
    founder = values["billing_interval"] == "year" and founder_offer(owner_user_id)
    return billing.quote(
        apartments(owner_user_id), values["plan"], values["billing_interval"],
        ttlock=values["addon_ttlock"], whitelabel=values["addon_whitelabel"], founder=founder,
    )


def place(owner_user_id: int, values: Dict[str, Any], *, today: Optional[date] = None) -> Dict[str, Any]:
    """Save the order. In a trial it starts when the trial ends; when paused it starts today
    and the first invoice is issued and mailed at once."""
    acc = billing.account(owner_user_id)
    if acc is None:
        raise ValueError("og")
    if acc["status"] not in ORDERABLE:
        raise ValueError("already_ordered")
    day = today or date.today()
    founder = 1 if acc["founder"] else 0
    if values["billing_interval"] == "year" and not founder:
        founder = 1 if billing.claim_founder_slot(owner_user_id) is not None else 0
    db.execute(
        "UPDATE billing_account SET plan = ?, billing_interval = ?, addon_ttlock = ?, "
        "addon_whitelabel = ?, founder = ?, apartments_billed = ?, pending_change_json = NULL, "
        "buyer_name = ?, buyer_street = ?, buyer_city = ?, buyer_zip = ?, buyer_ico = ?, "
        "buyer_dic = ?, buyer_email = ?, updated_at = ? WHERE owner_user_id = ?",
        (
            values["plan"], values["billing_interval"], int(values["addon_ttlock"]),
            int(values["addon_whitelabel"]), founder, apartments(owner_user_id),
            *(values[field] or None for field in BUYER_FIELDS), db.utcnow(), owner_user_id,
        ),
    )
    db.audit("billing_order", f"{values['plan']} {values['billing_interval']}", actor="host",
             owner_user_id=owner_user_id)
    if acc["status"] != "paused":
        return {"starts": "trial_end", "date": (acc["trial_ends_at"] or "")[:10], "invoice_id": None}
    end = billing_trial.period_end(day, values["billing_interval"])
    db.execute(
        "UPDATE billing_account SET period_start = ?, period_end = ?, updated_at = ? WHERE owner_user_id = ?",
        (day.isoformat(), end.isoformat(), db.utcnow(), owner_user_id),
    )
    billing.set_status(owner_user_id, "active", actor="host")
    invoice_id = billing_invoices.issue_for_period(owner_user_id, day.isoformat(), end.isoformat(), today=day)
    billing_invoices.send(invoice_id)
    return {"starts": "now", "date": day.isoformat(), "invoice_id": invoice_id}


def change(owner_user_id: int, field: str, value: Any, *, confirm: bool,
           today: Optional[date] = None) -> Dict[str, Any]:
    """Preview or save one change; a rise on an annual plan may issue a supplementary invoice."""
    day = today or date.today()
    result = billing.apply_change(owner_user_id, {field: value}, today=day, confirm=confirm)
    result["invoice_id"] = None
    if confirm and result["supplementary_czk"]:
        acc = billing.account(owner_user_id)
        result["invoice_id"] = billing_invoices.issue_supplementary(
            owner_user_id,
            amount_czk=result["supplementary_czk"],
            description=f"Doplatek za změnu předplatného od {validation.fmt_date(day.isoformat())}",
            period_from=day.isoformat(),
            period_to=(acc["period_end"] or day.isoformat())[:10],
            today=day,
        )
        billing_invoices.send(result["invoice_id"])
    return result


def cancel(owner_user_id: int) -> bool:
    """End at the period's end: active -> canceling."""
    if not billing.set_status(owner_user_id, "canceling", actor="host"):
        return False
    db.execute("UPDATE billing_account SET cancel_at_period_end = 1, updated_at = ? WHERE owner_user_id = ?",
               (db.utcnow(), owner_user_id))
    return True


def resume(owner_user_id: int) -> bool:
    """Take a cancellation back before the period ends: canceling -> active."""
    if not billing.set_status(owner_user_id, "active", actor="host"):
        return False
    db.execute("UPDATE billing_account SET cancel_at_period_end = 0, updated_at = ? WHERE owner_user_id = ?",
               (db.utcnow(), owner_user_id))
    return True
