"""1071: the host is told at once when stay-fee collection is on and no guest pay way works."""
from __future__ import annotations

import pytest

from app import alerts, config, db, stay_fee

OWNER = "no-pay-way-1071"
IBAN = "CZ6508000000192000145399"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (OWNER,)):
        oid = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


@pytest.fixture
def flat():
    """A property that collects by bank transfer, with an operator that has no account yet."""
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "NoPayWay", "created_at": db.utcnow()})
    entity = db.insert("legal_entity", {"name": "NoPayWay s.r.o.", "owner_user_id": oid,
                                        "created_at": db.utcnow()})
    aid = db.insert("apartment", {
        "internal_name": "Loft 1071", "owner_user_id": oid, "legal_entity_id": entity,
        "addr_obec": "Praha", "stay_fee_rate_czk": 30, "stay_fee_collect": 1,
        "stay_fee_guest_rails": "iban", "permalink_token": "tok-1071",
        "created_at": db.utcnow()})
    try:
        yield {"apartment": aid, "entity": entity}
    finally:
        _cleanup()


def _key(aid):
    return f"stay_fee_no_pay_way:{aid}"


def _update(aid, **values):
    db.update("apartment", aid, values)


def test_the_alert_is_raised_at_once_when_the_only_way_has_no_account(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    row = alerts.open_alert(_key(aid))
    assert row is not None
    assert row["level"] == "warning" and row["kind"] == "stay_fee_no_pay_way"
    assert row["message"] == "Guests cannot pay the stay fee: add a bank account"


def test_raising_twice_keeps_one_open_alert(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    stay_fee.reconcile_no_pay_way_alert(aid)
    rows = db.query("SELECT id FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (_key(aid),))
    assert len(rows) == 1


def test_it_resolves_itself_when_a_bank_account_is_added(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is not None
    db.update("legal_entity", flat["entity"], {"iban": IBAN})
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_it_resolves_itself_when_collection_is_turned_off(flat):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    _update(aid, stay_fee_collect=0)
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_cash_alone_is_a_working_way_so_there_is_no_alert(flat):
    aid = flat["apartment"]
    _update(aid, stay_fee_guest_rails="cash")
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_revolut_without_a_link_does_not_work(flat):
    aid = flat["apartment"]
    _update(aid, stay_fee_guest_rails="revolut")
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is not None
    _update(aid, stay_fee_guest_revolut_link="https://revolut.me/loft")
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_the_guest_box_and_the_alert_share_one_rule(flat):
    aid = flat["apartment"]
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))
    assert stay_fee.usable_rail_keys(apartment) == []
    db.update("legal_entity", flat["entity"], {"iban": IBAN})
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))
    assert stay_fee.usable_rail_keys(apartment) == ["iban"]


def test_a_malformed_bank_account_is_treated_as_missing(flat):
    """#868 hardened guest_pay_ways; payout_account / the 1071 alert still raised."""
    aid = flat["apartment"]
    db.update("legal_entity", flat["entity"], {"bank_account": "12-ab/0800"})
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))
    assert stay_fee.payout_account(apartment) == ("", "NoPayWay s.r.o.")
    assert stay_fee.usable_rail_keys(apartment) == []
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is not None


def test_cash_still_works_when_the_stored_bank_account_is_malformed(flat):
    aid = flat["apartment"]
    db.update("legal_entity", flat["entity"], {"bank_account": "12-ab/0800"})
    _update(aid, stay_fee_guest_rails="iban,cash")
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))
    assert stay_fee.usable_rail_keys(apartment) == ["cash"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_collection_on_with_rate_zero_raises_no_alert(flat):
    aid = flat["apartment"]
    _update(aid, stay_fee_collect=1, stay_fee_rate_czk=0)
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_the_deployment_switch_off_means_no_alert(flat, monkeypatch):
    aid = flat["apartment"]
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", False)
    stay_fee.reconcile_no_pay_way_alert(aid)
    assert alerts.open_alert(_key(aid)) is None


def test_the_daily_sweep_raises_and_resolves(flat):
    aid = flat["apartment"]
    assert stay_fee.reconcile_all_no_pay_way() >= 1
    assert alerts.open_alert(_key(aid)) is not None
    _update(aid, stay_fee_collect=0)
    stay_fee.reconcile_all_no_pay_way()
    assert alerts.open_alert(_key(aid)) is None


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_the_card_reads_in_every_host_language_and_never_says_paid(flat, lang):
    aid = flat["apartment"]
    stay_fee.reconcile_no_pay_way_alert(aid)
    card = alerts.present(dict(alerts.open_alert(_key(aid))), lang)
    shown = card["display_title"] + " " + card["display_detail"]
    assert "Loft 1071" in card["display_title"]
    assert "%(" not in shown and "notification." not in shown
    assert "paid" not in shown.lower()
    assert card["action_href"] == f"/apartments/{aid}?view=settings&section=reporting#stay-fee-settings"
    assert card["action_label_key"] == "notification.action.stay_fee_pay"
