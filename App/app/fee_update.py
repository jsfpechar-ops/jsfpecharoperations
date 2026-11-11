"""Brief 1078 (F3): one update mail when the stay-fee total changes after the bill.

The completion mail states the fee once. ``record_baseline`` stores that total;
``sweep_fee_updates`` compares it with the live total and, once the live total
has differed for ``QUIET_MINUTES`` without a further change, mails the lead
guest the old and the new amount. Nothing here touches the police filing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from . import claim, db, mail, mail_notify, validation

log = logging.getLogger("ubyhost.fee_update")

QUIET_MINUTES = 10


def record_baseline(reservation_id: int, total: int) -> None:
    """Remember the total the completion mail just stated."""
    # ``updated_at`` is left alone in every write of this module: it is the
    # clock of the claim-link resend cooldown (``claim._resend_too_soon``).
    db.execute(
        "UPDATE reservation_claim SET fee_mailed_total = ?, fee_mailed_at = ?, "
        "fee_pending_total = NULL, fee_pending_since = NULL "
        "WHERE reservation_id = ?",
        (int(total), db.utcnow(), reservation_id),
    )


def _record_sent(reservation_id: int, live: int, mailed_at: str, now_iso: str) -> None:
    """Move the baseline, but only if no other worker moved it first."""
    db.execute(
        "UPDATE reservation_claim SET fee_mailed_total = ?, fee_mailed_at = ?, "
        "fee_pending_total = NULL, fee_pending_since = NULL "
        "WHERE reservation_id = ? AND fee_mailed_at = ?",
        (live, now_iso, reservation_id, mailed_at),
    )


def _quiet_long_enough(since: Optional[str], now: datetime) -> bool:
    try:
        started = datetime.fromisoformat(since or "")
    except ValueError:
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return now - started >= timedelta(minutes=QUIET_MINUTES)


def _decide(reservation_id: int, live: Optional[int], now: datetime, now_iso: str):
    """Under the row lock: update the pending columns, or return what is due.

    Returns ``(outcome, due)``: outcome is "none", "pending" or "due"; ``due``
    carries the values read under the lock that the mail needs.
    """
    with db.immediate() as cur:
        db.lock_key(cur, "fee_update", reservation_id)
        cur.execute(
            "SELECT state, email, lang, fee_mailed_total, fee_mailed_at, "
            "fee_pending_total, fee_pending_since "
            "FROM reservation_claim WHERE reservation_id = ?",
            (reservation_id,),
        )
        row = cur.fetchone()
        if (
            row is None
            or row["state"] != claim.CLAIMED
            or not row["email"]
            or row["fee_mailed_total"] is None
        ):
            return "none", None
        mailed_total = int(row["fee_mailed_total"])
        pending_total = row["fee_pending_total"]
        if live is None or live == mailed_total:
            if pending_total is None and row["fee_pending_since"] is None:
                return "none", None
            # A mail queued under this baseline means its record was lost (the
            # process died after the enqueue). The guest was told that mail's
            # total, so it becomes the baseline; the next sweep then sees the
            # live total differ from it and mails the correction.
            prefix = f"completion_update:{reservation_id}:{row['fee_mailed_at']}:"
            cur.execute(
                "SELECT idempotency_key FROM email_outbox "
                "WHERE reservation_id = ? AND kind = 'completion_update' "
                "ORDER BY id DESC",
                (reservation_id,),
            )
            lost = next(
                (
                    found["idempotency_key"][len(prefix):]
                    for found in cur.fetchall()
                    if found["idempotency_key"].startswith(prefix)
                ),
                None,
            )
            if lost is not None and lost.isdigit() and int(lost) != mailed_total:
                cur.execute(
                    "UPDATE reservation_claim SET fee_mailed_total = ?, "
                    "fee_mailed_at = ?, fee_pending_total = NULL, "
                    "fee_pending_since = NULL WHERE reservation_id = ?",
                    (int(lost), now_iso, reservation_id),
                )
                return "none", None
            cur.execute(
                "UPDATE reservation_claim SET fee_pending_total = NULL, "
                "fee_pending_since = NULL WHERE reservation_id = ?",
                (reservation_id,),
            )
            return "none", None
        if pending_total is None or int(pending_total) != live:
            # The wait restarts on every further change.
            cur.execute(
                "UPDATE reservation_claim SET fee_pending_total = ?, "
                "fee_pending_since = ? WHERE reservation_id = ?",
                (live, now_iso, reservation_id),
            )
            return "pending", None
        if not _quiet_long_enough(row["fee_pending_since"], now):
            return "pending", None
        return "due", {
            "old": mailed_total,
            "mailed_at": row["fee_mailed_at"],
            "email": row["email"],
            "lang": row["lang"] or "en",
        }


def sweep_fee_updates(now: Optional[datetime] = None) -> Dict[str, int]:
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_iso = now.isoformat()
    summary = {"queued": 0, "pending": 0}
    rows = db.query(
        "SELECT r.*, c.fee_mailed_total, c.fee_pending_total FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        "JOIN reservation_claim c ON c.reservation_id = r.id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND a.archived_at IS NULL "
        "AND r.source != 'demo' AND r.date_to >= ? AND c.state = 'claimed' "
        "AND c.completion_notified_at IS NOT NULL AND c.fee_mailed_total IS NOT NULL "
        "AND c.email IS NOT NULL",
        (claim.prague_today().isoformat(),),
    )
    for reservation in rows:
        reservation_id = reservation["id"]
        try:
            apartment = db.query_one(
                "SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],)
            )
            fee = claim._completion_fee(apartment, reservation)
            live = fee["total"] if fee else None
            if reservation["fee_pending_total"] is None and (
                live is None or live == reservation["fee_mailed_total"]
            ):
                # Nothing changed and nothing is waiting: no transaction.
                continue
            outcome, due = _decide(reservation_id, live, now, now_iso)
            if outcome == "pending":
                summary["pending"] += 1
            if outcome != "due":
                continue
            lang = due["lang"]
            content = mail_notify.build_fee_update(
                lang=lang,
                property_name=mail_notify.property_label(apartment, lang),
                dates=validation.fmt_date_range(
                    reservation["date_from"], reservation["date_to"]
                ),
                host=mail_notify.host_details(apartment["legal_entity_id"]),
                old_total=due["old"],
                new_total=live,
                vs=fee["vs"] if "iban" in fee["rails"] else "",
            )
            payload = mail_notify.guest_payload(apartment, content, lang)
            outbox_id = mail.enqueue(
                kind="completion_update",
                # No clock and no counter in the key: a rerun, a second worker
                # or a crash before the record below reuses the same row.
                idempotency_key=(
                    f"completion_update:{reservation_id}:{due['mailed_at']}:{live}"
                ),
                to_email=due["email"],
                subject=content["subject"],
                payload=payload,
                reservation_id=reservation_id,
                apartment_id=apartment["id"],
                owner_user_id=apartment["owner_user_id"],
            )
            if outbox_id is None:
                continue
            _record_sent(reservation_id, live, due["mailed_at"], now_iso)
            summary["queued"] += 1
        except Exception:
            log.exception("fee update sweep skipped reservation_id=%s", reservation_id)
            continue
    return summary
