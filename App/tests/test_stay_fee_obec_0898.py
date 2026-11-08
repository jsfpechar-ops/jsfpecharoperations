"""0898: same-obec residence exemption (backend) and the shared charge computation.

Exact match after folding only; statutory-city district suffixes and the Prague
alias fold to the obec; a near miss is flagged for the host, never exempted.
Sealed periods keep their filed numbers (stay_fee_filing.frozen_summary).
"""
from __future__ import annotations

from datetime import date


from app import config, db, stay_fee, validation
from tests.test_stay_fee import AUG, _apartment, _apt, _entity, _stay, owner  # noqa: F401
from tests.test_stay_fee_finalize import _property, _stay as _finalize_stay, host  # noqa: F401

CZ = validation.CZECH_CODE
FIRST, LAST = date(2026, 8, 1), date(2026, 8, 31)


def _guest(**kw):
    base = {"id": 1, "stay_from": "2026-08-10", "stay_to": "2026-08-14", "birth_date": "01011990",
            "fee_host_decision": None, "fee_host_reason": None, "res_country": CZ, "res_city": ""}
    base.update(kw)
    return base


PROPERTY = {"addr_obec": "Praha"}
RES = {"date_from": "2026-08-10", "date_to": "2026-08-14"}


def test_guest_period_without_apartment_keeps_the_old_output():
    share = stay_fee.guest_period(_guest(res_city="Praha"), RES, FIRST, LAST)
    assert share["liable_nights"] == 4
    assert "auto_obec_resident" not in share and "obec_near_miss" not in share


def test_obec_rule_is_inert_without_a_cz_resident_match():
    share = stay_fee.guest_period(_guest(res_city="Praha", res_country="DEU"), RES, FIRST, LAST,
                                  apartment=PROPERTY)
    assert share["liable_nights"] == 4 and share["auto_obec_resident"] is False


def test_cz_resident_of_the_same_obec_is_exempt_with_the_obec_flag():
    share = stay_fee.guest_period(_guest(res_city="Praha"), RES, FIRST, LAST, apartment=PROPERTY)
    assert (share["liable_nights"], share["exempt_nights"]) == (0, 4)
    assert share["status"] == "exempt" and share["auto_obec_resident"] is True


def test_host_exempt_decision_is_not_flagged_as_automatic():
    share = stay_fee.guest_period(_guest(res_city="Praha", fee_host_decision="exempt"), RES,
                                  FIRST, LAST, apartment=PROPERTY)
    assert share["status"] == "exempt" and share["auto_obec_resident"] is False


def test_host_charge_decision_beats_a_same_obec_match():
    share = stay_fee.guest_period(_guest(res_city="Praha 5", fee_host_decision="charge"), RES,
                                  FIRST, LAST, apartment=PROPERTY)
    assert share["liable_nights"] == 4 and share["exempt_nights"] == 0
    assert share["status"] == "liable" and share["auto_obec_resident"] is False


def test_typo_is_liable_and_has_no_flag():
    for city in ("Prha", "Olomuc", "Praga", "Brod"):
        share = stay_fee.guest_period(_guest(res_city=city), RES, FIRST, LAST, apartment=PROPERTY)
        assert share["liable_nights"] == 4, city
        assert share["auto_obec_resident"] is False and "obec_near_miss" not in share, city


def test_different_obec_is_liable_and_not_a_near_miss():
    share = stay_fee.guest_period(_guest(res_city="Brno"), RES, FIRST, LAST, apartment=PROPERTY)
    assert share["liable_nights"] == 4


def test_scope_boundary_clears_the_obec_flags():
    apt = {"addr_obec": "Praha", "stay_fee_scope_rule": "calendar_days"}
    share = stay_fee.guest_period(_guest(res_city="Praha", stay_from="2026-07-01",
                                         stay_to="2026-08-31"),
                                  {"date_from": "2026-07-01", "date_to": "2026-08-31"},
                                  date(2026, 7, 1), date(2026, 8, 31), apartment=apt)
    assert share["status"] == "not_subject"
    assert share["auto_obec_resident"] is False


def test_same_obec_matching_rules():
    apt = {"addr_obec": "Praha"}
    matches = ["Praha", "PRAHA", "praha", "Praha 5", "Praha-Smíchov", "praha 1", "Prague", "Praha 5 "]
    for city in matches:
        assert stay_fee.same_obec_resident(_guest(res_city=city), apt), city
    refusals = ["Brno", "Prha", "Olomuc", "", "Kladno", "Praha 5 Brno"]
    for city in refusals:
        assert not stay_fee.same_obec_resident(_guest(res_city=city), apt), city
    assert not stay_fee.same_obec_resident(_guest(res_city="Praha", res_country="DEU"), apt)
    assert stay_fee.same_obec_resident(_guest(res_city="Brno-střed"), {"addr_obec": "Brno"})
    assert not stay_fee.same_obec_resident(_guest(res_city="Brno-střed"), {"addr_obec": "Praha"})


