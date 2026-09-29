"""CSV export for manually added stays."""
from __future__ import annotations

import csv
import io
from typing import Any, Iterator, List, Optional

from .csv_safety import csv_safe

STAY_COLUMNS = [
    ("apartment", "Apartment"),
    ("date_from", "Arrival"),
    ("date_to", "Departure"),
    ("guests", "Number of guests"),
    ("label", "Label"),
    ("guest_email", "Guest e-mail"),
]


def _export_sql(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    apartment_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
) -> tuple[str, List[Any]]:
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
    return sql, params


def iter_export_csv_rows(rows: List[Any]) -> Iterator[bytes]:
    """Stream an already-fetched stays export row-by-row."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    yield b"\xef\xbb\xbf"
    writer.writerow([label for _key, label in STAY_COLUMNS])
    yield buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    for row in rows:
        guests = row["expected_guests_override"] or row["declared_guests"]
        writer.writerow(
            [
                csv_safe(row["apartment_name"]),
                csv_safe(row["date_from"]),
                csv_safe(row["date_to"]),
                csv_safe(str(guests) if guests else ""),
                csv_safe(row["summary"] or ""),
                csv_safe(row["guest_email"] or ""),
            ]
        )
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)
