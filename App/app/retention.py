"""Scheduled retention: everything the retention schedule says may no longer be held.

BE-2 builds the job; BE-3 adds the reservation/claim/contact minimisation steps.
It is **dry-run by default** (Rule 7): in dry-run it computes exactly the row
set it would delete or null, audits the counts, and changes nothing. Deletion
starts only when ``UBYHOST_RETENTION_AUTOPURGE=1``, which the owner sets once
counsel confirms the retention anchor (G-D4).

Never logs personal data (Rule 8): counts and ids only.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import alerts, config, db, housebook, invoices, passport_photos

# G-D5: null the claim e-mail / reservation e-mail / phone fragment this long
# after the stay's end date.
CLAIM_EMAIL_GRACE_DAYS = 30
# G-D6: null the submitter IP this long after the guest's stay end (a disputes
# evidence window), counsel to confirm.
SUBMITTER_IP_GRACE_DAYS = 90

_OWNER_SCOPE = "(? IS NULL OR a.owner_user_id = ?)"


def _scalar(sql: str, params: tuple = ()) -> int:
    row = db.query_one(sql, params)
    return int(row["n"]) if row and row["n"] is not None else 0


def _run_guest_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    if dry_run:
        return len(housebook.expired_guest_ids(today, owner_user_id=owner_user_id))
    return housebook.purge_expired(today, owner_user_id=owner_user_id)


def _run_invoice_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    if dry_run:
        return len(invoices.expired_ids(today, owner_user_id=owner_user_id))
    return invoices.purge_expired(today, owner_user_id=owner_user_id)


def _claim_email_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Null ``reservation_claim.email`` once the stay is past the grace window."""
    cutoff = (today - timedelta(days=CLAIM_EMAIL_GRACE_DAYS)).isoformat()
    inner = (
        "SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE date(r.date_to) < ? AND {_OWNER_SCOPE}"
    )
    params = (cutoff, owner_user_id, owner_user_id)
    where = f"email IS NOT NULL AND reservation_id IN ({inner})"
    count = _scalar(f"SELECT COUNT(*) AS n FROM reservation_claim WHERE {where}", params)
    if not dry_run and count:
        db.execute(
            f"UPDATE reservation_claim SET email = NULL, updated_at = ? WHERE {where}",
            (db.utcnow(), *params),
        )
    return count


def _reservation_contact_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Null ``reservation.guest_email`` and ``phone_last4`` past the same window."""
    cutoff = (today - timedelta(days=CLAIM_EMAIL_GRACE_DAYS)).isoformat()
    inner = "SELECT id FROM apartment a WHERE (? IS NULL OR a.owner_user_id = ?)"
    params = (cutoff, owner_user_id, owner_user_id)
    where = (
        "(guest_email IS NOT NULL OR phone_last4 IS NOT NULL) "
        f"AND date(date_to) < ? AND apartment_id IN ({inner})"
    )
    count = _scalar(f"SELECT COUNT(*) AS n FROM reservation WHERE {where}", params)
    if not dry_run and count:
        db.execute(
            "UPDATE reservation SET guest_email = NULL, phone_last4 = NULL, updated_at = ? "
            f"WHERE {where}",
            (db.utcnow(), *params),
        )
    return count


def _submitter_ip_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Null ``guest.filled_ip`` past the submitter-IP window (G-D6)."""
    cutoff = (today - timedelta(days=SUBMITTER_IP_GRACE_DAYS)).isoformat()
    inner = "SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE " + _OWNER_SCOPE
    params = (cutoff, owner_user_id, owner_user_id)
    where = (
        "filled_ip IS NOT NULL AND "
        "COALESCE(date(stay_to), (SELECT date(date_to) FROM reservation r2 "
        "WHERE r2.id = guest.reservation_id)) < ? "
        f"AND reservation_id IN ({inner})"
    )
    count = _scalar(f"SELECT COUNT(*) AS n FROM guest WHERE {where}", params)
    if not dry_run and count:
        db.execute(f"UPDATE guest SET filled_ip = NULL WHERE {where}", params)
    return count


