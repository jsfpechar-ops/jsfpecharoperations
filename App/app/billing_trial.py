"""The 30-day trial (brief 0414): when it starts, the reminders, and what follows.

A new host's trial starts when UbyPort is verified for one of their apartments
(a passed connection test or a guest already reported), or 7 days after they
confirmed their e-mail, whichever comes first. At the end the account becomes
active on the plan the host ordered, or paused when they ordered none.
Hosts without a ``billing_account`` row (the "OG" hosts) are never touched.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Dict, Optional

from . import billing, db, validation

TRIAL_DAYS = 30
START_AFTER_DAYS = 7
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


def start(owner_user_id: int, *, today: Optional[date] = None) -> bool:
    """Start the trial of a ``trial_pending`` account; False when there is nothing to start."""
    if not billing.enabled():
        return False
    acc = billing.account(owner_user_id)
    if acc is None or acc["status"] != "trial_pending":
        return False
    if not billing.set_status(owner_user_id, "trialing"):
        return False
    day = today or date.today()
    db.execute(
        "UPDATE billing_account SET trial_started_at = ?, trial_ends_at = ?, updated_at = ? "
        "WHERE owner_user_id = ?",
        (day.isoformat(), (day + timedelta(days=TRIAL_DAYS)).isoformat(), db.utcnow(), owner_user_id),
    )
    return True


def mark_verified(apartment_id: int, owner_user_id: Optional[int]) -> None:
    """A passed UbyPort connection test: remember it and start the trial."""
    db.execute(
        "UPDATE apartment SET ubyport_verified_at = ? WHERE id = ? AND ubyport_verified_at IS NULL",
        (db.utcnow(), apartment_id),
    )
    if owner_user_id is not None:
        start(int(owner_user_id))


def _confirmed_on(owner_user_id: int) -> Optional[date]:
    row = db.query_one(
        "SELECT email_verified_at, created_at FROM user_account WHERE id = ?", (owner_user_id,)
    )
    if row is None:
        return None
    stamp = row["email_verified_at"] or row["created_at"]
    return date.fromisoformat(str(stamp)[:10]) if stamp else None


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
    day = today or date.today()
    for row in db.query("SELECT owner_user_id FROM billing_account WHERE status = 'trial_pending'"):
        owner = int(row["owner_user_id"])
        confirmed = _confirmed_on(owner)
        due = confirmed is not None and confirmed + timedelta(days=START_AFTER_DAYS) <= day
        if (due or verified(owner)) and start(owner, today=day):
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
        left = (ends - date.today()).days
        return {"kind": "trial", "warning": left <= 3, "date": validation.fmt_date(ends.isoformat())}
    if status in ("overdue", "paused"):
        return {"kind": status, "warning": True, "date": ""}
    if status == "canceling":
        return {"kind": "canceling", "warning": False,
                "date": validation.fmt_date((acc["period_end"] or "")[:10])}
    return None
