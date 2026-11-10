"""Brief 1084 (F2, P5): one rule for the guest pay ways and the QR code.

The stay page panel (routes.guest._fee_pay_panel) and the completion mail
(claim._completion_fee) both read stay_fee.guest_pay_ways, so for the same stay
they list the same ways, in the same order, and both carry the QR or neither.
The QR follows the stay (any Czech or Slovak guest), never the device.
"""
from __future__ import annotations

import inspect
import pathlib

import pytest

from app import claim, config, db, i18n, stay_fee
from app.routes import guest as guest_routes
from tests.test_completion_fee_mail_1077 import _completion, _fee

OWNER = "pay-rule-1084"
IBAN = "CZ6508000000192000145399"
SIG = "data:image/png;base64,AAAA"
T = i18n.translator("en")


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (OWNER,)):
        oid = row["id"]
        db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
                   "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)", (oid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN "
                   "(SELECT id FROM apartment WHERE owner_user_id = ?)", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def flat():
    """An apartment that collects, with an IBAN, all three ways, a Revolut link and a cash note."""
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "Pay rule", "created_at": db.utcnow()})
    entity = db.insert("legal_entity", {"name": "Pay Rule s.r.o.", "owner_user_id": oid,
                                        "iban": IBAN, "created_at": db.utcnow()})
    aid = db.insert("apartment", {
        "internal_name": "Pay rule flat", "owner_user_id": oid, "legal_entity_id": entity,
        "addr_obec": "Praha", "stay_fee_rate_czk": 30, "stay_fee_vs": "1234567890",
        "stay_fee_cadence": "monthly", "stay_fee_collect": 1,
        "stay_fee_guest_rails": "iban,revolut,cash",
        "stay_fee_guest_revolut_link": "https://revolut.me/host",
        "stay_fee_guest_cash_note": "At the reception desk.",
        "permalink_token": "tok-pay-rule-1084", "created_at": db.utcnow()})
    try:
        yield {"apartment": aid, "entity": entity, "owner": oid}
    finally:
        _cleanup()


def _apt(aid):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))


def _stay(aid, nationalities, archived=()):
    now = db.utcnow()
    rid = db.insert("reservation", {"apartment_id": aid, "uid": f"pay-rule-{len(nationalities)}-{now}",
                                    "date_from": "2026-07-10", "date_to": "2026-07-12",
                                    "status": "active", "created_at": now, "updated_at": now})
    for i, nationality in enumerate(nationalities):
        db.insert("guest", {"reservation_id": rid, "first_name": f"G{i}", "surname": "Rule",
                            "birth_date": "01011990", "nationality": nationality,
                            "res_country": "DEU", "res_city": "Berlin", "signature_png": SIG,
                            "archived_at": now if i in archived else None,
                            "created_at": now, "updated_at": now})
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (rid,))


def _both(aid, reservation):
    apartment = _apt(aid)
    panel = guest_routes._fee_pay_panel(apartment, reservation, T)
    fee = claim._completion_fee(apartment, reservation)
    assert panel is not None and fee is not None
    return panel, fee


def _bank(items):
    return next((item for item in items if item["key"] == "iban"), None)


# a. same stay, same ways


def test_screen_and_mail_list_the_same_ways(flat):
    res = _stay(flat["apartment"], ["DEU"])
    panel, fee = _both(flat["apartment"], res)
    assert [rail["key"] for rail in panel["rails"]] == [way["key"] for way in fee["ways"]]
    assert [rail["key"] for rail in panel["rails"]] == ["iban", "revolut", "cash"]
    assert _bank(panel["rails"])["iban"] == _bank(fee["ways"])["account"]
    assert panel["payee"] == _bank(fee["ways"])["payee"] == "Pay Rule s.r.o."


# b. the QR follows the stay


def test_a_czech_guest_gives_the_qr_on_both(flat):
    res = _stay(flat["apartment"], ["CZE", "DEU"])
    panel, fee = _both(flat["apartment"], res)
    assert _bank(panel["rails"])["qr"].startswith("data:image/")
    assert _bank(fee["ways"])["spayd"]


