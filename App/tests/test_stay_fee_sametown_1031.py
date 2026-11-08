"""1031: the form route carries the same-town rule; minors and residents owe nothing in every
birth format; the Check box, pay panel, charge and council register give one number."""
from __future__ import annotations

import json
from datetime import date, timedelta
from html import unescape

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, config, db, stay_fee
from app.main import app
from app.routes import guest as guest_routes
from tests.conftest import complete_guest_claim
from tests.test_stay_fee_audit_1025 import _apt, _register_total, _stay, flat  # noqa: F401

USER = "sametown-1031"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USER,)):
        uid = row["id"]
        db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
                   "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN "
                   "(SELECT id FROM apartment WHERE owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _seed(token, addr_obec, city_en=None):
    now = db.utcnow()
    today = claim.prague_today()
    host = auth.create_account(f"{token}@example.test", "Same town", username=USER)
    entity = db.insert("legal_entity", {
        "name": "Same town entity", "seat": "Praha 1", "ico": "12345678",
        "contact_email": "pm@example.test", "iban": "CZ6508000000192000145399",
        "owner_user_id": host, "created_at": now})
    apartment = db.insert("apartment", {
        "legal_entity_id": entity, "owner_user_id": host, "internal_name": "Same town flat",
        "uby_name": "Same town", "permalink_token": token, "permalink_window_days": 14,
        "default_purpose": "10", "passport_photo_policy": "off", "automation_mode": "manual",
        "active": 1, "created_at": now, "addr_obec": addr_obec, "city_en": city_en,
        "stay_fee_collect": 1, "stay_fee_rate_czk": 50, "stay_fee_vs": "1234567890",
        "stay_fee_cadence": "monthly", "stay_fee_guest_rails": "iban"})
    reservation = db.insert("reservation", {
        "apartment_id": apartment, "source": "airbnb", "uid": f"{token}-stay",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=3)).isoformat(),
        "declared_guests": 1, "status": "active", "created_at": now, "updated_at": now})
    return apartment, reservation


def _form_html(token, reservation):
    client = TestClient(app)
    complete_guest_claim(client, token, reservation, party_size=1, lang="en")
    page = client.get(f"/l/{token}/{reservation}/new?lang=en")
    assert page.status_code == 200, page.text[:300]
    return page.text


def _rule(html):
    if 'data-obec-rule="' not in html:
        return None
    return json.loads(unescape(html.split('data-obec-rule="')[1].split('"')[0]))


@pytest.mark.parametrize("addr_obec, city_en", [
    ("Praha", None), ("Praha 1 - Staré Město", None), ("Hlavní město Praha", None),
    ("Hl. m. Praha", None), ("Praha, Staré Město", None), ("", "Prague"), (None, "Prague"),
])
def test_form_route_carries_the_prague_rule(addr_obec, city_en):
    _apartment, reservation = _seed("sametown1031a", addr_obec, city_en)
    html = _form_html("sametown1031a", reservation)
    assert 'id="fee-estimate"' in html and "data-fee-live" in html
    rule = _rule(html)
    assert rule is not None and rule["obec"] == "PRAHA" and rule["country"] == "CZE"
    assert 'id="fee-obec-unknown"' not in html


def test_form_route_without_a_property_town_says_so():
    _apartment, reservation = _seed("sametown1031b", "", None)
    html = _form_html("sametown1031b", reservation)
    assert 'id="fee-estimate"' in html and _rule(html) is None
    assert 'id="fee-obec-unknown"' in html


APT = {"stay_fee_collect": 1, "stay_fee_rate_czk": 50, "addr_obec": "Praha", "legal_entity_id": None}
RES = {"id": 7, "date_from": "2026-07-01", "date_to": "2026-07-04"}


@pytest.mark.parametrize("birth", ["15.06.2010", "15062010", "15/06/2010", "15-06-2010"])
@pytest.mark.parametrize("city", ["Prague", "Brno"])
def test_minor_owes_nothing_in_every_birth_format(birth, city):
    typed = {"birth_date": birth, "res_country": "CZE", "res_city": city}
    assert guest_routes._fee_estimate(APT, RES, typed) is None


@pytest.mark.parametrize("city", ["Prague", "Praha", "Praha 3 - Žižkov", "Hlavní město Praha", "prague"])
def test_adult_from_the_same_town_owes_nothing(city):
    typed = {"birth_date": "15.06.2001", "res_country": "CZE", "res_city": city}
    assert guest_routes._fee_estimate(APT, RES, typed) is None


def test_adult_from_another_town_owes_nights_times_the_rate():
    typed = {"birth_date": "15.06.2001", "res_country": "CZE", "res_city": "Brno"}
    other = guest_routes._fee_estimate(APT, RES, typed)
    assert (other["amount"], other["days"], other["rate"]) == (150, 3, 50)


@pytest.mark.parametrize("obec", ["Praha", "Hlavní město Praha", "Praha 1 - Staré Město"])
def test_preview_pay_panel_charge_and_register_agree(flat, obec):  # noqa: F811
    db.update("apartment", flat, {"addr_obec": obec})
    cz = {"nationality": "CZE", "res_country": "CZE"}
    res = _stay(flat, "2026-07-01", "2026-07-04", [
        dict(cz, birth_date="15062010", res_city="Prague"),   # minor: 0
        dict(cz, birth_date="15062001", res_city="Prague"),   # same town: 0
        dict(cz, birth_date="15062001", res_city="Brno"),     # other town: 3 nights
    ])
    apartment = _apt(flat)
    rate = int(apartment["stay_fee_rate_czk"])
    charge = stay_fee.charge_for_reservation(apartment, res)
    assert (charge["total_czk"], charge["liable_nights"]) == (3 * rate, 3)
    panel = guest_routes._fee_pay_panel(apartment, res, lambda key, **kw: key)
    assert panel["total"] == 3 * rate
    assert _register_total(apartment, date(2026, 7, 1), 1) == (3 * rate, 3)
    previews = [guest_routes._fee_estimate(apartment, res, {"birth_date": b, "res_country": "CZE", "res_city": c})
                for b, c in (("15.06.2010", "Prague"), ("15.06.2001", "Prague"), ("15.06.2001", "Brno"))]
    assert sum(p["amount"] for p in previews if p) == charge["total_czk"]


def test_period_lines_carry_their_own_amount_and_the_total_is_their_sum(flat):  # noqa: F811
    """1031 step 7: the register and the stay-fee page read each guest's amount from the
    shared period; the lines add up to the same total the charge gives."""
    cz = {"nationality": "CZE", "res_country": "CZE"}
    res = _stay(flat, "2026-07-01", "2026-07-04", [
        dict(cz, birth_date="15062010", res_city="Prague"),
        dict(cz, birth_date="15062001", res_city="Prague"),
        dict(cz, birth_date="15062001", res_city="Brno"),
    ])
    apartment = _apt(flat)
    period = stay_fee.property_period(apartment, date(2026, 7, 1), live_only=True)
    mine = [line for line in period["lines"] if line["reservation_id"] == res["id"]]
    assert mine and all("amount_czk" in line for line in mine)
    assert sum(line["amount_czk"] for line in mine) == stay_fee.charge_for_reservation(apartment, res)["total_czk"]
