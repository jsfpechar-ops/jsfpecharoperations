"""Brief 1082 (S5, decision 7b): the server draft of an unfinished guest form.

One encrypted row per (reservation, device). The device is known only by the
sha256 of the random key in the ``ubyhost_draft`` cookie. A draft is never a
``guest`` row, so filing cannot see it. It is deleted when the form is sent,
else 7 days after its last change or the day after check-out (``purge``).
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

from . import db

log = logging.getLogger(__name__)

MAX_AGE_DAYS = 7
MAX_FIELD_LENGTH = 60
MAX_OWNED = 40
DRAFT_FIELDS = (
    "party_size",
    "first_name",
    "surname",
    "birth_date",
    "nationality",
    "doc_number",
    "child_in_passport",
    "parent_doc_number",
    "visa_number",
    "purpose",
    "res_country",
    "res_city",
    "res_street",
)
_TYPED = (
    "first_name",
    "surname",
    "birth_date",
    "doc_number",
    "parent_doc_number",
    "visa_number",
    "res_city",
    "res_street",
)


def key_hash(device_key: str) -> str:
    return hashlib.sha256(device_key.encode("utf-8")).hexdigest()


def clamp_owned(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_OWNED, number))


def _clean(fields) -> Dict[str, str]:
    clean: Dict[str, str] = {}
    for name in DRAFT_FIELDS:
        value = str(fields.get(name) or "").strip()[:MAX_FIELD_LENGTH]
        if value:
            clean[name] = value
    return clean


def _cutoff_iso() -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    return cutoff.replace(microsecond=0).isoformat()


def save(reservation_id: int, device_hash: str, generation: int, owned_count: int, fields) -> bool:
    clean = _clean(fields)
    if not any(name in clean for name in _TYPED):
        delete(reservation_id, device_hash)
        return False
    now = db.utcnow()
    db.execute(
        "INSERT INTO guest_form_draft (reservation_id, device_key_hash, claim_generation, owned_count, "
        "fields_enc, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (reservation_id, device_key_hash) DO UPDATE SET "
        "claim_generation = excluded.claim_generation, owned_count = excluded.owned_count, "
        "fields_enc = excluded.fields_enc, updated_at = excluded.updated_at",
        (
            reservation_id,
            device_hash,
            int(generation),
            clamp_owned(owned_count),
            db.encrypt_field(json.dumps(clean, ensure_ascii=False, sort_keys=True)),
            now,
            now,
        ),
    )
    return True


def delete(reservation_id: int, device_hash: str) -> int:
    return db.execute_rowcount(
        "DELETE FROM guest_form_draft WHERE reservation_id = ? AND device_key_hash = ?",
        (reservation_id, device_hash),
    )


def load(
    reservation_id: int,
    device_hash: str,
    generation: int,
    owned_count: int,
    today: Optional[date] = None,
) -> Optional[Dict[str, str]]:
    if today is None:
        from .claim import prague_today

        today = prague_today()
    row = db.query_one(
        "SELECT d.id, d.claim_generation, d.owned_count, d.fields_enc, d.updated_at, r.status, r.date_to "
        "FROM guest_form_draft d JOIN reservation r ON r.id = d.reservation_id "
        "WHERE d.reservation_id = ? AND d.device_key_hash = ?",
        (reservation_id, device_hash),
    )
    if row is None:
        return None
    fresh = (
        row["status"] == "active"
        and str(row["date_to"])[:10] >= today.isoformat()
        and str(row["updated_at"]) >= _cutoff_iso()
        and int(row["claim_generation"]) == int(generation)
        and int(row["owned_count"]) == clamp_owned(owned_count)
    )
    value = None
    if fresh:
        try:
            value = json.loads(db.decrypt_field(row["fields_enc"]) or "")
        except (ValueError, TypeError):
            value = None
    if not fresh or not isinstance(value, dict):
        db.execute_rowcount("DELETE FROM guest_form_draft WHERE id = ?", (row["id"],))
        return None
    return _clean(value)


def purge(today: Optional[date] = None) -> int:
    """Owner rule: a draft goes 7 days after its last change or the day after
    check-out, whichever comes first (also when the stay is no longer active).

    Not a ``retention.STEPS`` entry: every step there honours the dry run, and
    this rule must hold with UBYHOST_RETENTION_AUTOPURGE=0. It runs in the
    12-hour photo sweep, like ``passport_photos.purge_stale``.
    """
    if today is None:
        from .claim import prague_today

        today = prague_today()
    where = (
        "updated_at < ? OR reservation_id IN (SELECT r.id FROM reservation r WHERE r.status <> 'active' OR "
        + db.sqlite_date_expr("r.date_to")
        + " < ?)"
    )
    params = (_cutoff_iso(), today.isoformat())
    count = db.execute_rowcount(f"DELETE FROM guest_form_draft WHERE {where}", params)
    if count:
        log.info("guest_draft.purge deleted %s draft(s)", count)
    return count
