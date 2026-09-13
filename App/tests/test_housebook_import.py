"""House book CSV import (historical rows, Czech date formats)."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from app import db, housebook, reporting


def _seed_apartment(name: str = "Import flat", token: str = "tok-import") -> int:
    db.init_db()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": f"Import Test {token}", "seat": "Praha", "ico": "12345678", "created_at": now},
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


def _housebook_csv(**overrides: str) -> bytes:
    row = {**housebook.SAMPLE_HOUSEBOOK_ROW, **overrides}
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([label for _key, label in housebook.HOUSEBOOK_COLUMNS])
    writer.writerow([row.get(key, "") for key, _label in housebook.HOUSEBOOK_COLUMNS])
    return buffer.getvalue().encode("utf-8")


def test_import_parses_czech_dates_and_residence():
    apartment_id = _seed_apartment(token="tok-hb-dates")
    today = date.today()
    stay_from = (today - timedelta(days=30)).strftime("%d.%m.%Y")
    stay_to = (today - timedelta(days=20)).strftime("%d.%m.%Y")
    content = _housebook_csv(
        stay_from=stay_from,
        stay_to=stay_to,
        birth_date="15.03.1985",
        residence="Baker Street 221B, London, GBR",
        reported="not yet",
        signed="no",
    )
    result = housebook.import_csv(content, apartment_id)
    assert result["imported"] == 1
    assert not result["errors"]

    guest = db.query_one(
        "SELECT * FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    assert guest["stay_from"] == (today - timedelta(days=30)).isoformat()
    assert guest["stay_to"] == (today - timedelta(days=20)).isoformat()
    assert guest["birth_date"] == "15031985"
    assert guest["res_street"] == "Baker Street 221B"
    assert guest["res_city"] == "London"
    assert guest["res_country"] == "GBR"
    assert guest["submit_state"] == reporting.PENDING
    assert not reporting.guest_has_signature(guest)


def test_import_marks_reported_rows_as_sent_with_imported_signature():
    apartment_id = _seed_apartment(token="tok-hb-reported")
    content = _housebook_csv(reported="yes", signed="yes", reported_at="2026-09-04")
    result = housebook.import_csv(content, apartment_id)
    assert result["imported"] == 1

    guest = db.query_one(
        "SELECT * FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    assert guest["submit_state"] == reporting.SENT
    assert guest["submitted_at"] == "2026-09-04"
    assert reporting.guest_has_signature(guest)


def test_import_rejects_missing_required_columns():
    apartment_id = _seed_apartment(token="tok-hb-cols")
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Stay from", "Stay to"])
    writer.writerow(["2026-01-01", "2026-01-05"])
    result = housebook.import_csv(buffer.getvalue().encode("utf-8"), apartment_id)
    assert result["imported"] == 0
    assert any("required columns" in err.lower() for err in result["errors"])


def test_import_is_idempotent_for_same_stay_line():
    apartment_id = _seed_apartment(token="tok-hb-idem")
    content = _housebook_csv()
    first = housebook.import_csv(content, apartment_id)
    second = housebook.import_csv(content, apartment_id)
    assert first["imported"] == 1
    assert second["imported"] == 1
    reservations = db.query(
        "SELECT id FROM reservation WHERE apartment_id = ? AND source = 'import'",
        (apartment_id,),
    )
    assert len(reservations) == 1
