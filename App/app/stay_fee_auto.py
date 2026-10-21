"""Monthly stay-fee email (plan: docs/plans/stay-fee-monthly-email.md).

0205: the host's switch. 0206/0207 add the shared confirm step and the daily job.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import claim, db, demo, host_i18n, mail_notify, stay_fee, stay_fee_filing

log = logging.getLogger("ubyhost.stay_fee_auto")


def emails_enabled(user_id: int) -> bool:
    row = db.query_one("SELECT stay_fee_emails_opt_out FROM user_account WHERE id = ?", (user_id,))
    return bool(row) and not row["stay_fee_emails_opt_out"]


def set_emails_enabled(user_id: int, enabled: bool, *, actor: str) -> None:
    db.execute(
        "UPDATE user_account SET stay_fee_emails_opt_out = ?, stay_fee_emails_opt_out_at = ? "
        "WHERE id = ?",
        (0 if enabled else 1, None if enabled else db.utcnow(), user_id),
    )
    db.audit("stay_fee_emails_on" if enabled else "stay_fee_emails_off", f"user_id={user_id} by={actor}")


def workspace_has_fee_property(user_id: int) -> bool:
    row = db.query_one(
        "SELECT 1 AS n FROM apartment WHERE owner_user_id = ? AND archived_at IS NULL "
        "AND COALESCE(stay_fee_rate_czk, 0) > 0 LIMIT 1",
        (user_id,),
    )
    return bool(row)


def period_label(lang: str, cadence: str, month: date) -> str:
    """Host-language period name, the same wording as the Stay fee page."""
    if cadence == "quarterly":
        return host_i18n.translate(
            lang,
            "stay_fees.quarter",
            n=(month.month - 1) // 3 + 1,
            year=month.year,
        )
    return f"{host_i18n.translate(lang, f'month.{month.month}')} {month.year}"


def check(apartment, month, today, *, cadence=None, rate=None) -> dict:
    """Everything that blocks sealing ``month``. The button and the job both call this."""
    cadence = cadence or stay_fee.cadence_of(apartment)
    period = stay_fee.property_period(apartment, month, live_only=True, cadence=cadence, rate=rate)
    group = stay_fee.report_group(apartment, month, live_only=True, period=period, cadence=cadence)
    issues = stay_fee.report_issues(group, today)
    if stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"], period):
        issues.append("stay_fees.issue.unsigned")
    return {"period": period, "group": group, "issues": issues,
            "key": stay_fee_filing.period_key(group["cadence"], group["first"])}


def confirm(apartment, month, today) -> Optional[int]:
    """Seal a clean period with the fee as calculated (job only). None when blocked or saved."""
    checked = check(apartment, month, today)
    if checked["issues"] or stay_fee_filing.latest(apartment["id"], checked["key"]):
        return None
    period, group = checked["period"], checked["group"]
    rate = period["rate_czk"] if period else stay_fee.clamp_rate(apartment["stay_fee_rate_czk"])
    collected = {line["guest_id"]: line["amount_czk"] for line in (period or {}).get("lines") or []}
    try:
        filing_id = stay_fee_filing.save(apartment, group["first"], rate_czk=rate,
                                         collected=collected, issued_on=today,
                                         cadence=group["cadence"])
    except (ValueError, sqlite3.IntegrityError):
        return None
    db.audit("stay_fee_auto_finalize", f"apartment_id={apartment['id']} period={checked['key']}")
    return filing_id


def due_month(cadence: str, today: date) -> Optional[date]:
    """First month of the period that ended most recently, when the job seals it.

    Sealed from the 2nd day after the period ends until the 15th: blocked periods
    are retried until then, and an old period is never sealed out of the blue.
    """
    if cadence == "quarterly":
        this_quarter = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        month = stay_fee.shift_month(this_quarter, -3)
    else:
        month = stay_fee.previous_month(today)
    _, last = stay_fee.period_bounds(cadence, month)
    if last + timedelta(days=2) <= today <= last + timedelta(days=15):
        return month
    return None


def run(today: Optional[date] = None) -> dict:
    """The daily job (0207): seal clean periods, queue the reports and the blocked mails."""
    today = today or claim.prague_today()
    counts = {"confirmed": 0, "reports": 0, "blocked": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat()
    hosts = db.query(
        "SELECT id FROM user_account WHERE role = 'host' AND deletion_due_at IS NULL "
        "AND COALESCE(stay_fee_emails_opt_out, 0) = 0"
    )
    for host in hosts:
        apartments = db.query(
            "SELECT * FROM apartment WHERE owner_user_id = ? AND archived_at IS NULL",
            (host["id"],),
        )
        for apartment in apartments:
            try:
                _run_apartment(apartment, today, cutoff, counts)
            except Exception:
                log.exception("stay-fee mail failed for apartment %s", apartment["id"])
    return counts


def _run_apartment(apartment, today: date, cutoff: str, counts: dict) -> None:
    if not stay_fee.is_active(apartment) or demo.is_demo_apartment(apartment):
        return
    cadence = stay_fee.cadence_of(apartment)
    month = due_month(cadence, today)
    if month and not stay_fee_filing.latest(apartment["id"], stay_fee_filing.period_key(cadence, month)):
        if confirm(apartment, month, today):
            counts["confirmed"] += 1
        else:
            checked = check(apartment, month, today, cadence=cadence)
            if checked["issues"] and mail_notify.queue_stay_fee_blocked(
                apartment, checked["group"], checked["issues"]
            ):
                counts["blocked"] += 1
    # Live filings saved or sealed in the last 3 days. The mail key includes the
    # version, so a repeated run sends nothing twice and a correction sends again.
    rows = db.query(
        "SELECT * FROM stay_fee_filing WHERE apartment_id = ? AND superseded_at IS NULL "
        "AND created_at >= ?",
        (apartment["id"], cutoff),
    )
    for row in rows:
        if mail_notify.queue_stay_fee_report(apartment, row):
            counts["reports"] += 1
