"""Security regression tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import config, db, rate_limit
from app.main import app
from app.routes import admin as admin_routes
from tests.test_accounts import _account, _clean_accounts, _login


def test_security_headers_on_healthz():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_redirect_path_from_referer_rejects_off_site():
    class FakeRequest:
        def __init__(self, referer: str):
            self.headers = {"referer": referer}

    class HostRequest:
        def __init__(self, referer: str, host: str = "app.example"):
            self.headers = {"referer": referer, "host": host}

    assert admin_routes._redirect_path_from_referer(HostRequest("https://evil.example/phish")) == "/"
    assert (
        admin_routes._redirect_path_from_referer(
            HostRequest("https://app.example/reservations?x=1")
        )
        == "/reservations?x=1"
    )


def test_login_rate_limit_not_bypassed_by_spoofed_cf_connecting_ip(monkeypatch):
    db.init_db()
    _clean_accounts()
    _account("boundary-cf-spoof")
    monkeypatch.setattr(config, "TRUST_CF_CONNECTING_IP", False)
    try:
        client = TestClient(app)
        for i in range(rate_limit._LOGIN_MAX_FAILURES):
            client.post(
                "/login",
                data={"username": "boundary-cf-spoof", "password": "wrong"},
                headers={"cf-connecting-ip": f"203.0.113.{i}"},
                follow_redirects=False,
            )
        blocked = client.post(
            "/login",
            data={"username": "boundary-cf-spoof", "password": "wrong"},
            headers={"cf-connecting-ip": "203.0.113.99"},
            follow_redirects=False,
        )
        assert blocked.status_code == 429
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", ("%boundary-cf-spoof%",))
        _clean_accounts()


def test_login_rate_limit_blocks_after_repeated_failures():
    db.init_db()
    _clean_accounts()
    _account("boundary-rate")
    key = "testclient:boundary-rate"
    try:
        for _ in range(rate_limit._LOGIN_MAX_FAILURES):
            rate_limit.record_login_failure(key)
        assert rate_limit.login_blocked(key)
        client = TestClient(app)
        response = client.post(
            "/login",
            data={"username": "boundary-rate", "password": "wrong"},
            follow_redirects=False,
        )
        assert response.status_code == 429
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key = ?", (key,))
        _clean_accounts()


def test_alert_dismiss_does_not_redirect_to_external_site():
    db.init_db()
    _clean_accounts()
    owner_id = _account("boundary-alert")
    alert_id = db.insert(
        "alert",
        {
            "owner_user_id": owner_id,
            "level": "info",
            "kind": "security_test",
            "message": "Test",
            "dedupe_key": "security-test",
            "created_at": db.utcnow(),
        },
    )
    try:
        client = _login("boundary-alert")
        response = client.post(
            f"/alerts/{alert_id}/dismiss",
            headers={"referer": "https://evil.example/steal"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"
    finally:
        db.execute("DELETE FROM alert WHERE id = ?", (alert_id,))
        _clean_accounts()
