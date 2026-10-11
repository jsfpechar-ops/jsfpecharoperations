"""ARES business-register lookup (task 0055). No real network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from app import ares, auth, db, host_i18n, rate_limit
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import drop_stays, make_stay, stay_form

USERNAME = "ares-lookup-host"
ICO = "04656679"

SAMPLE_PAYLOAD = {
    "obchodniJmeno": "ARES Test s.r.o.",
    "sidlo": {
        "textovaAdresa": "Praha 1, Václavské náměstí 1",
        "nazevUlice": "Václavské náměstí",
        "cisloDomovni": 1,
        "cisloOrientacni": 2,
        "nazevObce": "Praha",
        "psc": 11000,
    },
    "dic": "CZ04656679",
    "seznamRegistraci": {"stavZdrojeDph": "AKTIVNI"},
    "dalsiUdaje": [{"datovyZdroj": "vr", "spisovaZnacka": "B 8525/MSPH"}],
}


def _mock_response(status_code=200, payload=SAMPLE_PAYLOAD):
    response = MagicMock()
    response.status_code = status_code
    response.ok = status_code == 200
    response.json.return_value = payload
    return response


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'ares' AND key = ?", (str(user_id),))
    drop_stays(user_id)
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM login_token WHERE user_account_id = ?", (user_id,))
    db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    ares._CACHE.clear()


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "ARES Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture(autouse=True)
def clear_ares_cache():
    ares._CACHE.clear()
    yield
    ares._CACHE.clear()


def test_format_registry_mark_maps_known_court():
    text = ares.format_registry_mark("B 8525/MSPH")
    assert "B 8525" in text
    assert "Městského soudu v Praze" in text


def test_format_registry_mark_keeps_unknown_court():
    assert ares.format_registry_mark("X 1/ZZZZ") == "X 1/ZZZZ"


@patch("app.ares.requests.get")
def test_lookup_maps_fields(mock_get):
    mock_get.return_value = _mock_response()
    data = ares.lookup(ICO)
    assert data is not None
    assert data["name"] == "ARES Test s.r.o."
    assert data["vat_payer"] is True
    assert "Městského soudu v Praze" in data["registry_entry"]
    mock_get.assert_called_once()


@patch("app.ares.requests.get")
def test_lookup_invalid_checksum_makes_no_request(mock_get):
    assert ares.lookup("12345678") is None
    mock_get.assert_not_called()


@patch("app.ares.requests.get")
def test_lookup_timeout_returns_none(mock_get):
    mock_get.side_effect = requests.Timeout()
    assert ares.lookup(ICO) is None


@patch("app.ares.requests.get")
def test_lookup_timeout_not_cached_then_succeeds(mock_get):
    mock_get.side_effect = [requests.Timeout(), _mock_response()]
    assert ares.lookup(ICO) is None
    data = ares.lookup(ICO)
    assert data is not None
    assert data["name"] == "ARES Test s.r.o."
    assert mock_get.call_count == 2


@patch("app.ares.requests.get")
def test_lookup_404_is_cached(mock_get):
    mock_get.return_value = _mock_response(status_code=404)
    assert ares.lookup(ICO) is None
    assert ares.lookup(ICO) is None
    mock_get.assert_called_once()


def test_entities_fill_does_not_save(host):
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response()
        response = host.post(
            "/entities?lang=en",
            data={
                "ico": ICO,
                "fill_from_register": "1",
                "name": "",
                "seat": "",
                "dic": "",
                "contact_email": "",
            },
        )
    assert response.status_code == 200
    assert "ARES Test s.r.o." in response.text
    assert "Filled from the public business register (ARES)" in response.text
    assert db.query_one("SELECT 1 AS x FROM legal_entity WHERE ico = ?", (ICO,)) is None


def test_entities_fill_keeps_typed_name(host):
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response()
        response = host.post(
            "/entities?lang=en",
            data={
                "ico": ICO,
                "fill_from_register": "1",
                "name": "My kept name",
                "seat": "",
                "dic": "",
                "contact_email": "a@example.test",
            },
        )
    assert response.status_code == 200
    assert "My kept name" in response.text
    assert "ARES Test s.r.o." not in response.text


def test_entities_failure_message(host):
    ares._CACHE.clear()
    with patch("app.ares.lookup", return_value=None):
        response = host.post(
            "/entities?lang=en",
            data={"ico": ICO, "fill_from_register": "1", "name": "X", "seat": "Y", "contact_email": ""},
        )
    assert "Please type the details" in response.text


def test_rate_limit_blocks_after_twenty(host):
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response()
        owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
        key = str(owner["id"])
        for _ in range(20):
            rate_limit.record("ares", key)
        response = host.post(
            "/entities?lang=en",
            data={"ico": ICO, "fill_from_register": "1", "name": "", "seat": "", "contact_email": ""},
        )
        mock_get.assert_not_called()
    assert "Too many lookups" in response.text


def test_i18n_keys_exist():
    for key in (
        "ares.fill",
        "ares.source_note",
        "ares.failure",
        "ares.rate_limited",
        "ares.vat_found",
        "ares.field.name",
    ):
        assert host_i18n.translate("en", key)
        assert host_i18n.translate("cs", key)


def test_invoice_settings_fill_registry(host):
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response()
        owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
        entity_id = db.insert(
            "legal_entity",
            {
                "name": "Seller s.r.o.",
                "seat": "Praha",
                "ico": ICO,
                "owner_user_id": owner["id"],
                "created_at": db.utcnow(),
                "vat_status": "non_payer",
            },
        )
        response = host.post(
            f"/invoices/settings?lang=en&entity={entity_id}",
            data={
                "legal_entity_id": str(entity_id),
                "ico": ICO,
                "fill_from_register": "1",
                "vat_status": "non_payer",
                "registry_entry": "",
                "invoice_due_days": "14",
            },
        )
    assert response.status_code == 200
    assert "Městského soudu v Praze" in response.text
    assert "We found: VAT registered" in response.text
    row = db.query_one("SELECT registry_entry, vat_status FROM legal_entity WHERE id = ?", (entity_id,))
    assert not row["registry_entry"]
    assert row["vat_status"] == "non_payer"


def test_invoice_buyer_fill(host):
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _mock_response()
        owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
        entity_id = db.insert(
            "legal_entity",
            {
                "name": "Seller s.r.o.",
                "seat": "Praha",
                "ico": "12345679",
                "owner_user_id": owner["id"],
                "created_at": db.utcnow(),
            },
        )
        stay_id = make_stay(owner["id"], entity_id=entity_id)
        response = host.post(
            "/invoices?lang=en",
            data={
                **stay_form(stay_id),
                "legal_entity_id": str(entity_id),
                "buyer_ico": ICO,
                "fill_buyer_from_register": "1",
                "buyer_name": "",
                "buyer_street": "",
                "buyer_city": "",
                "buyer_zip": "",
                "buyer_country": "CZE",
                "lang": "cs",
                "stay_price": "10000",
            },
        )
    assert response.status_code == 200
    assert "ARES Test s.r.o." in response.text
    assert db.query_one("SELECT 1 AS x FROM invoice WHERE owner_user_id = ?", (owner["id"],)) is None
