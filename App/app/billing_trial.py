"""The 30-day trial (brief 0414): when it starts, the reminders, and what follows.

A new host's trial starts when their email is verified and the account is
activated. UbyPort setup never starts or restarts this clock. At the end the account becomes
active on the plan the host ordered, or paused when they ordered none.
Hosts without a ``billing_account`` row (the "OG" hosts) are never touched.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from . import billing, config, db, validation

TRIAL_DAYS = 30
REMINDER_DAYS = (7, 3, 0)


def period_end(start: date, interval: str) -> date:
    """The last day of a month or year that starts on ``start``."""
    if interval == "year":
        year, month = start.year + 1, start.month
    else:
        year, month = start.year + start.month // 12, start.month % 12 + 1
    last = calendar.monthrange(year, month)[1]
    if start.day > last:
        # 31 January runs to the end of February.
        return date(year, month, last)
    return date(year, month, start.day) - timedelta(days=1)


def verified(owner_user_id: int) -> bool:
    """UbyPort works for this host: a passed connection test or a reported guest."""
    row = db.query_one(
        "SELECT 1 AS n FROM apartment WHERE owner_user_id = ? AND ubyport_verified_at IS NOT NULL "
        "UNION ALL "
        "SELECT 1 AS n FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE a.owner_user_id = ? AND g.submit_state = 'sent' "
        "LIMIT 1",
        (owner_user_id, owner_user_id),
    )
    return row is not None


def activation_dates(stamp: str) -> tuple[date, date]:
    """Thirty calendar days in the configured timezone, including activation day.

    The stored end date is inclusive, as required by finish()/period_end().
    Existing running trials keep their original dates.
    """
    moment = datetime.fromisoformat(stamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    first = moment.astimezone(ZoneInfo(config.TIMEZONE)).date()
    return first, first + timedelta(days=TRIAL_DAYS - 1)


def start(owner_user_id: int, *, today: Optional[date] = None) -> bool:
    """Recover a pending trial from its verified date; never create a billing row."""
    if not billing.enabled():
        return False
    row = db.query_one(
        "SELECT email_verified_at FROM user_account WHERE id = ? AND active = 1",
        (owner_user_id,),
    )
    if row is None or not row["email_verified_at"]:
        return False
    first, last = activation_dates(row["email_verified_at"])
    day = today or datetime.now(ZoneInfo(config.TIMEZONE)).date()
    if first > day:
        return False
    # One conditional write: competing jobs cannot expose a trial with missing
    # dates, or reset a trial that another request already started.
    changed = db.execute(
        "UPDATE billing_account SET status = 'trialing', trial_started_at = ?, "
        "trial_ends_at = ?, updated_at = ? WHERE owner_user_id = ? "
        "AND status = 'trial_pending' AND trial_started_at IS NULL AND trial_ends_at IS NULL",
        (first.isoformat(), last.isoformat(), db.utcnow(), owner_user_id),
    )
    if changed:
        db.audit("billing_status", "trial_pending->trialing", owner_user_id=owner_user_id,
                 actor="system")
    return bool(changed)


def mark_verified(apartment_id: int, owner_user_id: Optional[int]) -> None:
    """Remember a passed UbyPort test without changing the billing clock."""
    db.execute(
        "UPDATE apartment SET ubyport_verified_at = ? WHERE id = ? AND ubyport_verified_at IS NULL",
        (db.utcnow(), apartment_id),
    )


def finish(owner_user_id: int, *, today: date) -> str:
    """End a trial: ``active`` on the ordered plan, else ``paused``."""
    acc = billing.account(owner_user_id)
    ends = date.fromisoformat(acc["trial_ends_at"][:10])
    if acc["plan"] and acc["billing_interval"]:
        start_day = ends + timedelta(days=1)
        db.execute(
            "UPDATE billing_account SET period_start = ?, period_end = ?, updated_at = ? "
            "WHERE owner_user_id = ?",
            (start_day.isoformat(), period_end(start_day, acc["billing_interval"]).isoformat(),
             db.utcnow(), owner_user_id),
        )
        billing.set_status(owner_user_id, "active")
        return "active"
    billing.set_status(owner_user_id, "paused")
    return "paused"


def run(today: Optional[date] = None) -> Dict[str, int]:
    """Daily: start due trials, send the reminders, end finished trials."""
    from . import mail_notify

    counts = {"started": 0, "reminded": 0, "active": 0, "paused": 0}
    if not billing.enabled():
        return counts
    day = today or datetime.now(ZoneInfo(config.TIMEZONE)).date()
    for row in db.query("SELECT owner_user_id FROM billing_account WHERE status = 'trial_pending'"):
        owner = int(row["owner_user_id"])
        if start(owner, today=day):
            counts["started"] += 1
    for row in db.query(
        "SELECT owner_user_id, trial_ends_at, plan FROM billing_account WHERE status = 'trialing'"
    ):
        owner = int(row["owner_user_id"])
        ends = date.fromisoformat(row["trial_ends_at"][:10])
        left = (ends - day).days
        if left < 0:
            counts[finish(owner, today=day)] += 1
        elif left in REMINDER_DAYS and not row["plan"]:
            if mail_notify.billing_trial(owner_user_id=owner, days_left=left,
                                         ends=row["trial_ends_at"][:10]):
                counts["reminded"] += 1
    return counts


def banner(owner_user_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """The one billing line on host pages, or None. Billing off or an OG host: None."""
    if owner_user_id is None or not billing.enabled():
        return None
    acc = billing.account(int(owner_user_id))
    if acc is None:
        return None
    status = acc["status"]
    if status == "trialing" and not acc["plan"]:
        ends = date.fromisoformat(acc["trial_ends_at"][:10])
        left = (ends - datetime.now(ZoneInfo(config.TIMEZONE)).date()).days
        return {"kind": "trial", "warning": left <= 3, "date": validation.fmt_date(ends.isoformat())}
    if status in ("overdue", "paused"):
        return {"kind": status, "warning": True, "date": ""}
    if status == "canceling":
        return {"kind": "canceling", "warning": False,
                "date": validation.fmt_date((acc["period_end"] or "")[:10])}
    return None
