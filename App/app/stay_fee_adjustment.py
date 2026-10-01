"""Aggregate stay-fee corrections that are not guest records.

A host can add or remove liable bed-days, either directly or as
``people × nights``. The rows stay in the audit trail. They never become
guests and never appear in the statutory register as named people.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from . import db


def net_bed_days(apartment_id: int, period_key: str) -> int:
    total, _rows = active(apartment_id, period_key)
    return total


def active(apartment_id: int, period_key: str) -> Tuple[int, List[Dict[str, Any]]]:
    rows = db.query(
        "SELECT * FROM stay_fee_adjustment WHERE apartment_id = ? AND period_key = ? "
        "AND reversed_at IS NULL ORDER BY id",
        (apartment_id, period_key),
    )
    signed = []
    total = 0
    for row in rows:
        delta = int(row["bed_days"])
        if row["direction"] == "remove":
            delta = -delta
        total += delta
        item = dict(row)
        item["delta"] = delta
        item["reason"] = db.decrypt_field(row["reason_enc"]) or ""
        signed.append(item)
    return total, signed


def add(
    *,
    apartment_id: int,
    period_key: str,
    direction: str,
    mode: str,
    people_count: int,
    nights: int,
    bed_days: int,
    reason: str,
    created_by: int,
) -> int:
    return db.insert(
        "stay_fee_adjustment",
        {
            "apartment_id": apartment_id,
            "period_key": period_key,
            "direction": direction,
            "mode": mode,
            "people_count": people_count or None,
            "nights": nights or None,
            "bed_days": bed_days,
            "reason_enc": db.encrypt_field(reason),
            "created_by": created_by,
            "created_at": db.utcnow(),
        },
    )


def reverse(adjustment_id: int, actor_id: int) -> None:
    db.update(
        "stay_fee_adjustment",
        adjustment_id,
        {"reversed_at": db.utcnow(), "reversed_by": actor_id},
    )


def attach_open(apartment_id: int, period_key: str, filing_id: int) -> None:
    db.execute(
        "UPDATE stay_fee_adjustment SET filing_id = ? "
        "WHERE apartment_id = ? AND period_key = ? AND reversed_at IS NULL AND filing_id IS NULL",
        (filing_id, apartment_id, period_key),
    )
