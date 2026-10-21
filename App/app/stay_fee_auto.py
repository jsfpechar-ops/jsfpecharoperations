"""Monthly stay-fee email (plan: docs/plans/stay-fee-monthly-email.md).

0205: the host's switch. 0206/0207 add the shared confirm step and the daily job.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from . import db, host_i18n, stay_fee, stay_fee_filing


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
