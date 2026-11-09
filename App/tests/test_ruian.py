"""0884 D: RÚIAN address suggest endpoint. No real network: requests.get is mocked.

Response shapes match the live ČÚZK service (checked 2026-11-09): geocoder candidates
carry only label, score and an S-JTSK point; structure comes from RÚIAN layer queries.
"""
from __future__ import annotations

import pytest
import requests
from fastapi.testclient import TestClient

from app import ruian
from app.main import app
from tests.test_onboarding_wizard_survival import host  # noqa: F401

ROUTE = "/apartments/ruian-suggest"
ADDRESS = "Václavské náměstí 1306/55, Nové Město, 11000 Praha 1"

CANDIDATE = {
    "address": ADDRESS,
    "location": {"x": -742321.89, "y": -1043891.77, "spatialReference": {"wkid": 102067}},
    "score": 100,
    "attributes": {"Type": "AdresniMisto", "Match_addr": ADDRESS, "Score": 100},
}
FEATURE = {
    "kod": 1,
    "cislodomovni": 1306,
    "cisloorientacni": 55,
    "cisloorientacnipismeno": None,
    "psc": 11000,
    "ulice": 123,
    "adresa": ADDRESS,
}
LAYERS = {
    1: {"features": [{"attributes": FEATURE}]},
    4: {"features": [{"attributes": {"nazev": "Václavské náměstí"}}]},
    12: {"features": [{"attributes": {"nazev": "Praha", "okres": 3100}}]},
    15: {"features": []},
}


class _Response:
    def __init__(self, payload=None, ok=True):
        self._payload = payload if payload is not None else {}
        self.ok = ok

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    ruian._CACHE.clear()
    monkeypatch.delenv("UBYHOST_RUIAN_ENABLED", raising=False)
    yield
    ruian._CACHE.clear()


@pytest.fixture
def cuzk(monkeypatch):
    """Routes requests.get by URL: geocoder candidates, then per-layer payloads."""
    state = {"candidates": [CANDIDATE], "layers": dict(LAYERS), "calls": []}

    def fake_get(url, **kwargs):
        state["calls"].append((url, kwargs))
        if url == ruian._find_url():
            return _Response({"candidates": state["candidates"]})
        layer = int(url[len(ruian._LAYER_BASE) + 1:].split("/")[0])
        return _Response(state["layers"].get(layer, {"features": []}))

    monkeypatch.setattr(ruian.requests, "get", fake_get)
    return state


@pytest.fixture
def calls(cuzk):
    return cuzk["calls"]


def _geocoder_calls(calls):
    return [call for call in calls if call[0] == ruian._find_url()]


