"""0834 D: RÚIAN address suggest endpoint. No real network: requests.get is mocked."""
from __future__ import annotations

import pytest
import requests
from fastapi.testclient import TestClient

from app import ruian
from app.main import app
from tests.test_onboarding_wizard_survival import host  # noqa: F401

ROUTE = "/apartments/ruian-suggest"

CANDIDATE = {
    "address": "Václavské náměstí 1/2, Praha 1, 11000",
    "attributes": {
        "StreetName": "Václavské náměstí",
        "BuildingNumber": "1",
        "OrientationNumber": "2",
        "PostalCode": "11000",
        "Municipality": "Praha",
        "MunicipalityPart": "Praha 1",
        "District": "Hlavní město Praha",
    },
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
def calls(monkeypatch):
    recorded = []

    def fake_get(url, **kwargs):
        recorded.append((url, kwargs))
        return _Response({"candidates": [CANDIDATE]})

    monkeypatch.setattr(ruian.requests, "get", fake_get)
    return recorded


def test_happy_path_returns_structured_fields(host, calls):  # noqa: F811
    response = host["client"].get(ROUTE, params={"q": "Václavské náměstí 1"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["label"] == CANDIDATE["address"]
    fields = body[0]["fields"]
    assert fields["street"] == "Václavské náměstí"
    assert fields["house_no"] == "1"
    assert fields["orientation_no"] == "2"
    assert fields["zip"] == "11000"
    assert fields["town"] == "Praha"
    assert fields["district_part"] == "Praha 1"
    assert fields["okres"] == "Hlavní město Praha"
    url, kwargs = calls[0]
    assert url == ruian._FIND_URL
    assert kwargs["params"]["SingleLine"] == "Václavské náměstí 1"
    assert kwargs["timeout"] == 4


def test_label_is_not_parsed_into_fields(host, monkeypatch):  # noqa: F811
    # A candidate without structured attributes gives a label only: nothing is split out of it.
    monkeypatch.setattr(
        ruian.requests,
        "get",
        lambda url, **kwargs: _Response({"candidates": [{"address": "Ulice 12/3, Brno", "attributes": {}}]}),
    )
    assert ruian.suggest("Ulice 12") == []
    assert host["client"].get(ROUTE, params={"q": "Ulice 12"}).json() == []


def test_empty_result_returns_empty_list(host, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ruian.requests, "get", lambda url, **kwargs: _Response({"candidates": []}))
    assert host["client"].get(ROUTE, params={"q": "Nikde 999"}).json() == []


def test_timeout_returns_empty_list(host, monkeypatch):  # noqa: F811
    def boom(url, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(ruian.requests, "get", boom)
    response = host["client"].get(ROUTE, params={"q": "Praha 1 Vaclavske"})
    assert response.status_code == 200
    assert response.json() == []


def test_short_query_makes_no_request(host, calls):  # noqa: F811
    assert host["client"].get(ROUTE, params={"q": "ab"}).json() == []
    assert calls == []


def test_rate_limit_blocks_without_request(host, calls, monkeypatch):  # noqa: F811
    monkeypatch.setattr(ruian, "rate_limited", lambda owner: True)
    assert host["client"].get(ROUTE, params={"q": "Václavské náměstí"}).json() == []
    assert calls == []


def test_repeat_query_uses_cache(host, calls):  # noqa: F811
    client = host["client"]
    first = client.get(ROUTE, params={"q": "Václavské náměstí"}).json()
    second = client.get(ROUTE, params={"q": "  VÁCLAVSKÉ   NÁMĚSTÍ "}).json()
    assert first == second
    assert len(calls) == 1


def test_disabled_by_env_makes_no_request(host, calls, monkeypatch):  # noqa: F811
    monkeypatch.setenv("UBYHOST_RUIAN_ENABLED", "0")
    assert host["client"].get(ROUTE, params={"q": "Václavské náměstí"}).json() == []
    assert calls == []


def test_anonymous_request_is_refused(calls):
    response = TestClient(app).get(ROUTE, params={"q": "Václavské náměstí"})
    assert response.status_code == 401
    assert response.json() == []
    assert calls == []
