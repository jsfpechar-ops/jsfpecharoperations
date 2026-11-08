"""Brief 1028: callers of the dated stay-fee rates (seal, corrections, save hook, guest)."""
from __future__ import annotations

from datetime import date

from app import claim, config, db, stay_fee, stay_fee_auto, stay_fee_filing, stay_fee_rate
from app.routes import guest as guest_routes
from tests import test_property_form_save as form_save
from tests.test_property_form_save import host  # noqa: F401  (pytest fixture)
from tests.test_stay_fee_rate_dates_1027 import MARCH, _apartment, _mixed, _rate_row, _stay


def _sealed(apartment_id: int):
    return db.query_one("SELECT * FROM stay_fee_filing WHERE apartment_id = ? "
                        "AND superseded_at IS NULL", (apartment_id,))


def test_auto_seal_prices_per_night_and_stays_frozen():
    apartment, _ = _mixed()
    assert stay_fee_auto.confirm(apartment, MARCH, date(2026, 4, 2)) is not None
    row = _sealed(apartment["id"])
    assert row["rate_czk"] == 40 and row["total_due_czk"] == 140 and row["liable_days"] == 4
    assert stay_fee_filing.payload(row)["rate_segments"] == [[30, 2], [40, 2]]
    _rate_row(apartment["id"], 99, "2026-05-01")
    assert dict(_sealed(apartment["id"])) == dict(row)
    frozen = stay_fee.property_period(apartment, MARCH)
    assert frozen["frozen"] and frozen["total_czk"] == 140
    # Correction of a mixed period: priced per night again, same total.
    assert stay_fee_filing.correction_rate(apartment, row) is None
    again = stay_fee.property_period(apartment, MARCH, live_only=True,
                                     rate=stay_fee_filing.correction_rate(apartment, row))
    assert again["total_czk"] == 140


def test_correction_of_legacy_flat_period_keeps_its_rate():
    apartment = _apartment(30)
    _stay(apartment["id"])
    stay_fee_filing.save(apartment, MARCH, rate_czk=30, collected={}, issued_on=date(2026, 4, 2))
    _rate_row(apartment["id"], 30, "2000-01-01")
    _rate_row(apartment["id"], 99, "2026-05-01")
    db.update("apartment", apartment["id"], {"stay_fee_rate_czk": 99})
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment["id"],))
    row = _sealed(apartment["id"])
    assert stay_fee_filing.correction_rate(apartment, row) == 30
    period = stay_fee.property_period(apartment, MARCH, live_only=True, rate=30)
    assert period["total_czk"] == 120


def _rates(apartment_id: int):
    return [(r["effective_from"], r["rate_czk"]) for r in db.query(
        "SELECT effective_from, rate_czk FROM stay_fee_rate WHERE apartment_id = ? "
        "ORDER BY effective_from", (apartment_id,))]


def _save_rate(client, apartment_id: int, rate: int, **extra):
    data = form_save._payload(stay_fee_rate_czk=str(rate), **extra)
    response = client.post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text[:300]
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def test_editor_rate_change_writes_a_dated_row(host, monkeypatch):  # noqa: F811
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 3, 12))
    apartment_id = form_save._apartment()["id"]
    first = _save_rate(host, apartment_id, 30)
    assert first["stay_fee_rate_czk"] == 30
    assert _rates(apartment_id) == [("2000-01-01", 30)]
    _stay(apartment_id)
    changed = _save_rate(host, apartment_id, 45, stay_fee_rate_from="2026-03-12")
    assert _rates(apartment_id) == [("2000-01-01", 30), ("2026-03-12", 45)]
    schedule = stay_fee_rate.schedule_for(changed)
    assert stay_fee_rate.rate_on(schedule, date(2026, 3, 11)) == 30
    assert stay_fee_rate.rate_on(schedule, date(2026, 3, 12)) == 45
    # Unchanged rate: no row. Past date: clamped to today. No date: today.
    _save_rate(host, apartment_id, 45, stay_fee_rate_from="2026-03-20")
    assert len(_rates(apartment_id)) == 2
    _save_rate(host, apartment_id, 50, stay_fee_rate_from="2026-01-01")
    assert _rates(apartment_id)[-1] == ("2026-03-12", 50)
    _save_rate(host, apartment_id, 35, stay_fee_rate_from="not-a-date")
    assert _rates(apartment_id)[-1] == ("2026-03-12", 35)
    _save_rate(host, apartment_id, 40, stay_fee_rate_from="2026-04-01")
    assert _rates(apartment_id)[-1] == ("2026-04-01", 40)


def _guest_apartment(apartment):
    db.update("apartment", apartment["id"], {"stay_fee_collect": 1})
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment["id"],))


def test_guest_estimate_across_a_rate_change(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    apartment, reservation = _mixed()
    estimate = guest_routes._fee_estimate(_guest_apartment(apartment), reservation, {})
    assert estimate["amount"] == 140 and estimate["days"] == 4
    assert estimate["live"] is None


def test_guest_estimate_single_rate_keeps_live(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    apartment = _apartment(30)
    reservation = _stay(apartment["id"])
    estimate = guest_routes._fee_estimate(_guest_apartment(apartment), reservation, {})
    assert estimate["amount"] == 120 and estimate["rate"] == 30
    assert estimate["live"] == {"from": "2026-03-10", "to": "2026-03-14", "rate": 30}


def test_pay_panel_register_and_qr_agree_across_a_rate_change(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    apartment, reservation = _mixed()
    apartment = _guest_apartment(apartment)
    db.update("apartment", apartment["id"], {"stay_fee_guest_rails": "iban"})
    db.update("legal_entity", apartment["legal_entity_id"], {"iban": "CZ6508000000192000145399"})
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment["id"],))
    panel = guest_routes._fee_pay_panel(apartment, reservation, lambda key, **kw: key)
    assert panel["total"] == 140
    assert [p["amount"] for p in panel["persons"]] == [140]
    assert panel["rails"][0]["qr"]
    from app import payments
    assert "AM:140" in payments.spayd("CZ6508000000192000145399", panel["total"], panel["vs"], "x")
    period = stay_fee.property_period(apartment, MARCH, live_only=True)
    register = stay_fee.register_rows(period)
    assert [r["amount_czk"] for r in register] == [140]
    assert period["total_czk"] == panel["total"]
