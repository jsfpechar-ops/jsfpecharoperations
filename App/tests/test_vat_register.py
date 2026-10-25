"""MFČR VAT register lookup in the invoice details (task 0394). No real network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from app import ares, auth, db, payments, vat_register
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import drop_stays

USERNAME = "vat-register-host"
ICO = "04656679"
DIC = "CZ1111111111"

ARES_PAYLOAD = {
    "obchodniJmeno": "VAT Test s.r.o.",
    "sidlo": {
        "textovaAdresa": "Praha 1, Václavské náměstí 1",
        "nazevUlice": "Václavské náměstí",
        "cisloDomovni": 1,
        "cisloOrientacni": 2,
        "nazevObce": "Praha",
        "psc": 11000,
    },
    "dic": DIC,
    "seznamRegistraci": {"stavZdrojeDph": "AKTIVNI"},
    "dalsiUdaje": [{"datovyZdroj": "vr", "spisovaZnacka": "B 8525/MSPH"}],
}
ARES_NO_DIC = {key: value for key, value in ARES_PAYLOAD.items() if key != "dic"}

VAT_XML = (
    '<?xml version="1.0" encoding="utf-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
    '<soapenv:Header/><soapenv:Body><StatusNespolehlivySubjektRozsirenyResponse xmlns="http://adis.mfcr.cz/rozhraniCRPDPH/">'
    '<status odpovedGenerovana="2026-10-25" statusCode="0" statusText="OK"/>'
    '<statusSubjektu typSubjektu="PLATCE_DPH" dic="1111111111" nespolehlivyPlatce="NE" cisloFu="451">'
    '<zverejneneUcty>'
    '<ucet datumZverejneni="2024-04-19"><standardniUcet cislo="123456789" kodBanky="0300"/></ucet>'
    '<ucet datumZverejneni="2024-05-01"><standardniUcet predcisli="19" cislo="2000145399" kodBanky="0800"/></ucet>'
    '<ucet datumZverejneni="2020-01-01" datumZverejneniUkonceni="2021-01-01"><standardniUcet cislo="999" kodBanky="0100"/></ucet>'
    '</zverejneneUcty><nazevSubjektu>Test Host</nazevSubjektu></statusSubjektu>'
    '</StatusNespolehlivySubjektRozsirenyResponse></soapenv:Body></soapenv:Envelope>'
).encode("utf-8")


def _vat_answer(content=VAT_XML):
    return MagicMock(ok=True, status_code=200, content=content)


def _ares_answer(payload=ARES_PAYLOAD):
    response = MagicMock()
    response.status_code = 200
    response.ok = True
    response.json.return_value = payload
    return response


def _owner() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'ares' AND key = ?", (str(user_id),))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    db.execute("DELETE FROM invoice_item WHERE invoice_id IN "
               "(SELECT id FROM invoice WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user_id,))
    drop_stays(user_id)
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN "
               "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    ares._CACHE.clear()
    vat_register._CACHE.clear()


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "VAT Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture(autouse=True)
def clear_caches():
    ares._CACHE.clear()
    vat_register._CACHE.clear()
    yield
    ares._CACHE.clear()
    vat_register._CACHE.clear()


@pytest.fixture
def networks():
    """(ARES get, MFČR post) mocks; both answer with fake data by default."""
    with patch("app.ares.requests.get") as get, patch("app.vat_register.requests.post") as post:
        get.return_value = _ares_answer()
        post.return_value = _vat_answer()
        yield get, post


def _entity(**over) -> int:
    values = {
        "name": "VAT Host s.r.o.", "seat": "Praha", "ico": ICO,
        "owner_user_id": _owner(), "created_at": db.utcnow(), "vat_status": "non_payer",
    }
    values.update(over)
    return db.insert("legal_entity", values)


def _form(entity_id: int, **fields) -> dict:
    data = {
        "legal_entity_id": str(entity_id), "ico": ICO, "vat_status": "non_payer",
        "registry_entry": "", "invoice_due_days": "14",
    }
    data.update(fields)
    return data


def test_dic_digits_keeps_only_the_czech_digits():
    assert vat_register.dic_digits("CZ 12345678") == "12345678"
    assert vat_register.dic_digits("CZ1111111111") == "1111111111"
    assert vat_register.dic_digits("SK123") == ""


def test_lookup_reads_the_published_accounts_and_status(networks):
    _, post = networks
    assert vat_register.lookup(DIC) == {
        "vat_status": "payer",
        "unreliable": False,
        "accounts": ["123456789/0300", "19-2000145399/0800"],
    }
    body = post.call_args.kwargs["data"]
    assert b"<dic>1111111111</dic>" in body
    assert b"CZ" not in body


def test_a_bad_status_is_not_cached(networks):
    _, post = networks
    post.return_value = _vat_answer(VAT_XML.replace(b'statusCode="0"', b'statusCode="1"'))
    assert vat_register.lookup(DIC) is None
    assert vat_register.lookup(DIC) is None
    assert post.call_count == 2


def test_sole_trader_gets_the_account_from_the_saved_dic(host, networks):
    get, post = networks
    get.return_value = _ares_answer(ARES_NO_DIC)
    entity_id = _entity(dic=DIC, bank_account=None, iban=None)
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1"),
    )
    assert response.status_code == 200
    assert post.call_count == 1
    assert 'value="123456789"' in response.text
    assert 'value="0300"' in response.text
    assert 'value="19-2000145399/0800"' in response.text
    assert "and the VAT register" in response.text
    bic = payments.bic_for_account("123456789/0300")
    assert bic
    assert f'value="{bic}"' in response.text
    row = db.query_one("SELECT bank_account FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] is None


def test_a_typed_account_is_never_replaced(host, networks):
    entity_id = _entity()
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1", account_number="555", account_bank="0100"),
    )
    assert response.status_code == 200
    assert 'value="555"' in response.text
    assert 'value="123456789"' not in response.text
    assert 'value="123456789/0300"' in response.text


def test_picking_a_published_account_fills_the_fields(host, networks):
    entity_id = _entity()
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, use_register_account="19-2000145399/0800"),
    )
    assert response.status_code == 200
    assert 'value="19"' in response.text
    assert 'value="2000145399"' in response.text
    assert 'value="0800"' in response.text

    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, use_register_account="1/0100", account_number="555", account_bank="0100"),
    )
    assert response.status_code == 200
    assert 'value="555"' in response.text
    assert 'value="2000145399"' not in response.text


def test_vat_status_comes_from_the_register_only_from_the_default(host, networks):
    entity_id = _entity()
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1"),
    )
    assert '<option value="payer" selected>' in response.text

    _, post = networks
    post.return_value = _vat_answer(VAT_XML.replace(b"PLATCE_DPH", b"IDENTIFIKOVANA_OSOBA"))
    vat_register._CACHE.clear()
    entity_id = _entity(name="Identified s.r.o.")
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1"),
    )
    assert '<option value="identified" selected>' in response.text

    vat_register._CACHE.clear()
    entity_id = _entity(name="Payer s.r.o.", vat_status="payer")
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1", vat_status="payer"),
    )
    assert '<option value="payer" selected>' in response.text


def test_no_dic_anywhere_makes_no_vat_request(host, networks):
    get, post = networks
    get.return_value = _ares_answer(ARES_NO_DIC)
    entity_id = _entity()
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1"),
    )
    assert response.status_code == 200
    post.assert_not_called()
    assert "add your DIČ in" in response.text


def test_an_unreliable_payer_shows_one_alert(host, networks):
    _, post = networks
    post.return_value = _vat_answer(VAT_XML.replace(b'nespolehlivyPlatce="NE"', b'nespolehlivyPlatce="ANO"'))
    entity_id = _entity()
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1"),
    )
    assert response.status_code == 200
    assert response.text.count("unreliable VAT payer") == 1


def test_a_failing_mfcr_is_silent_and_ares_still_shows(host, networks):
    _, post = networks
    post.side_effect = requests.Timeout()
    entity_id = _entity()
    response = host.post(
        f"/entities/{entity_id}/invoice?lang=en",
        data=_form(entity_id, fill_from_register="1"),
    )
    assert response.status_code == 200
    assert "Filled from the public business register (ARES)" in response.text
    assert 'value="123456789"' not in response.text
    row = db.query_one("SELECT bank_account FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] is None
