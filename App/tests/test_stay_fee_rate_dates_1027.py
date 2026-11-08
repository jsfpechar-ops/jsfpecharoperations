"""Brief 1027: dated stay-fee rates, each counted night priced at the rate in force."""
from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

import pytest

from app import (auth, config, db, stay_fee, stay_fee_adjustment, stay_fee_filing,
                 stay_fee_rate, stay_fee_remittance_pdf)

SIGNATURE = "data:image/png;base64,AAAA"
MARCH = date(2026, 3, 1)


def _apartment(rate: int = 30) -> dict:
    db.init_db()
    username = f"fee-dates-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Dates", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Dates s.r.o.", "owner_user_id": owner,
                                        "created_at": db.utcnow()})
    apartment_id = db.insert("apartment", {
        "internal_name": "Dates loft",
        "owner_user_id": owner,
        "legal_entity_id": entity,
        "stay_fee_rate_czk": rate,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
        "stay_fee_cadence": "monthly",
        "active": 1,
        "created_at": db.utcnow(),
    })
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def _stay(apartment_id: int, date_from: str = "2026-03-10", date_to: str = "2026-03-14") -> dict:
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id, "uid": f"dates-{secrets.token_hex(3)}",
        "date_from": date_from, "date_to": date_to, "status": "active",
        "created_at": now, "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": rid, "first_name": "Ada", "surname": "Guest",
        "birth_date": "01011990", "nationality": "DEU", "signature_png": SIGNATURE,
        "created_at": now, "updated_at": now,
    })
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (rid,))


def _rate_row(apartment_id: int, rate: int, effective_from: str) -> None:
    db.insert("stay_fee_rate", {"apartment_id": apartment_id, "rate_czk": rate,
                                "effective_from": effective_from, "created_at": db.utcnow()})


def _mixed() -> tuple:
    """Rate 30, then 40 from 13 March; one adult stays 10-14 March (nights 11..14)."""
    apartment = _apartment(40)
    _rate_row(apartment["id"], 30, "2000-01-01")
    _rate_row(apartment["id"], 40, "2026-03-13")
    reservation = _stay(apartment["id"])
    return apartment, reservation


def test_backfill_row_exists_and_totals_identical():
    sql = (Path(__file__).resolve().parents[1] / "app/migrations/0038_stay_fee_rate_history.sql").read_text()
    assert "'2000-01-01'" in sql and "ON CONFLICT" in sql
    plain = _apartment(30)
    _stay(plain["id"])
    backfilled = _apartment(30)
    _rate_row(backfilled["id"], 30, "2000-01-01")
    _stay(backfilled["id"])
    one = stay_fee.property_period(plain, MARCH, live_only=True)
    two = stay_fee.property_period(backfilled, MARCH, live_only=True)
    assert one["liable_nights"] == two["liable_nights"] == 4
    assert one["total_czk"] == two["total_czk"] == 4 * 30
    assert one["rate_segments"] == two["rate_segments"] == [[30, 4]]


def test_rate_change_mid_stay_prices_each_night():
    apartment, _ = _mixed()
    period = stay_fee.property_period(apartment, MARCH, live_only=True)
    assert period["total_czk"] == 2 * 30 + 2 * 40 == 140
    assert period["lines"][0]["amount_czk"] == 140
    assert period["lines"][0]["rate_nights"] == [[30, 2], [40, 2]]
    assert period["rate_czk"] == 40
    assert period["rate_segments"] == [[30, 2], [40, 2]]


def test_sealed_period_is_not_repriced():
    apartment, _ = _mixed()
    filing_id = stay_fee_filing.save(apartment, MARCH, rate_czk=None, collected={},
                                     issued_on=date(2026, 4, 2))
    row = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (filing_id,))
    assert row["total_due_czk"] == 140 and row["rate_czk"] == 40
    _rate_row(apartment["id"], 99, "2026-05-01")
    frozen = stay_fee.property_period(apartment, MARCH)
    assert frozen["frozen"] is True
    assert frozen["total_czk"] == 140
    assert frozen["rate_segments"] == [[30, 2], [40, 2]]
    assert stay_fee_filing.correction_rate(apartment, row) is None


def test_legacy_flat_sealed_period_keeps_its_rate_for_corrections():
    apartment = _apartment(30)
    _stay(apartment["id"])
    filing_id = stay_fee_filing.save(apartment, MARCH, rate_czk=30, collected={},
                                     issued_on=date(2026, 4, 2))
    _rate_row(apartment["id"], 30, "2000-01-01")
    _rate_row(apartment["id"], 99, "2026-05-01")
    row = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (filing_id,))
    assert stay_fee_filing.frozen_summary(row, apartment)["rate_segments"] == [[30, 4]]
    assert stay_fee_filing.correction_rate(apartment, row) == 30


