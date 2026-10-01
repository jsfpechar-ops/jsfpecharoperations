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


def latest(apartment_id: int, key: str) -> Optional[Dict[str, Any]]:
    return db.query_one(
        "SELECT * FROM stay_fee_filing WHERE apartment_id = ? AND period_key = ? "
        "AND superseded_at IS NULL ORDER BY version DESC LIMIT 1",
        (apartment_id, key),
    )


def latest_version(apartment_id: int, key: str) -> int:
    row = db.query_one(
        "SELECT MAX(version) AS v FROM stay_fee_filing WHERE apartment_id = ? AND period_key = ?",
        (apartment_id, key),
    )
    return int(row["v"] or 0)


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
    version: int,
) -> int:
    """Seal a period; returns the new filing row id."""
    group = stay_fee.report_group(apartment, month)
    period = stay_fee.property_period(apartment, month)
    if period is None:
        raise ValueError("inactive property")
    key = period_key(group["cadence"], month)
    pdf = stay_fee_remittance_pdf.render(stay_fee.hlaseni(group, issued_on))
    csv = stay_fee.register_csv(stay_fee.register_rows(period))
    due = group["total_czk"]
    collected_total = sum(int(collected.get(line["guest_id"], line["amount_czk"]))
                          for line in period["lines"])
    payload_obj = {
        "collected": {str(gid): int(collected.get(gid, 0)) for gid in collected},
        "lines": period["lines"],
    }
    now = db.utcnow()
    return db.insert("stay_fee_filing", {
        "apartment_id": apartment["id"],
        "period_key": key,
        "version": version,
        "cadence": group["cadence"],
        "rate_czk": rate_czk,
        "liable_days": group["liable_nights"],
        "exempt_days": group["exempt_nights"],
        "total_due_czk": due,
        "total_collected_czk": collected_total,
        "pdf_enc": db.encrypt_blob(pdf),
        "csv_enc": db.encrypt_blob(csv),
        "payload_enc": db.encrypt_field(json.dumps(payload_obj, sort_keys=True)),
        "created_at": now,
        "superseded_at": None,
    })


def start_correction(apartment_id: int, key: str) -> None:
    row = latest(apartment_id, key)
    if row:
        db.update("stay_fee_filing", row["id"], {"superseded_at": db.utcnow()})


def frozen_summary(row: Dict[str, Any], apartment) -> Dict[str, Any]:
    """Shape compatible with property_period for a sealed row."""
    return {
        "apartment": apartment,
        "cadence": row["cadence"],
        "first": None,
        "last": None,
        "label": row["period_key"],
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
