"""Manual stays CSV import/export."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from app import db, stays_import


def _seed_apartment(name: str = "Stay import flat", token: str = "tok-stays") -> int:
    db.init_db()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": f"Stays Import Test {token}", "created_at": now},
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": name,
            "permalink_token": token,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )


def _stays_csv(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def test_sample_csv_matches_import_headers():
    body = stays_import.sample_csv()
    assert body.startswith(b"\xef\xbb\xbf")
    text = body.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(reader)
    assert header[0] == "Apartment"
    assert "Arrival" in header


def test_import_creates_reservation_with_iso_dates():
    apartment_id = _seed_apartment(token="tok-stays-iso")
    today = date.today()
    arrival = today.isoformat()
    departure = (today + timedelta(days=3)).isoformat()
    content = _stays_csv(
        [
            [label for _key, label in stays_import.STAY_COLUMNS],
            ["Stay import flat", arrival, departure, "2", "Direct", "guest@example.com"],
        ]
    )
    result = stays_import.import_csv(content)
    assert result["imported"] == 1
    assert not result["errors"]

    row = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
        (apartment_id,),
    )
    assert row["date_from"] == arrival
    assert row["date_to"] == departure
    assert row["expected_guests_override"] == 2
    assert row["guest_email"] == "guest@example.com"


def test_import_accepts_czech_date_format():
    apartment_id = _seed_apartment(token="tok-stays-cz")
    content = _stays_csv(
        [
            [label for _key, label in stays_import.STAY_COLUMNS],
            ["Stay import flat", "15.09.2026", "18.09.2026", "", "Label", ""],
        ]
    )
    result = stays_import.import_csv(content)
    assert result["imported"] == 1
    row = db.query_one(
        "SELECT date_from, date_to FROM reservation WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
        (apartment_id,),
    )
    assert row["date_from"] == "2026-09-15"
    assert row["date_to"] == "2026-09-18"


def test_import_skips_unknown_apartment_and_invalid_range():
    _seed_apartment(token="tok-stays-skip")
    content = _stays_csv(
        [
            [label for _key, label in stays_import.STAY_COLUMNS],
            ["Missing flat", "2026-09-15", "2026-09-18", "", "", ""],
            ["Stay import flat", "2026-09-18", "2026-09-15", "", "", ""],
        ]
    )
    result = stays_import.import_csv(content)
    assert result["imported"] == 0
    assert result["skipped"] == 2
    assert len(result["errors"]) == 2
    assert any("unknown apartment" in err.lower() for err in result["errors"])
    assert any("departure must be after arrival" in err.lower() for err in result["errors"])
