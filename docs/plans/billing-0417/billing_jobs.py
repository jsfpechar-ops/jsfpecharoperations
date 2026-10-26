"""The daily billing run (brief 0417): trials, new periods, invoices, apartment counts, dunning.

Called by the scheduler's ``billing`` job at 06:00. Nothing happens while
billing is off, and hosts without a ``billing_account`` row (OG hosts) are never
touched. UbyPort reporting does not depend on anything here.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from . import billing, billing_invoices, billing_order, billing_trial, db

log = logging.getLogger(__name__)

# Days after the due date: first reminder, second reminder, read-only.
REMIND_AFTER = 1
SECOND_AFTER = 7
PAUSE_AFTER = 14
BILLED = ("active", "overdue", "canceling")


def _accounts(statuses, owner_user_id: Optional[int] = None) -> list:
    marks = ", ".join("?" for _ in statuses)
    return [dict(r) for r in db.query(
        f"SELECT * FROM billing_account WHERE status IN ({marks}) AND plan IS NOT NULL "
        "AND (? IS NULL OR owner_user_id = ?)",
        (*statuses, owner_user_id, owner_user_id),
    )]


def roll(acc: Dict[str, Any], today: date) -> Optional[str]:
    """Start the next period once the current one has ended. ``None`` when nothing to do."""
    owner = int(acc["owner_user_id"])
    if not acc["period_end"] or today <= date.fromisoformat(acc["period_end"][:10]):
        return None
    if acc["status"] == "canceling":
        billing.set_status(owner, "paused")
        return "paused"
    start = date.fromisoformat(acc["period_end"][:10]) + timedelta(days=1)
    pending = json.loads(acc["pending_change_json"] or "{}")
    values = {
        "plan": pending.get("plan", acc["plan"]),
        "billing_interval": pending.get("billing_interval", acc["billing_interval"]),
        "addon_ttlock": int(pending.get("addon_ttlock", acc["addon_ttlock"])),
        "addon_whitelabel": int(pending.get("addon_whitelabel", acc["addon_whitelabel"])),
    }
    db.execute(
        "UPDATE billing_account SET plan = ?, billing_interval = ?, addon_ttlock = ?, addon_whitelabel = ?, "
        "apartments_billed = ?, period_start = ?, period_end = ?, pending_change_json = NULL, updated_at = ? "
        "WHERE owner_user_id = ?",
        (
            values["plan"], values["billing_interval"], values["addon_ttlock"], values["addon_whitelabel"],
            billing_order.apartments(owner), start.isoformat(),
            billing_trial.period_end(start, values["billing_interval"]).isoformat(), db.utcnow(), owner,
        ),
    )
    db.audit("billing_period", f"{start.isoformat()} {values['plan']} {values['billing_interval']}",
             actor="system", owner_user_id=owner)
    return "rolled"


def invoice_period(acc: Dict[str, Any], today: date) -> Optional[int]:
    """Issue and mail the current period's invoice once; its id when it was new."""
    owner = int(acc["owner_user_id"])
    if not acc["period_start"] or date.fromisoformat(acc["period_start"][:10]) > today:
        return None
    existing = db.query_one(
        "SELECT id FROM platform_invoice WHERE owner_user_id = ? AND period_from = ? AND period_to = ? "
        "AND kind = 'invoice' AND voided = 0",
        (owner, acc["period_start"][:10], acc["period_end"][:10]),
    )
    if existing:
        return None
    invoice_id = billing_invoices.issue_for_period(owner, acc["period_start"][:10], acc["period_end"][:10],
                                                   today=today)
    billing_invoices.send(invoice_id)
    return invoice_id


def follow_apartments(acc: Dict[str, Any], today: date) -> Optional[str]:
    """More active apartments than billed: billed from today. Fewer: from the next period."""
    owner = int(acc["owner_user_id"])
    count = billing_order.apartments(owner)
    if acc["status"] not in ("active", "overdue") or count == int(acc["apartments_billed"]):
        return None
    pending = json.loads(acc["pending_change_json"] or "{}")
    if count < int(acc["apartments_billed"]) and pending.get("apartments") == count:
        return None
    result = billing_order.change(owner, "apartments", count, confirm=True, today=today)
    return result["when"]


