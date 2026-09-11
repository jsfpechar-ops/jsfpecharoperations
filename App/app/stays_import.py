"""CSV import/export for manually added stays."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from . import db

STAY_COLUMNS = [
    ("apartment", "Apartment"),
    ("date_from", "Arrival"),
    ("date_to", "Departure"),
    ("guests", "Number of guests"),
    ("label", "Label"),
    ("guest_email", "Guest e-mail"),
]

SAMPLE_ROW = {
    "apartment": "My apartment",
    "date_from": "2026-09-15",
    "date_to": "2026-09-18",
    "guests": "2",
    "label": "Direct booking – Novák",
    "guest_email": "guest@example.com",
}


def _parse_date(value: str) -> Optional[str]:
    value = (value or "").strip()
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value
    if len(value) == 10 and value[2] == "." and value[5] == ".":
        day, month, year = value.split(".")
        if day.isdigit() and month.isdigit() and year.isdigit():
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None


def sample_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for _key, label in STAY_COLUMNS])
    writer.writerow([SAMPLE_ROW[key] for key, _label in STAY_COLUMNS])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def import_csv(content: bytes, owner_user_id: Optional[int] = None) -> Dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    if not rows:
        return {"imported": 0, "skipped": 0, "errors": ["The file is empty."]}

    header = [cell.strip().lower() for cell in rows[0]]
    label_to_key = {label.lower(): key for key, label in STAY_COLUMNS}
    indexes: Dict[str, int] = {}
    for index, label in enumerate(header):
        key = label_to_key.get(label)
        if key:
            indexes[key] = index
    required = ("apartment", "date_from", "date_to")
    missing = [name for name in required if name not in indexes]
    if missing:
        return {
            "imported": 0,
            "skipped": 0,
            "errors": [
                "Could not find required columns: "
                + ", ".join(name.replace("_", " ") for name in missing)
                + ". Download the sample CSV and match its headers."
            ],
        }

    apartments = {
        row["internal_name"].strip().lower(): row["id"]
        for row in db.query(
            "SELECT id, internal_name FROM apartment WHERE archived_at IS NULL "
            "AND (? IS NULL OR owner_user_id = ?)",
            (owner_user_id, owner_user_id),
        )
    }
    imported = 0
    skipped = 0
    errors: List[str] = []
    now = db.utcnow()

    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue

        def cell(key: str) -> str:
            index = indexes.get(key)
            if index is None or index >= len(row):
                return ""
            return row[index].strip()

        apartment_name = cell("apartment")
        apartment_id = apartments.get(apartment_name.lower())
        if not apartment_id:
            skipped += 1
            errors.append(f"Line {line_no}: unknown apartment “{apartment_name}”.")
            continue

        date_from = _parse_date(cell("date_from"))
        date_to = _parse_date(cell("date_to"))
        if not (date_from and date_to):
            skipped += 1
            errors.append(f"Line {line_no}: invalid arrival or departure date.")
            continue
        if date_to <= date_from:
            skipped += 1
            errors.append(f"Line {line_no}: departure must be after arrival.")
            continue

        guests_raw = cell("guests")
        guests = int(guests_raw) if guests_raw.isdigit() else None
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "import",
                "uid": f"import-{apartment_id}-{date_from}-{date_to}-{line_no}",
                "date_from": date_from,
                "date_to": date_to,
                "summary": cell("label") or "Imported stay",
                "expected_guests_override": guests,
                "guest_email": cell("guest_email") or None,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
        imported += 1

    if imported:
        db.audit("stays_import", f"rows={imported}")
    return {"imported": imported, "skipped": skipped, "errors": errors[:8]}


def export_csv(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    apartment_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
) -> bytes:
    """Export stays in the same format used for CSV import."""
    sql = (
        "SELECT r.*, a.internal_name AS apartment_name FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.archived_at IS NULL AND (? IS NULL OR a.owner_user_id = ?)"
    )
    params: List[Any] = [owner_user_id, owner_user_id]
    if apartment_id:
        sql += " AND r.apartment_id = ?"
        params.append(apartment_id)
    if date_from:
        sql += " AND r.date_to >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND r.date_from <= ?"
        params.append(date_to)
    sql += " ORDER BY r.date_from, a.internal_name"

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([label for _key, label in STAY_COLUMNS])
    for row in db.query(sql, params):
        guests = row["expected_guests_override"] or row["declared_guests"]
        writer.writerow(
            [
                row["apartment_name"],
                row["date_from"],
                row["date_to"],
                str(guests) if guests else "",
                row["summary"] or "",
                row["guest_email"] or "",
            ]
        )
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
