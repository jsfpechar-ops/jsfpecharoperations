"""Data-subject request register and per-guest export (BE-8).

A host records an access/erasure/etc. request; the register computes the
one-month deadline Art 12(3) sets and the deadline job warns when it is near.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from . import alerts, db, reporting

DUE_SOON_DAYS = 5
CHANNELS = ("email", "post", "in_person", "support", "other")
REQUEST_TYPES = (
    "access",
    "rectification",
    "erasure",
    "restriction",
    "portability",
    "objection",
    "other",
)
SUBJECT_KINDS = ("guest", "host_user", "other")
STATUSES = ("open", "extended", "fulfilled", "refused", "withdrawn")


def one_month_later(iso: str) -> str:
    """``received_at`` plus one calendar month (Art 12(3))."""
    moment = datetime.fromisoformat(iso)
    month = moment.month + 1
    year = moment.year + (1 if month > 12 else 0)
    if month > 12:
        month = 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day).isoformat()


def list_for_owner(owner_user_id: Optional[int]) -> List[Any]:
    return db.query(
        "SELECT * FROM data_subject_request WHERE owner_user_id IS ? "
        "ORDER BY (status IN ('open','extended')) DESC, due_at, id",
        (owner_user_id,),
    )


def get(request_id: int):
    return db.query_one("SELECT * FROM data_subject_request WHERE id = ?", (request_id,))


def create(
    *,
    owner_user_id: Optional[int],
    received_at: str,
    channel: str,
    request_type: str,
    subject_kind: str,
    guest_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    handled_by: Optional[int] = None,
) -> int:
    now = db.utcnow()
    return db.insert(
        "data_subject_request",
        {
            "owner_user_id": owner_user_id,
            "received_at": received_at,
            "due_at": one_month_later(received_at),
            "channel": channel,
            "request_type": request_type,
            "subject_kind": subject_kind,
            "guest_id": guest_id,
            "reservation_id": reservation_id,
            "status": "open",
            "handled_by": handled_by,
            "created_at": now,
            "updated_at": now,
        },
    )


def update(request_id: int, values: Dict[str, Any]) -> None:
    db.update("data_subject_request", request_id, {**values, "updated_at": db.utcnow()})


def guest_export(guest_id: int) -> Optional[Dict[str, Any]]:
    """Everything the operator holds about one guest, decrypted, ids only.

    The image itself is not included: the bundle carries a presence flag, not a
    copy of the passport or the signature.
    """
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest:
        return None
    reservation = db.query_one(
        "SELECT id, date_from, date_to, source, uid FROM reservation WHERE id = ?",
        (guest["reservation_id"],),
    )
    submissions = db.query(
        "SELECT id, state, created_at, finished_at, pseudo_stamp, "
        "(receipt_pdf IS NOT NULL) AS has_receipt FROM submission "
        "WHERE id IN (SELECT submission_id FROM guest WHERE id = ? "
        "UNION SELECT receipt_submission_id FROM guest WHERE id = ?)",
        (guest_id, guest_id),
    )
    audit_rows = db.query(
        "SELECT at, actor, action, detail FROM audit WHERE detail LIKE ? ORDER BY id",
        (f"%guest_id={guest_id}%",),
    )

    fields: Dict[str, Any] = {}
    for key in guest.keys():
        if key in ("signature_png", "signature_png_enc"):
            continue
        fields[key] = guest[key]
    fields["signature_present"] = reporting.guest_has_signature(guest)
    fields["passport_photo_present"] = reporting.guest_has_passport_photo(guest)

    return {
        "generated_at": db.utcnow(),
        "guest": fields,
        "notice": {
            "version": guest["notice_version"],
            "lang": guest["notice_lang"],
            "acknowledged_at": guest["notice_ack_at"],
        },
        "reservation": dict(reservation) if reservation else None,
        "submissions": [dict(row) for row in submissions],
        "receipt_submission_id": guest["receipt_submission_id"],
        "audit": [dict(row) for row in audit_rows],
    }


def raise_due_alerts(today: Optional[date] = None) -> int:
    """Warn, per request, when its one-month deadline is near (or past)."""
    today = today or date.today()
    horizon = (today + timedelta(days=DUE_SOON_DAYS)).isoformat()
    rows = db.query(
        "SELECT * FROM data_subject_request "
        "WHERE status IN ('open','extended') AND date(due_at) <= ?",
        (horizon,),
    )
    for row in rows:
        alerts.raise_alert(
            "warning",
            "dsr_due",
            f"Data-subject request due {row['due_at']}.",
            "Handle it and record the outcome.",
            dedupe_key=f"dsr_due:{row['id']}",
            owner_user_id=row["owner_user_id"],
            params={"due": row["due_at"]},
        )
    return len(rows)
