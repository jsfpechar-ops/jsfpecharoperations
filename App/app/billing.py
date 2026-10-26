"""UbyHost's own billing, phase 1: bank transfer on an invoice (brief 0411).

Other code reads ``entitlements()`` and nothing else. Nothing here knows about
a payment gateway: none is chosen yet. Off unless ``UBYHOST_BILLING_ENABLED``;
while off, and for hosts who predate billing (no ``billing_account`` row),
everyone is active Standard, exactly as before.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional

from . import config, db

STATUSES = ("trial_pending", "trialing", "active", "overdue", "canceling", "paused")
TRANSITIONS = {
    "trial_pending": {"trialing"},
    "trialing": {"active", "paused"},
    "active": {"overdue", "canceling"},
    "overdue": {"active", "paused"},
    "canceling": {"paused"},
    "paused": {"active"},
}
PLANS = ("standard", "max")
INTERVALS = ("month", "year")

# Final prices in whole Kč. Bands: apartments 1-4, 5-9, 10 and up; each band
# prices only the apartments inside it.
BAND_TOPS = (4, 9)
BASE = {"month": (149, 119, 99), "year": (1190, 950, 790)}
MAX_EXTRA = {"month": (79, 59, 39), "year": (760, 570, 370)}
TTLOCK = {"month": 49, "year": 470}
WHITELABEL = {"month": 590, "year": 5660}
FOUNDER_YEAR = 890
# A supplementary amount under this is carried to the next invoice instead.
SUPPLEMENTARY_MIN_CZK = 50

CHANGE_COLUMNS = {
    "apartments": "apartments_billed",
    "plan": "plan",
    "billing_interval": "billing_interval",
    "addon_ttlock": "addon_ttlock",
    "addon_whitelabel": "addon_whitelabel",
}


def enabled() -> bool:
    return bool(config.BILLING_ENABLED)


def _band(index: int) -> int:
    """0, 1 or 2 for the 1-based position of an apartment."""
    if index <= BAND_TOPS[0]:
        return 0
    if index <= BAND_TOPS[1]:
        return 1
    return 2


def graduated(count: int, rates) -> int:
    return sum(rates[_band(i)] for i in range(1, count + 1))


def quote(
    apartments: int,
    plan: str,
    interval: str,
    *,
    ttlock: bool = False,
    whitelabel: bool = False,
    founder: bool = False,
) -> Dict[str, int]:
    """Whole-Kč amounts for one period (a month or a year). Prices are final."""
    if plan not in PLANS or interval not in INTERVALS:
        raise ValueError(f"unknown plan or interval: {plan} {interval}")
    n = max(0, int(apartments))
    if founder and interval == "year":
        base = FOUNDER_YEAR * n
    else:
        base = graduated(n, BASE[interval])
    extra = graduated(n, MAX_EXTRA[interval]) if plan == "max" else 0
    lock = TTLOCK[interval] * n if ttlock and plan != "max" else 0
    brand = WHITELABEL[interval] if whitelabel else 0
    return {
        "base": base,
        "max": extra,
        "ttlock": lock,
        "whitelabel": brand,
        "total": base + extra + lock + brand,
    }


@dataclass(frozen=True)
class Entitlements:
    status: str
    plan: str
    # Never False: a paused account still reports guests who are already registered.
    ubyport_submit: bool = True
    read_only: bool = False
    ical_import: bool = True
    ai_multiplier: int = 1  # 0 off, 1 base limits, 3 Max
    ttlock: bool = True
    whitelabel: bool = False
    priority_support: bool = False


UNBILLED = Entitlements(status="active", plan="standard")


def account(owner_user_id: int) -> Optional[Dict[str, Any]]:
    row = db.query_one("SELECT * FROM billing_account WHERE owner_user_id = ?", (owner_user_id,))
    return dict(row) if row else None


def ensure_account(owner_user_id: int) -> Dict[str, Any]:
    """The host's billing row, created as trial_pending the first time."""
    db.execute(
        "INSERT INTO billing_account (owner_user_id, status, updated_at) "
        "VALUES (?, 'trial_pending', ?) ON CONFLICT(owner_user_id) DO NOTHING",
        (owner_user_id, db.utcnow()),
    )
    return account(owner_user_id)


def entitlements(owner_user_id: int) -> Entitlements:
    if not enabled():
        return UNBILLED
    acc = account(owner_user_id)
    if acc is None:
        return UNBILLED
    status = acc["status"]
    plan = acc["plan"] or "standard"
    if status == "paused":
        return Entitlements(
            status=status, plan=plan, read_only=True, ical_import=False,
            ai_multiplier=0, ttlock=False,
        )
    if status in ("trial_pending", "trialing"):
        return Entitlements(status=status, plan="standard")
    is_max = plan == "max"
    return Entitlements(
        status=status,
        plan=plan,
        ai_multiplier=3 if is_max else 1,
        ttlock=is_max or bool(acc["addon_ttlock"]),
        whitelabel=bool(acc["addon_whitelabel"]),
        priority_support=is_max,
    )