def _empty_reservation_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete reservations past the six-year cutoff that have no guest rows."""
    cutoff = housebook.retention_cutoff(today).isoformat()
    inner = "SELECT id FROM apartment a WHERE (? IS NULL OR a.owner_user_id = ?)"
    params = (cutoff, owner_user_id, owner_user_id)
    where = (
        "date(date_to) < ? AND NOT EXISTS "
        "(SELECT 1 FROM guest g WHERE g.reservation_id = reservation.id) "
        f"AND apartment_id IN ({inner})"
    )
    count = _scalar(f"SELECT COUNT(*) AS n FROM reservation WHERE {where}", params)
    if not dry_run and count:
        db.execute(f"DELETE FROM reservation WHERE {where}", params)
    return count


def _days_ago_iso(days: int) -> str:
    return (
        (datetime.now(timezone.utc) - timedelta(days=days))
        .replace(microsecond=0)
        .isoformat()
    )


def _audit_retention_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete audit rows past the window, but never the acceptance evidence.

    ``legal_accepted`` rows are the BE-1 evidence and have their own rule
    (``_acceptance_retention_step``); the free-text ``login`` rows that used to
    carry the versions are ordinary audit rows and expire here.
    """
    cutoff = _days_ago_iso(config.AUDIT_RETENTION_DAYS)
    where = (
        "at < ? AND action NOT IN ('legal_accepted') "
        "AND (? IS NULL OR owner_user_id = ?)"
    )
    params = (cutoff, owner_user_id, owner_user_id)
    count = _scalar(f"SELECT COUNT(*) AS n FROM audit WHERE {where}", params)
    if not dry_run and count:
        db.execute(f"DELETE FROM audit WHERE {where}", params)
    return count


def _alert_retention_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete alerts that were resolved longer ago than the window."""
    cutoff = _days_ago_iso(config.ALERT_RETENTION_DAYS)
    where = (
        "resolved_at IS NOT NULL AND resolved_at < ? "
        "AND (? IS NULL OR owner_user_id = ?)"
    )
    params = (cutoff, owner_user_id, owner_user_id)
    count = _scalar(f"SELECT COUNT(*) AS n FROM alert WHERE {where}", params)
    if not dry_run and count:
        db.execute(f"DELETE FROM alert WHERE {where}", params)
    return count


def _rate_limit_retention_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete stale rate-limit events. Global only: the table has no owner."""
    if owner_user_id is not None:
        return 0
    cutoff = time.time() - config.RATE_LIMIT_RETENTION_HOURS * 3600
    count = _scalar(
        "SELECT COUNT(*) AS n FROM rate_limit_event WHERE at < ?", (cutoff,)
    )
    if not dry_run and count:
        db.execute("DELETE FROM rate_limit_event WHERE at < ?", (cutoff,))
    return count


