"""Regression tests for the calendar sync CTA and POST /sync redirects."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Sync-Return-Password-123"
USERNAME = "sync-return-host"


def _host() -> TestClient:
    db.init_db()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(
            USERNAME,
            PASSWORD,
            "Sync redirect host",
            role="host",
            must_change_password=False,
        )
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _stub_sync(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.admin.icalsync.sync_all",
        lambda owner_user_id=None: {
            "feeds": 0,
            "created": 0,
            "updated": 0,
            "cancelled": 0,
            "errors": 0,
        },
    )
    monkeypatch.setattr(
        "app.routes.admin.reporting.check_deadlines",
        lambda owner_user_id=None: None,
    )


def test_sync_returns_to_the_properties_list_when_triggered_there(monkeypatch):
    _stub_sync(monkeypatch)
    client = _host()

    response = client.post(
        "/sync",
        data={"return_to": "/apartments"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/apartments?")


def test_sync_defaults_to_the_dashboard_when_return_to_is_missing(monkeypatch):
    _stub_sync(monkeypatch)
    client = _host()

    response = client.post("/sync", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?")


def test_sync_rejects_an_off_site_return_to(monkeypatch):
    _stub_sync(monkeypatch)
    client = _host()

    response = client.post(
        "/sync",
        data={"return_to": "https://evil.example/phish"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/?")


def test_sync_forms_embed_their_return_to_on_dashboard_and_properties():
    client = _host()

    dashboard = client.get("/")
    apartments = client.get("/apartments")

    assert dashboard.status_code == 200
    assert apartments.status_code == 200
    assert 'action="/sync"' in dashboard.text
    assert 'name="return_to" value="/"' in dashboard.text
    assert 'action="/sync"' in apartments.text
    assert 'name="return_to" value="/apartments"' in apartments.text