def set_status(owner_user_id: int, new: str, *, actor: str = "system") -> bool:
    """Move the account to ``new`` if the state machine allows it; False otherwise."""
    if new not in STATUSES:
        raise ValueError(f"unknown status: {new}")
    with db.immediate() as cur:
        cur.execute("SELECT status FROM billing_account WHERE owner_user_id = ?", (owner_user_id,))
        row = cur.fetchone()
        if row is None or new not in TRANSITIONS[row["status"]]:
            return False
        old = row["status"]
        cur.execute(
            "UPDATE billing_account SET status = ?, updated_at = ? WHERE owner_user_id = ?",
            (new, db.utcnow(), owner_user_id),
        )
    db.audit("billing_status", f"{old}->{new}", actor=actor, owner_user_id=owner_user_id)
    return True


def apartment_count(owner_user_id: int) -> int:
    """Apartments that count for billing: the host's active ones."""
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE owner_user_id = ? AND active = 1",
        (owner_user_id,),
    )
    return int(row["n"]) if row else 0


def _whole_months(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day < start.day:
        months -= 1
    return max(0, months)


def _period_total(state: Dict[str, Any]) -> int:
    return quote(
        state["apartments"],
        state["plan"],
        state["billing_interval"],
        ttlock=bool(state["addon_ttlock"]),
        whitelabel=bool(state["addon_whitelabel"]),
        founder=bool(state["founder"]),
    )["total"]


def apply_change(
    owner_user_id: int,
    change: Dict[str, Any],
    *,
    today: Optional[date] = None,
    confirm: bool = False,
    actor: str = "host",
) -> Dict[str, Any]:
    """Preview (``confirm=False``) or save one change to an ordered plan.

    ``change`` has exactly one key from ``CHANGE_COLUMNS``. A rise (more
    apartments, Max, an add-on switched on) starts now; on an annual plan it
    costs the difference for the remaining whole months, billed on a
    supplementary invoice, or carried to the next invoice when under 50 Kč.
    Anything else (fewer apartments, back to Standard, an add-on off, another
    interval) waits for the next period. Issuing the invoice is not done here.
    """
    if len(change) != 1 or next(iter(change)) not in CHANGE_COLUMNS:
        raise ValueError("one change at a time, from CHANGE_COLUMNS")
    acc = account(owner_user_id)
    if acc is None or acc["plan"] is None:
        raise ValueError("no ordered plan to change")
    field, value = next(iter(change.items()))
    current = {
        "apartments": acc["apartments_billed"],
        "plan": acc["plan"],
        "billing_interval": acc["billing_interval"],
        "addon_ttlock": acc["addon_ttlock"],
        "addon_whitelabel": acc["addon_whitelabel"],
        "founder": acc["founder"],
    }
    target = {**current, field: value}
    before = _period_total(current)
    after = _period_total(target)
    if after == before and field != "billing_interval":
        when = "none"
    elif after > before and field != "billing_interval":
        when = "now"
    else:
        when = "next_period"
    months = 0
    difference = 0
    if when == "now" and current["billing_interval"] == "year" and acc["period_end"]:
        months = _whole_months(today or date.today(), date.fromisoformat(acc["period_end"][:10]))
        difference = round((after - before) * months / 12)
    supplementary = difference if difference >= SUPPLEMENTARY_MIN_CZK else 0
    carry = difference - supplementary
    result = {
        "when": when,
        "period_total_before": before,
        "period_total_after": after,
        "months": months,
        "supplementary_czk": supplementary,
        "carry_czk": carry,
    }
    if not confirm or when == "none":
        return result
    if when == "now":
        column = CHANGE_COLUMNS[field]
        db.execute(
            f"UPDATE billing_account SET {column} = ?, carry_czk = carry_czk + ?, updated_at = ? "
            "WHERE owner_user_id = ?",
            (value, carry, db.utcnow(), owner_user_id),
        )
    else:
        pending = json.loads(acc["pending_change_json"] or "{}")
        pending[field] = value
        db.execute(
            "UPDATE billing_account SET pending_change_json = ?, updated_at = ? WHERE owner_user_id = ?",
            (json.dumps(pending, sort_keys=True), db.utcnow(), owner_user_id),
        )
    db.audit("billing_change", f"{field} {when}", actor=actor, owner_user_id=owner_user_id)
    return result


def founder_slots_left() -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM founder_slot")
    used = int(row["n"]) if row else 0
    return max(0, int(config.FOUNDER_SLOTS) - used)


def claim_founder_slot(owner_user_id: int) -> Optional[int]:
    """The host's founder slot number, claiming the next one; None when all are gone."""
    with db.immediate() as cur:
        cur.execute("SELECT slot FROM founder_slot WHERE owner_user_id = ?", (owner_user_id,))
        mine = cur.fetchone()
        if mine is not None:
            return int(mine["slot"])
        cur.execute("SELECT COUNT(*) AS n, COALESCE(MAX(slot), 0) AS top FROM founder_slot")
        row = cur.fetchone()
        if int(row["n"]) >= int(config.FOUNDER_SLOTS):
            return None
        slot = int(row["top"]) + 1
        cur.execute(
            "INSERT INTO founder_slot (slot, owner_user_id, claimed_at) VALUES (?, ?, ?)",
            (slot, owner_user_id, db.utcnow()),
        )
    return slot
