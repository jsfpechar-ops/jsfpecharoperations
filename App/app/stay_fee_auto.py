"""Monthly stay-fee email (plan: docs/plans/stay-fee-monthly-email.md).

0205: the host's switch. 0206/0207 add the shared confirm step and the daily job.
"""
from __future__ import annotations

from . import db


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