def test_happy_path_returns_structured_fields(host, calls):  # noqa: F811
    response = host["client"].get(ROUTE, params={"q": "Václavské náměstí 1306/55"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["label"] == ADDRESS
    fields = body[0]["fields"]
    assert fields["addr_street"] == "Václavské náměstí"
    assert fields["addr_house_no"] == "1306"
    assert fields["addr_orient_no"] == "55"
    assert fields["addr_zip"] == "11000"
    assert fields["addr_obec"] == "Praha"
    assert fields["addr_okres"] == "Hlavní město Praha"
    assert fields["addr_obec_cast"] == "Nové Město"
    url, kwargs = calls[0]
    assert url == ruian._find_url()
    assert kwargs["params"]["SingleLine"] == "Václavské náměstí 1306/55"
    assert kwargs["timeout"] == 4


def test_layer_queries_use_layer_base(cuzk):
    ruian.suggest("Václavské náměstí 1306/55")
    layer_urls = [url for url, _ in cuzk["calls"] if url != ruian._find_url()]
    assert layer_urls
    assert all(url.startswith(ruian._LAYER_BASE + "/") for url in layer_urls)


def test_orientation_letter_is_appended(cuzk):
    cuzk["layers"][1] = {"features": [{"attributes": dict(FEATURE, cisloorientacnipismeno="a")}]}
    result = ruian.suggest("Václavské náměstí 1306/55")
    assert result[0]["fields"]["addr_orient_no"] == "55a"


def test_candidate_without_matching_adresa_is_dropped(cuzk):
    cuzk["layers"][1] = {"features": [{"attributes": dict(FEATURE, adresa="Jiná 1, Praha")}]}
    assert ruian.suggest("Václavské náměstí 1306/55") == []


def test_low_score_or_other_type_is_dropped(cuzk):
    cuzk["candidates"] = [dict(CANDIDATE, score=40)]
    assert ruian.suggest("Václavské náměstí 1306") == []
    cuzk["candidates"] = [dict(CANDIDATE, attributes={"Type": "Ulice"})]
    assert ruian.suggest("Václavské náměstí 1306") == []


def test_network_error_returns_empty_and_is_not_cached(cuzk, monkeypatch):
    def boom(url, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(ruian.requests, "get", boom)
    assert ruian.suggest("Václavské náměstí 1306/55") == []
    assert ruian._CACHE == {}
    monkeypatch.setattr(ruian.requests, "get", cuzk_get(cuzk))
    assert len(ruian.suggest("Václavské náměstí 1306/55")) == 1


def cuzk_get(state):
    def fake_get(url, **kwargs):
        if url == ruian._find_url():
            return _Response({"candidates": state["candidates"]})
        layer = int(url[len(ruian._LAYER_BASE) + 1:].split("/")[0])
        return _Response(state["layers"].get(layer, {"features": []}))

    return fake_get


def test_non_ok_response_returns_empty_list(monkeypatch):
    monkeypatch.setattr(ruian.requests, "get", lambda url, **kwargs: _Response({}, ok=False))
    assert ruian.suggest("Václavské náměstí 1306/55") == []


def test_village_address_without_street(cuzk):
    label = "12, Horní Lhota, 76001 Horní Lhota"
    cuzk["candidates"] = [dict(CANDIDATE, address=label)]
    cuzk["layers"][1] = {
        "features": [
            {"attributes": dict(FEATURE, cislodomovni=12, cisloorientacni=None, psc=76001, ulice=None, adresa=label)}
        ]
    }
    cuzk["layers"][12] = {"features": [{"attributes": {"nazev": "Horní Lhota", "okres": 3300}}]}
    cuzk["layers"][15] = {"features": [{"attributes": {"nazev": "Vsetín"}}]}
    result = ruian.suggest("Horní Lhota 12")
    assert len(result) == 1
    fields = result[0]["fields"]
    assert "addr_street" not in fields
    assert "addr_obec_cast" not in fields
    assert fields["addr_house_no"] == "12"
    assert fields["addr_okres"] == "Vsetín"


def test_timeout_returns_empty_list(host, monkeypatch):  # noqa: F811
    def boom(url, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(ruian.requests, "get", boom)
    response = host["client"].get(ROUTE, params={"q": "Praha 1 Vaclavske"})
    assert response.status_code == 200
    assert response.json() == []


def test_empty_result_returns_empty_list(host, cuzk):  # noqa: F811
    cuzk["candidates"] = []
    assert host["client"].get(ROUTE, params={"q": "Nikde 999"}).json() == []


def test_query_reaches_geocoder_unchanged(calls):
    ruian.suggest("Vaclavske namesti 1")
    geocoder = _geocoder_calls(calls)
    assert geocoder[0][1]["params"]["SingleLine"] == "Vaclavske namesti 1"


def test_short_query_makes_no_request(host, calls):  # noqa: F811
    assert host["client"].get(ROUTE, params={"q": "ab"}).json() == []
    assert calls == []


def test_rate_limit_blocks_without_request(host, calls, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ruian, "rate_limited", lambda owner: True)
    assert host["client"].get(ROUTE, params={"q": "Václavské náměstí"}).json() == []
    assert calls == []


def test_repeat_query_uses_cache(host, calls):  # noqa: F811
    client = host["client"]
    first = client.get(ROUTE, params={"q": "Václavské náměstí 1306/55"}).json()
    count_after_first = len(calls)
    second = client.get(ROUTE, params={"q": "  VÁCLAVSKÉ   NÁMĚSTÍ 1306/55 "}).json()
    assert first == second
    assert len(calls) == count_after_first


def test_disabled_by_env_makes_no_request(host, calls, monkeypatch):  # noqa: F811
    monkeypatch.setenv("UBYHOST_RUIAN_ENABLED", "0")
    assert host["client"].get(ROUTE, params={"q": "Václavské náměstí"}).json() == []
    assert calls == []


def test_anonymous_request_is_refused(calls):
    response = TestClient(app).get(ROUTE, params={"q": "Václavské náměstí"})
    assert response.status_code == 401
    assert response.json() == []
    assert calls == []
