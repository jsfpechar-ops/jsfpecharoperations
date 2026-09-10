"""Persistent alerts.

Appendix 5 section 10.4(2) requires an application that reports automatically
to inform the host "without delay" and "by an effective means" when a record
was not accepted - it explicitly suggests a prominent warning on every screen.
These rows drive the banner rendered in the base template.
"""
from __future__ import annotations

from typing import List, Optional

from . import db

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}


def raise_alert(
    level: str,
    kind: str,
    message: str,
    detail: str = "",
    dedupe_key: Optional[str] = None,
    apartment_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
) -> None:
    """Record an alert, refreshing the message if the same one is already open."""
    key = dedupe_key or f"{kind}:{apartment_id}:{reservation_id}:{message}"
    if db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = ? AND user_dismissed = 1 LIMIT 1", (key,)
    ):
        return
    existing = db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
    )
    if existing:
        db.update(
            "alert",
            existing["id"],
            {"level": level, "message": message, "detail": detail, "created_at": db.utcnow()},
        )
        return
    db.insert(
        "alert",
        {
            "level": level,
            "kind": kind,
            "apartment_id": apartment_id,
            "reservation_id": reservation_id,
            "dedupe_key": key,
            "message": message,
            "detail": detail,
            "created_at": db.utcnow(),
        },
    )


def resolve(dedupe_key: str) -> None:
    db.execute(
        "UPDATE alert SET resolved_at = ? WHERE dedupe_key = ? AND resolved_at IS NULL",
        (db.utcnow(), dedupe_key),
    )


def resolve_by_id(alert_id: int, user_dismissed: bool = False) -> None:
    db.execute(
        "UPDATE alert SET resolved_at = ?, user_dismissed = ? WHERE id = ?",
        (db.utcnow(), 1 if user_dismissed else 0, alert_id),
    )


def resolve_kind(kind: str, apartment_id: Optional[int] = None) -> None:
    if apartment_id is None:
        db.execute(
            "UPDATE alert SET resolved_at = ? WHERE kind = ? AND resolved_at IS NULL",
            (db.utcnow(), kind),
        )
    else:
        db.execute(
            "UPDATE alert SET resolved_at = ? WHERE kind = ? AND apartment_id = ? "
            "AND resolved_at IS NULL",
            (db.utcnow(), kind, apartment_id),
        )


def open_alerts() -> List:
    rows = db.query("SELECT * FROM alert WHERE resolved_at IS NULL ORDER BY created_at DESC")
    return sorted(rows, key=lambda r: LEVEL_ORDER.get(r["level"], 9))


def count_critical() -> int:
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE resolved_at IS NULL AND level = 'critical'"
    )
    return row["n"] if row else 0
