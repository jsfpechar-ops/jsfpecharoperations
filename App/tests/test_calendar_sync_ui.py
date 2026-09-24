"""Regression tests for the calendar sync CTA and POST /sync redirects."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import alerts, auth, db
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


def test_sync_reports_a_failed_feed_in_the_redirect_and_alerts(monkeypatch):
    client = _host()
    owner_id = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Failed feed property",
            "automation_mode": "manual",
            "active": 1,
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/failed.ics",
            "active": 1,
            "created_at": now,
        },
    )
    monkeypatch.setattr(
        "app.routes.admin.icalsync.fetch_feed",
        lambda _url: (_ for _ in ()).throw(RuntimeError("feed offline")),
    )

    response = client.post("/sync", follow_redirects=False)

    assert response.status_code == 303
    assert "Some%20calendars%20could%20not%20be%20read" in response.headers["location"]
    feed_alerts = [
        alert
        for alert in alerts.open_alerts(owner_id)
        if alert["kind"] == "feed_error"
    ]
    assert len(feed_alerts) == 1
    assert feed_alerts[0]["apartment_id"] == apartment_id
    db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))


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