def _acceptance_retention_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete acceptance evidence only for long-inactive accounts (G-D7).

    There is no ``disabled_at`` column, so "inactive for three years" is read
    conservatively as a disabled account whose last login is also older than
    the window; a never-used account is left alone. Recorded in FOLLOWUPS.md.
    """
    cutoff = _days_ago_iso(config.AUDIT_RETENTION_DAYS)
    inner = (
        "SELECT id FROM user_account WHERE active = 0 "
        "AND last_login_at IS NOT NULL AND last_login_at < ?"
    )
    where = f"user_account_id IN ({inner}) AND (? IS NULL OR user_account_id = ?)"
    params = (cutoff, owner_user_id, owner_user_id)
    count = _scalar(f"SELECT COUNT(*) AS n FROM legal_acceptance WHERE {where}", params)
    if not dry_run and count:
        db.execute(f"DELETE FROM legal_acceptance WHERE {where}", params)
    return count


def _workspace_deletion_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    """Delete workspaces whose termination date has passed (BE-10, G-D11).

    Global only: a workspace cannot delete itself from the owner-scoped button.
    """
    if owner_user_id is not None:
        return 0
    rows = db.query(
        "SELECT id FROM user_account WHERE deletion_due_at IS NOT NULL AND deletion_due_at <= ?",
        (db.utcnow(),),
    )
    if dry_run or not rows:
        return len(rows)
    for row in rows:
        _delete_workspace(row["id"])
    return len(rows)


def _delete_workspace(owner_id: int) -> None:
    """Remove every row that belongs to one workspace, in dependency order."""
    for guest in db.query(
        "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id IS ?",
        (owner_id,),
    ):
        passport_photos.delete_photo(guest["id"])
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE a.owner_user_id IS ?)",
        (owner_id,),
    )
    db.execute(
        "DELETE FROM submission WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id IS ?)",
        (owner_id,),
    )
    db.execute(
        "DELETE FROM reservation WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id IS ?)",
        (owner_id,),
    )
    db.execute("DELETE FROM apartment WHERE owner_user_id IS ?", (owner_id,))

    invoice_ids = [
        row["id"]
        for row in db.query("SELECT id FROM invoice WHERE owner_user_id IS ?", (owner_id,))
    ]
    if invoice_ids:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        try:
            for invoice_id in invoice_ids:
                db.execute("DELETE FROM invoice_item WHERE invoice_id = ?", (invoice_id,))
                db.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
        finally:
            db.execute(
                "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
                "ON CONFLICT(key) DO UPDATE SET value = ''"
            )

    db.execute("DELETE FROM legal_entity WHERE owner_user_id IS ?", (owner_id,))

    db.execute("DELETE FROM data_subject_request WHERE owner_user_id IS ?", (owner_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id IS ?", (owner_id,))
    # legal_acceptance has a NOT NULL account reference, so it cannot outlive the
    # account; see FOLLOWUPS.md for the tension with G-D7.
    db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id IS ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _raise_due_notices(today: date) -> None:
    """Warn each owner whose records reach the end of their retention window.

    One card per owner per calendar month (the dedupe key carries the month).
    """
    days = config.RETENTION_NOTICE_DAYS
    month = today.strftime("%Y-%m")
    for owner_user_id, count in housebook.due_guest_counts(today, days).items():
        alerts.raise_alert(
            "warning",
            "retention_due",
            f"{count} guest record(s) reach the end of their retention period "
            f"within {days} days.",
            "Review the house book and export anything you still need: /housebook",
            dedupe_key=f"retention_due:{owner_user_id}:{month}",
            owner_user_id=owner_user_id,
            params={"count": count, "days": days},
        )


# Each step takes (today, dry_run, owner_user_id) and returns the affected count.
STEPS: List[tuple] = [
    ("guests", _run_guest_step),
    ("invoices", _run_invoice_step),
    ("claim_emails", _claim_email_step),
    ("reservation_contacts", _reservation_contact_step),
    ("submitter_ips", _submitter_ip_step),
    ("empty_reservations", _empty_reservation_step),
    ("audit_rows", _audit_retention_step),
    ("alerts", _alert_retention_step),
    ("rate_limit_events", _rate_limit_retention_step),
    ("legal_acceptance", _acceptance_retention_step),
    ("workspaces", _workspace_deletion_step),
]


def run(
    today: Optional[date] = None,
    *,
    dry_run: Optional[bool] = None,
    owner_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Everything the retention schedule says may no longer be held.

    ``dry_run`` defaults to ``not config.RETENTION_AUTOPURGE``. Each step is
    wrapped so one failure does not stop the rest; the first failure is
    re-raised at the end so the scheduler marks the job failed. The run is
    always audited and its summary stored for the Settings panel (FE-3).
    """
    today = today or date.today()
    if dry_run is None:
        dry_run = not config.RETENTION_AUTOPURGE

    counts: Dict[str, int] = {}
    failures: List[BaseException] = []

    for name, step in STEPS:
        try:
            counts[name] = step(today, dry_run, owner_user_id)
        except Exception as exc:  # keep going; re-raised below
            failures.append(exc)

    summary = {"dry_run": dry_run, "owner_user_id": owner_user_id, "counts": counts}
    db.audit("retention_run", json.dumps(summary), actor="system")
    db.set_setting(
        "retention_last_run", json.dumps({**summary, "at": db.utcnow()})
    )

    # The notice is a platform-wide view, so it is raised only on a global run,
    # not from the owner-scoped Settings button.
    if owner_user_id is None:
        try:
            _raise_due_notices(today)
        except Exception as exc:
            failures.append(exc)

    if failures:
        raise failures[0]
    return summary