def test_fold_text_folds_diacritics_case_and_space():
    assert stay_fee.fold_text("  Příbram   nad  Vltavou ") == "PRIBRAM NAD VLTAVOU"


def _charge_setup(owner_id, **apt_kw):
    ent = _entity(owner_id)
    return _apartment(owner_id, ent, "Obec test", addr_obec="Praha", **apt_kw)


def test_charge_for_reservation_applies_the_rules(owner, monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    aid = _charge_setup(owner)
    rid = _stay(aid, "2026-08-10", "2026-08-14", [
        {"first_name": "Adult"},
        {"birth_date": "01012015"},                              # minor: exempt
        {"res_country": CZ, "res_city": "Praha 5"},              # same obec: exempt
        {"res_country": CZ, "res_city": "Brno"},                 # other obec: liable
        {"res_country": CZ, "res_city": "Prha"},                 # typo: liable
        {"fee_host_decision": "exempt"},                         # host: exempt
    ])
    charge = stay_fee.charge_for_reservation(_apt(aid), {"id": rid})
    assert charge["rate_czk"] == 50
    assert charge["liable_nights"] == 12 and charge["total_czk"] == 600
    flags = [(line["liable_nights"], line["auto_obec_resident"]) for line in charge["lines"]]
    assert flags == [(4, False), (0, False), (0, True), (4, False), (4, False), (0, False)]


def test_charge_for_reservation_more_than_60_nights_is_not_subject(owner, monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    aid = _charge_setup(owner)
    rid = _stay(aid, "2026-08-01", "2026-10-01", [{}])            # 61 nights
    charge = stay_fee.charge_for_reservation(_apt(aid), {"id": rid})
    assert charge["total_czk"] == 0 and charge["lines"][0]["status"] == "not_subject"


def test_charge_counts_unsigned_excludes_demo_and_respects_the_kill_switch(owner, monkeypatch):
    aid = _charge_setup(owner)
    rid = _stay(aid, "2026-08-10", "2026-08-14", [{}])
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    assert stay_fee.charge_for_reservation(_apt(aid), {"id": rid}) is None
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    unsigned = _stay(aid, "2026-08-10", "2026-08-14", [{"signature_png": None}])
    assert len(stay_fee.charge_for_reservation(_apt(aid), {"id": unsigned})["lines"]) == 1
    demo = _stay(aid, "2026-08-10", "2026-08-14", [{}])
    db.update("reservation", demo, {"source": "demo"})
    assert stay_fee.charge_for_reservation(_apt(aid), {"id": demo})["lines"] == []


def test_charge_total_matches_the_live_register(owner, monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    aid = _charge_setup(owner)
    rid = _stay(aid, "2026-08-10", "2026-08-14", [
        {}, {"res_country": CZ, "res_city": "Praha 5"}, {"res_country": CZ, "res_city": "Prha"},
    ])
    charge = stay_fee.charge_for_reservation(_apt(aid), {"id": rid})
    register = stay_fee.property_period(_apt(aid), AUG, live_only=True)
    assert register["liable_nights"] == charge["liable_nights"] == 8
    assert register["total_czk"] == charge["total_czk"] == 400


def test_sealed_period_keeps_its_filed_numbers_after_the_same_obec_rule(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    db.update("apartment", apartment_id, {"addr_obec": "Praha"})
    _finalize_stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    db.update("guest", guest_id, {"res_country": CZ, "res_city": "Brno"})
    page = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    token = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    saved = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": token, "month": "2026-08", "rate_czk": "50", "confirm_collected": "1",
              f"collected_{guest_id}": "200"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    sealed = stay_fee.property_period(_apt(apartment_id), FIRST)
    assert sealed["liable_nights"] == 4 and sealed["total_czk"] == 200
    # The guest now declares a Praha residence: the live register drops them, the sealed one does not.
    db.update("guest", guest_id, {"res_city": "Praha"})
    live = stay_fee.property_period(_apt(apartment_id), FIRST, live_only=True)
    assert live["liable_nights"] == 0
    filed = stay_fee.property_period(_apt(apartment_id), FIRST)
    assert (filed["liable_nights"], filed["total_czk"]) == (4, 200)


def test_same_obec_reason_shows_only_for_the_automatic_exemption(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    db.update("apartment", apartment_id, {"addr_obec": "Praha"})
    _finalize_stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    reason = "exempt automatically, from the city the guest declared"
    db.update("guest", guest_id, {"res_country": CZ, "res_city": "Praha 5"})
    page = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert reason in page.text and "Check residence" not in page.text
    db.update("guest", guest_id, {"res_city": "Prha"})
    page = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert reason not in page.text and "Check residence" not in page.text
