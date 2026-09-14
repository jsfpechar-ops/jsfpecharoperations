"""Security regression tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import client_ip, config, db, rate_limit
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


def test_cf_connecting_ip_ignored_without_trusted_proxy(monkeypatch):
    monkeypatch.setattr(config, "CLOUDFLARE_PROXY", False)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "")
    client_ip.reset_trusted_proxy_cache()

    scope = {"client": ("203.0.113.50", 12345)}
    headers = {"cf-connecting-ip": "198.51.100.99"}
    client_ip.apply_visitor_client(scope, headers)
    assert scope["client"][0] == "203.0.113.50"


def test_cf_connecting_ip_honoured_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(config, "CLOUDFLARE_PROXY", False)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "172.18.0.0/16")
    client_ip.reset_trusted_proxy_cache()

    scope = {"client": ("172.18.0.2", 0)}
    headers = {"cf-connecting-ip": "198.51.100.77"}
    client_ip.apply_visitor_client(scope, headers)
    assert scope["client"][0] == "198.51.100.77"


def test_pin_rate_limit_not_bypassed_by_spoofed_cf_header(monkeypatch):
    monkeypatch.setattr(config, "CLOUDFLARE_PROXY", False)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", "")
    client_ip.reset_trusted_proxy_cache()

    db.init_db()
    token = "cf-pin-guard"
    pin = "654321"
    now = db.utcnow()
    apt = db.query_one("SELECT id FROM apartment WHERE permalink_token = ?", (token,))
    if apt:
        db.execute("DELETE FROM apartment WHERE id = ?", (apt["id"],))
    entity_id = db.insert("legal_entity", {"name": "CF guard", "created_at": now})
    db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "CF",
            "permalink_token": token,
            "permalink_pin": pin,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    try:
        client = TestClient(app)
        for _ in range(rate_limit._PIN_MAX_FAILURES):
            client.post(f"/l/{token}/pin", data={"pin": "000000"}, follow_redirects=False)
        blocked = client.post(f"/l/{token}/pin", data={"pin": "000000"}, follow_redirects=False)
        assert "Wait about 15" in blocked.text

        spoofed = client.post(
            f"/l/{token}/pin",
            data={"pin": "000000"},
            headers={"CF-Connecting-IP": "203.0.113.99"},
            follow_redirects=False,
        )
        assert "Wait about 15" in spoofed.text
    finally:
        db.execute("DELETE FROM apartment WHERE permalink_token = ?", (token,))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{token}",))


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


def test_guest_pages_are_never_cached_but_static_still_is():
    """Passport data must not survive in history on a handed-back phone."""
    client = TestClient(app)

    page = client.get("/login")
    assert "no-store" in page.headers.get("Cache-Control", "")

    unavailable = client.get("/l/does-not-exist", follow_redirects=False)
    assert "no-store" in unavailable.headers.get("Cache-Control", "")

    # Stylesheets and the signature pad still cache, or the guest pays for
    # them again on hotel wifi.
    asset = client.get("/static/guest.css")
    assert asset.status_code == 200
    assert "no-store" not in asset.headers.get("Cache-Control", "")


def test_pin_return_to_cannot_escape_the_apartment_permalink():
    from app.routes.guest import _safe_return_to

    token = "abc123"
    inside = f"/l/{token}/42/new?lang=en"
    assert _safe_return_to(inside, token, "en") == inside
    assert _safe_return_to(f"/l/{token}", token, "en") == f"/l/{token}"

    # A plain startswith() check lets all of these through.
    for escape in (
        f"/l/{token}/../../apartments",
        f"/l/{token}/../..//evil.example",
        "//evil.example",
        "https://evil.example",
        "/apartments",
        f"/l/{token}-other/1",
    ):
        landing = _safe_return_to(escape, token, "en")
        assert landing.startswith(f"/l/{token}"), (escape, landing)
        assert ".." not in landing


def test_mock_environment_is_declared_on_every_host_page(monkeypatch):
    """On mock, stays go green while nothing reaches the police. Say so."""
    db.init_db()
    _clean_accounts()
    _account("boundary-envcheck")
    try:
        host = _login("boundary-envcheck")

        # conftest runs the suite against the mock UbyPort server.
        assert config.UBYPORT_ENV == "mock"
        for path in ("/", "/reservations", "/submissions"):
            page = host.get(path)
            assert page.status_code == 200, path
            assert "Nothing is being reported to the police" in page.text, path

        # The badge must not render mock and test identically.
        overview = host.get("/")
        assert 'class="env-badge mock"' in overview.text
    finally:
        _clean_accounts()