def test_hlaseni_splits_mixed_period_rows():
    apartment, _ = _mixed()
    period = stay_fee.property_period(apartment, MARCH, live_only=True)
    group = stay_fee.report_group(apartment, MARCH, live_only=True, period=period,
                                  cadence="monthly")
    report = stay_fee.hlaseni(group, date(2026, 4, 2))
    rows = report["rows"]
    assert [(r["rate_czk"], r["liable_nights"], r["amount_czk"]) for r in rows] == [
        (30, 2, 60), (40, 2, 80)]
    assert sum(r["amount_czk"] for r in rows) == group["total_czk"] == 140
    assert sum(r["liable_nights"] for r in rows) == report["liable_nights"] == 4
    assert stay_fee_remittance_pdf.render(report)[:4] == b"%PDF"


def _adjust(apartment, direction: str, bed_days: int) -> None:
    stay_fee_adjustment.add(apartment_id=apartment["id"], period_key="2026-03",
                            direction=direction, mode="bed_days", people_count=0,
                            nights=0, bed_days=bed_days, reason="test",
                            created_by=apartment["owner_user_id"])


def test_adjustment_priced_at_last_day_rate():
    apartment, _ = _mixed()
    _adjust(apartment, "add", 2)
    period = stay_fee.property_period(apartment, MARCH, live_only=True)
    assert period["total_czk"] == 140 + 2 * 40
    assert period["rate_segments"] == [[30, 2], [40, 4]]


def test_large_removal_keeps_rows_consistent():
    apartment, _ = _mixed()
    _adjust(apartment, "remove", 3)
    period = stay_fee.property_period(apartment, MARCH, live_only=True)
    # Two 40-nights removed, the third removal comes off the 30 rate.
    assert period["liable_nights"] == 1
    assert period["rate_segments"] == [[30, 1]]
    assert period["total_czk"] == 30
    group = stay_fee.report_group(apartment, MARCH, live_only=True, period=period,
                                  cadence="monthly")
    stay_fee_remittance_pdf.validate(stay_fee.hlaseni(group, date(2026, 4, 2)))


def test_over_60_nights_still_zero():
    apartment, _ = _mixed()
    long_stay = _apartment(30)
    _stay(long_stay["id"], "2026-03-01", "2026-05-01")
    period = stay_fee.property_period(long_stay, MARCH, live_only=True)
    assert period["lines"][0]["amount_czk"] == 0
    assert period["lines"][0]["rate_nights"] == []
    assert period["total_czk"] == 0


def test_charge_for_reservation_prices_per_night(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    apartment, reservation = _mixed()
    charge = stay_fee.charge_for_reservation(apartment, reservation)
    assert charge["total_czk"] == 140 and charge["mixed"] is True
    assert charge["lines"][0]["amount_czk"] == 140
    plain = _apartment(30)
    flat = stay_fee.charge_for_reservation(plain, _stay(plain["id"]))
    assert flat["total_czk"] == 120 and flat["mixed"] is False


def test_record_rules():
    apartment = _apartment(30)
    with pytest.raises(ValueError):
        stay_fee_rate.record(apartment["id"], 40, date(2026, 3, 13), today=date(2026, 3, 20))
    assert stay_fee_rate.record(apartment["id"], 40, date(2026, 3, 13), today=date(2026, 3, 1))
    assert not stay_fee_rate.record(apartment["id"], 40, date(2026, 3, 13), today=date(2026, 3, 1))
    assert stay_fee_rate.record(apartment["id"], 45, date(2026, 3, 13), today=date(2026, 3, 1))
    rows = db.query("SELECT effective_from, rate_czk FROM stay_fee_rate WHERE apartment_id = ? "
                    "ORDER BY effective_from", (apartment["id"],))
    # The first record keeps the old rate for earlier nights (baseline at 2000-01-01).
    assert [(r["effective_from"], r["rate_czk"]) for r in rows] == [
        ("2000-01-01", 30), ("2026-03-13", 45)]


def test_record_baseline_uses_previous_rate_or_first_rate():
    changed = _apartment(45)  # column already written by the save
    assert stay_fee_rate.record(changed["id"], 45, date(2026, 3, 13), previous=30,
                                today=date(2026, 3, 13))
    assert stay_fee_rate.schedule_for(changed) == [(date(2000, 1, 1), 30), (date(2026, 3, 13), 45)]
    first = _apartment(25)  # fee switched on: 0 -> 25 applies from the beginning
    assert not stay_fee_rate.record(first["id"], 25, date(2026, 3, 13), previous=0,
                                    today=date(2026, 3, 13))
    assert stay_fee_rate.schedule_for(first) == [(date(2000, 1, 1), 25)]