def _unpaid_overdue(today: date, owner_user_id: Optional[int] = None) -> list:
    return [dict(r) for r in db.query(
        "SELECT i.*, b.status AS account_status FROM platform_invoice i "
        "JOIN billing_account b ON b.owner_user_id = i.owner_user_id "
        "WHERE i.kind IN ('invoice', 'supplementary') AND i.voided = 0 AND i.paid_on IS NULL "
        "AND i.due_date < ? AND (? IS NULL OR i.owner_user_id = ?) ORDER BY i.id",
        (today.isoformat(), owner_user_id, owner_user_id),
    )]


def dunning(today: date, owner_user_id: Optional[int] = None) -> Dict[str, int]:
    """Reminders 1 and 7 days after the due date; read-only after 14. One mail per stage."""
    from . import mail_notify

    counts = {"overdue": 0, "reminded": 0, "paused": 0}
    for inv in _unpaid_overdue(today, owner_user_id):
        owner = int(inv["owner_user_id"])
        late = (today - date.fromisoformat(inv["due_date"][:10])).days
        if inv["account_status"] == "active" and billing.set_status(owner, "overdue"):
            counts["overdue"] += 1
        stage = None
        if late >= PAUSE_AFTER:
            if billing.set_status(owner, "paused"):
                counts["paused"] += 1
            stage = "paused"
        elif late >= SECOND_AFTER:
            stage = "second"
        elif late >= REMIND_AFTER:
            stage = "reminder"
        if stage and mail_notify.billing_overdue(
            invoice_id=int(inv["id"]), owner_user_id=owner, stage=stage, number=inv["number"],
            amount_czk=int(inv["total_haler"]) // 100, due=inv["due_date"][:10],
            today=today.isoformat(),
        ):
            counts["reminded"] += 1
    return counts


def settle(owner_user_id: int, *, today: Optional[date] = None) -> bool:
    """After a payment: back to active once nothing is overdue. True when the status changed."""
    acc = billing.account(owner_user_id)
    if acc is None or acc["status"] not in ("overdue", "paused") or acc["plan"] is None:
        return False
    day = today or date.today()
    still = db.query_one(
        "SELECT 1 AS n FROM platform_invoice WHERE owner_user_id = ? AND kind IN ('invoice', 'supplementary') "
        "AND voided = 0 AND paid_on IS NULL AND due_date < ?",
        (owner_user_id, day.isoformat()),
    )
    if still:
        return False
    if acc["status"] == "paused":
        # Only an account the dunning paused comes back: its current period was invoiced and is now paid.
        paid = db.query_one(
            "SELECT 1 AS n FROM platform_invoice WHERE owner_user_id = ? AND kind = 'invoice' AND voided = 0 "
            "AND paid_on IS NOT NULL AND period_to >= ?",
            (owner_user_id, day.isoformat()),
        )
        if not paid:
            return False
    return billing.set_status(owner_user_id, "active", actor="system")


def run(today: Optional[date] = None, owner_user_id: Optional[int] = None) -> Dict[str, int]:
    """The whole daily run, or one host's part of it. One account's failure never stops the others."""
    counts = {"rolled": 0, "invoiced": 0, "apartments": 0, "errors": 0}
    if not billing.enabled():
        return counts
    day = today or date.today()
    counts.update({f"trial_{k}": v for k, v in billing_trial.run(day).items()})
    for acc in _accounts(BILLED, owner_user_id):
        try:
            if roll(acc, day):
                counts["rolled"] += 1
                acc = billing.account(int(acc["owner_user_id"]))
                if acc["status"] not in BILLED:
                    continue
            if invoice_period(acc, day):
                counts["invoiced"] += 1
            if follow_apartments(billing.account(int(acc["owner_user_id"])), day):
                counts["apartments"] += 1
        except Exception:  # noqa: BLE001 - one account must not stop the run
            log.exception("billing run failed for owner %s", acc["owner_user_id"])
            db.audit("billing_run_failed", "", actor="system", owner_user_id=acc["owner_user_id"])
            counts["errors"] += 1
    counts.update({f"dunning_{k}": v for k, v in dunning(day, owner_user_id).items()})
    return counts
