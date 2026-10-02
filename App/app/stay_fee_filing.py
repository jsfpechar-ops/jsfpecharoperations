"""Persisted stay-fee periods: encrypted PDF/CSV snapshots after finalization."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from . import db, stay_fee, stay_fee_remittance_pdf


def period_key(cadence: str, month: date) -> str:
    if cadence == "quarterly":
        return f"{month.year:04d}-Q{(month.month - 1) // 3 + 1}"
    return stay_fee.month_key(month)


def overlap_keys(cadence: str, month: date) -> list:
    """Period keys whose dates intersect the period of ``cadence`` containing month."""
    if cadence == "quarterly":
        first, _last = stay_fee.period_bounds("quarterly", month)
        keys = [period_key("quarterly", first)]
        keys.extend(
            stay_fee.month_key(stay_fee.shift_month(first, offset)) for offset in range(3)
        )
        return keys
    return [period_key("monthly", month), period_key("quarterly", month)]


def period_anchor(row: Dict[str, Any]) -> date:
    """First day of the period a filing row was sealed for."""
    key = row["period_key"]
    if "-Q" in key:
        year_s, quarter_s = key.split("-Q")
        return date(int(year_s), (int(quarter_s) - 1) * 3 + 1, 1)
    parsed = stay_fee.parse_month(key)
    if parsed is None:
        raise ValueError(f"bad period key {key}")
    return parsed


def _active(apartment_id: int, keys: list) -> Optional[Dict[str, Any]]:
    if not keys:
        return None
    placeholders = ", ".join("?" for _ in keys)
    return db.query_one(
        "SELECT * FROM stay_fee_filing WHERE apartment_id = ? AND superseded_at IS NULL "
        f"AND period_key IN ({placeholders}) ORDER BY created_at DESC, id DESC LIMIT 1",
        (apartment_id, *keys),
    )


def covering(apartment_id: int, month: date) -> Optional[Dict[str, Any]]:
    """Newest sealed filing whose period contains ``month``, either cadence."""
    return _active(apartment_id, overlap_keys("monthly", month))


def foreign_overlap(apartment_id: int, cadence: str, month: date) -> Optional[Dict[str, Any]]:
    """A sealed filing that intersects this period but is not this period itself."""
    own = period_key(cadence, month)
    return _active(apartment_id, [key for key in overlap_keys(cadence, month) if key != own])


def latest(apartment_id: int, key: str) -> Optional[Dict[str, Any]]:
    return db.query_one(
        "SELECT * FROM stay_fee_filing WHERE apartment_id = ? AND period_key = ? "
        "AND superseded_at IS NULL ORDER BY version DESC LIMIT 1",
        (apartment_id, key),
    )


def pdf_bytes(row: Dict[str, Any]) -> bytes:
    if not row or not row["pdf_enc"]:
        return b""
    return db.decrypt_blob(row["pdf_enc"])


def csv_bytes(row: Dict[str, Any]) -> bytes:
    if not row or not row["csv_enc"]:
        return b""
    return db.decrypt_blob(row["csv_enc"])


def payload(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row or not row["payload_enc"]:
        return {}
    plain = db.decrypt_field(row["payload_enc"])
    return json.loads(plain) if plain else {}


def save(
    apartment,
    month: date,
    *,
    rate_czk: int,
    collected: Dict[int, int],
    issued_on: date,
    cadence: Optional[str] = None,
    replacing_id: Optional[int] = None,
) -> int:
    """Seal a period; returns the new filing row id.

    The previous version is marked superseded in the same transaction as the
    insert. A failure leaves the earlier file downloadable.
    """
    chosen = cadence if cadence in stay_fee.CADENCES else stay_fee.cadence_of(apartment)
    period = stay_fee.property_period(
        apartment, month, live_only=True, cadence=chosen, rate=rate_czk
    )
    if period is None:
        raise ValueError("inactive property")
    group = stay_fee.report_group(apartment, month, live_only=True, period=period, cadence=chosen)
    key = period_key(group["cadence"], group["first"])
    pdf = stay_fee_remittance_pdf.render(stay_fee.hlaseni(group, issued_on))
    csv = stay_fee.register_csv(stay_fee.register_rows(period))
    due = group["total_czk"]
    collected_total = sum(int(collected.get(line["guest_id"], line["amount_czk"]))
                          for line in period["lines"])
    payload_obj = {
        "collected": {str(gid): int(collected.get(gid, 0)) for gid in collected},
        "lines": period["lines"],
        "adjustments": [
            {"id": row["id"], "delta": row["delta"], "mode": row["mode"], "reason": row["reason"]}
            for row in period.get("adjustments") or []
        ],
    }
    now = db.utcnow()
    payload_enc = db.encrypt_field(json.dumps(payload_obj, sort_keys=True))
    with db.immediate() as cur:
        if replacing_id is not None:
            cur.execute(
                "UPDATE stay_fee_filing SET superseded_at = ? "
                "WHERE id = ? AND apartment_id = ? AND superseded_at IS NULL",
                (now, replacing_id, apartment["id"]),
            )
            if cur.rowcount != 1:
                raise ValueError("filing changed")
        else:
            keys = overlap_keys(group["cadence"], group["first"])
            placeholders = ", ".join("?" for _ in keys)
            cur.execute(
                "SELECT id FROM stay_fee_filing WHERE apartment_id = ? "
                f"AND superseded_at IS NULL AND period_key IN ({placeholders}) LIMIT 1",
                (apartment["id"], *keys),
            )
            if cur.fetchone():
                raise ValueError("overlaps saved period")
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) AS v FROM stay_fee_filing "
            "WHERE apartment_id = ? AND period_key = ?",
            (apartment["id"], key),
        )
        version = int(cur.fetchone()["v"]) + 1
        cur.execute(
            "INSERT INTO stay_fee_filing ("
            "apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days, "
            "total_due_czk, total_collected_czk, pdf_enc, csv_enc, payload_enc, created_at, "
            "superseded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                apartment["id"], key, version, group["cadence"], rate_czk,
                group["liable_nights"], group["exempt_nights"], due, collected_total,
                db.encrypt_blob(pdf), db.encrypt_blob(csv), payload_enc, now,
            ),
        )
        filing_id = int(cur.lastrowid)
        cur.execute(
            "UPDATE stay_fee_adjustment SET filing_id = ? "
            "WHERE apartment_id = ? AND period_key = ? AND reversed_at IS NULL "
            "AND filing_id IS NULL",
            (filing_id, apartment["id"], key),
        )
        return filing_id


def frozen_summary(row: Dict[str, Any], apartment) -> Dict[str, Any]:
    """Shape compatible with property_period for a sealed row."""
    anchor = period_anchor(row)
    first, last = stay_fee.period_bounds(row["cadence"], anchor)
    return {
        "apartment": apartment,
        "cadence": row["cadence"],
        "first": first,
        "last": last,
        "label": stay_fee.period_label_cs(row["cadence"], anchor),
        "period_key": row["period_key"],
        "rate_czk": row["rate_czk"],
        "lines": payload(row).get("lines", []),
        "liable_nights": row["liable_days"],
        "exempt_nights": row["exempt_days"],
        "total_czk": row["total_due_czk"],
        "frozen": True,
        "filing_id": row["id"],
        "version": row["version"],
        "total_collected_czk": row["total_collected_czk"],
    }
