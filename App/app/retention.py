"""Scheduled retention: everything the retention schedule says may no longer be held.

BE-2 builds the job. It is **dry-run by default** (Rule 7): in dry-run it
computes exactly the row set it would delete, audits the counts, and deletes
nothing. Deletion starts only when ``UBYHOST_RETENTION_AUTOPURGE=1``, which the
owner sets once counsel confirms the retention anchor (G-D4).

Never logs personal data (Rule 8): counts and ids only.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from . import alerts, config, db, housebook, invoices


def _run_guest_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    if dry_run:
        return len(housebook.expired_guest_ids(today, owner_user_id=owner_user_id))
    return housebook.purge_expired(today, owner_user_id=owner_user_id)


def _run_invoice_step(today: date, dry_run: bool, owner_user_id: Optional[int]) -> int:
    if dry_run:
        return len(invoices.expired_ids(today, owner_user_id=owner_user_id))
    return invoices.purge_expired(today, owner_user_id=owner_user_id)


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

    steps = (
        ("guests", _run_guest_step),
        ("invoices", _run_invoice_step),
        # BE-3 and BE-4 append their steps here when those land.
    )
    for name, step in steps:
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