def test_no_czech_or_slovak_guest_gives_no_qr_on_both(flat):
    res = _stay(flat["apartment"], ["DEU", "FRA"])
    panel, fee = _both(flat["apartment"], res)
    assert _bank(panel["rails"])["qr"] == ""
    assert _bank(fee["ways"])["spayd"] == ""
    # Bank details still go to everyone.
    assert _bank(panel["rails"])["iban"] and _bank(fee["ways"])["account"]


def test_an_archived_czech_guest_does_not_count(flat):
    res = _stay(flat["apartment"], ["DEU", "CZE"], archived=(1,))
    panel, fee = _both(flat["apartment"], res)
    assert _bank(panel["rails"])["qr"] == ""
    assert _bank(fee["ways"])["spayd"] == ""


def test_a_lowercase_slovak_guest_counts(flat):
    res = _stay(flat["apartment"], ["DEU", "svk"])
    panel, fee = _both(flat["apartment"], res)
    assert _bank(panel["rails"])["qr"] and _bank(fee["ways"])["spayd"]


# c. the device does not matter


def test_the_panel_does_not_read_the_device(flat):
    assert "request" not in inspect.signature(guest_routes._fee_pay_panel).parameters
    source = pathlib.Path(guest_routes.__file__).read_text(encoding="utf-8")
    assert "_qr_offered" not in source
    assert "QR_NATIONALITIES" not in source
    assert not hasattr(stay_fee, "GUEST_RAIL_ORDER")
    # The phone's own guest is German; the Czech guest registered elsewhere.
    res = _stay(flat["apartment"], ["DEU", "CZE"])
    panel, fee = _both(flat["apartment"], res)
    assert _bank(panel["rails"])["qr"] and _bank(fee["ways"])["spayd"]


# d. no valid account: the bank way is left out on both


@pytest.mark.parametrize("entity_fields", [
    {"iban": None, "bank_account": None},
    {"iban": None, "bank_account": "12-ab/0800"},
])
def test_without_a_valid_account_neither_side_lists_the_bank(flat, entity_fields):
    db.update("legal_entity", flat["entity"], entity_fields)
    res = _stay(flat["apartment"], ["CZE"])
    panel, fee = _both(flat["apartment"], res)
    assert [rail["key"] for rail in panel["rails"]] == ["revolut", "cash"]
    assert [way["key"] for way in fee["ways"]] == ["revolut", "cash"]


# e. default way first


def test_the_default_way_comes_first_on_both(flat):
    db.update("apartment", flat["apartment"], {"stay_fee_guest_default_rail": "cash"})
    res = _stay(flat["apartment"], ["CZE"])
    panel, fee = _both(flat["apartment"], res)
    assert [rail["key"] for rail in panel["rails"]] == ["cash", "iban", "revolut"]
    assert [way["key"] for way in fee["ways"]] == ["cash", "iban", "revolut"]
    db.update("apartment", flat["apartment"], {"stay_fee_guest_default_rail": "qr"})
    panel, fee = _both(flat["apartment"], res)
    assert panel["rails"][0]["key"] == fee["ways"][0]["key"] == "iban"


# f. cash without a note


def test_cash_without_a_note_reads_the_same_default(flat):
    db.update("apartment", flat["apartment"], {"stay_fee_guest_cash_note": ""})
    res = _stay(flat["apartment"], ["DEU"])
    panel, fee = _both(flat["apartment"], res)
    default = T("fee_cash_default")
    assert panel["rails"][-1] == {"key": "cash", "note": default}
    assert fee["ways"][-1] == {"key": "cash", "note": ""}
    assert f"Cash: {default}" in _completion(_fee(fee["ways"]))["text"]


# g. idempotent and read-only


def test_the_rule_is_idempotent_and_writes_nothing(flat):
    res = _stay(flat["apartment"], ["CZE", "DEU"])
    apartment = _apt(flat["apartment"])
    charge = stay_fee.charge_for_reservation(apartment, res)
    counts = [db.query_one(f"SELECT COUNT(*) AS n FROM {table}")["n"]
              for table in ("guest", "reservation")]
    first = stay_fee.guest_pay_ways(apartment, res, charge)
    second = stay_fee.guest_pay_ways(apartment, res, charge)
    assert first == second
    assert [db.query_one(f"SELECT COUNT(*) AS n FROM {table}")["n"]
            for table in ("guest", "reservation")] == counts
