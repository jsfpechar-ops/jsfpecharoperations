"""Security regression tests."""
from __future__ import annotations

import base64
import re
from datetime import timedelta

from fastapi.testclient import TestClient
from fastapi.responses import Response

from app import auth, claim, client_ip, config, db, host_i18n, rate_limit, security
from app.main import app
from app.routes import admin as admin_routes
from tests.conftest import complete_guest_claim
from tests.test_accounts import _account, _clean_accounts, _login


def test_security_headers_on_healthz():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    policy = response.headers.get("Content-Security-Policy", "")
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy


def test_production_healthz_omits_environment_details(monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert "deployment" not in response.json()
    assert "ubyport_env" not in response.json()


def _csrf_from(response) -> str:
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.text)
    assert match
    return match.group(1)


def test_production_host_posts_require_cookie_bound_csrf_token(monkeypatch):
    db.init_db()
    _clean_accounts()
    _account("boundary-csrf")
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    try:
        client = TestClient(app)
        login_token = _csrf_from(client.get("/login"))
        denied = client.post(
            "/login",
            data={"username": "boundary-csrf", "password": "Secure-Password-123"},
            follow_redirects=False,
        )
        assert denied.status_code == 303
        assert denied.headers["location"].startswith("/login?err=")

        logged_in = client.post(
            "/login",
            data={
                "username": "boundary-csrf",
                "password": "Secure-Password-123",
                security.CSRF_FIELD: login_token,
            },
            follow_redirects=False,
        )
        assert logged_in.status_code == 303

        host_token = _csrf_from(client.get("/settings"))
        expired = client.post(
            "/settings/purge-expired",
            headers={"Referer": "http://testserver/settings"},
            follow_redirects=False,
        )
        assert expired.status_code == 303
        assert expired.headers["location"].startswith("/settings?err=")
        accepted = client.post(
            "/settings/purge-expired",
            data={security.CSRF_FIELD: host_token},
            follow_redirects=False,
        )
        assert accepted.status_code == 303
        cross_site = client.post(
            "/settings/purge-expired",
            data={security.CSRF_FIELD: "not-a-valid-token"},
            headers={"Origin": "https://other.example"},
            follow_redirects=False,
        )
        assert cross_site.status_code == 403
        assert cross_site.json()["detail"] in {
            "Cross-site request rejected.",
            "Invalid or expired form token.",
        }
    finally:
        _clean_accounts()


def test_login_token_survives_session_cookie_appearing_after_cross_site_navigation(monkeypatch):
    """Safari can omit Strict session cookies on the initial externally-opened GET."""
    db.init_db()
    _clean_accounts()
    account_id = _account("strict-cookie-login")
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    try:
        client = TestClient(app, base_url="https://ubyhost.com")
        login_token = _csrf_from(client.get("/login"))
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (account_id,))
        client.cookies.set(
            auth.SESSION_COOKIE,
            auth.issue_session(account_id, account["session_version"]),
            domain="ubyhost.com",
            path="/",
        )
        response = client.post(
            "/login",
            data={
                "username": "strict-cookie-login",
                "password": "Secure-Password-123",
                security.CSRF_FIELD: login_token,
            },
            headers={"Origin": "https://ubyhost.com"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"
    finally:
        _clean_accounts()


def test_csrf_token_remains_valid_when_authenticated_session_is_reissued(monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    client = TestClient(app, base_url="https://ubyhost.com")
    token = _csrf_from(client.get("/login"))
    client.cookies.set(auth.SESSION_COOKIE, "a-new-session", domain="ubyhost.com", path="/")
    response = client.post(
        "/language",
        data={"lang": "en", security.CSRF_FIELD: token},
        headers={"Origin": "https://ubyhost.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_production_login_accepts_https_origin_behind_http_proxy(monkeypatch):
    db.init_db()
    _clean_accounts()
    _account("proxy-login")
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://ubyhost.com")
    try:
        client = TestClient(app, base_url="http://ubyhost.com")
        login_token = _csrf_from(client.get("/login"))
        response = client.post(
            "/login",
            data={
                "username": "proxy-login",
                "password": "Secure-Password-123",
                security.CSRF_FIELD: login_token,
            },
            headers={"Origin": "https://ubyhost.com"},
            follow_redirects=False,
        )
        assert response.status_code == 303
    finally:
        _clean_accounts()


def test_production_login_accepts_same_site_mobile_headers(monkeypatch):
    db.init_db()
    _clean_accounts()
    _account("mobile-login")
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    try:
        client = TestClient(app, base_url="https://ubyhost.com")
        login_token = _csrf_from(client.get("/login"))
        response = client.post(
            "/login",
            data={
                "username": "mobile-login",
                "password": "Secure-Password-123",
                security.CSRF_FIELD: login_token,
            },
            headers={
                "Origin": "https://www.ubyhost.com",
                "Sec-Fetch-Site": "same-site",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
    finally:
        _clean_accounts()


def test_safe_local_path_rejects_ambiguous_redirect_targets():
    for value in (
        "https://other.example/path",
        "//other.example/path",
        "/%2f%2fother.example/path",
        "/\\other.example/path",
        "/%5cother.example/path",
        "/safe\r\nLocation: https://other.example",
        "/a/../../other",
    ):
        result = security.safe_local_path(value, "/fallback")
        assert result.startswith("/")
        assert not result.startswith("//")
        assert "\\" not in result
        assert "\r" not in result and "\n" not in result


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


def test_login_rate_limit_also_caps_failures_across_usernames():
    ip_key = "203.0.113.90"
    try:
        for index in range(rate_limit._LOGIN_IP_MAX_FAILURES):
            rate_limit.record_login_failure(f"{ip_key}:candidate-{index}", ip_key)
        assert rate_limit.login_blocked(f"{ip_key}:new-candidate", ip_key)
    finally:
        db.execute(
            "DELETE FROM rate_limit_event WHERE scope = ? AND key = ?",
            ("login_fail_ip", ip_key),
        )


def test_production_cookies_are_secure_even_if_public_url_is_misconfigured(monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "http://app.example")

    attached = Response()
    auth.attach_session(attached, "session-token")
    assert "Secure" in attached.headers["set-cookie"]

    cleared = Response()
    auth.clear_session(cleared)
    header = cleared.headers["set-cookie"]
    assert "Secure" in header
    assert "HttpOnly" in header
    assert "SameSite=strict" in header


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
        client.cookies.set(host_i18n.LANG_COOKIE, "en")
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
        f"/l/{token}/%2e%2e/%2e%2e/%2f%2fevil.example",
        f"/l/{token}/%5cevil.example",
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
        for path in ("/", "/reservations", "/submissions", "/settings", "/apartments"):
            page = host.get(path)
            assert page.status_code == 200, path
            assert "Nothing is being reported to the police" in page.text, path

        # The badge must not render mock and test identically.
        overview = host.get("/")
        assert 'class="env-badge mock"' in overview.text

        # Login says it too. It is where a host who keeps a practice instance
        # alongside a real one finds out they opened the wrong one, which is
        # the cheapest moment to correct. It discloses nothing new: /healthz
        # already reports the environment without any authentication. The
        # signed-out page answers in Czech unless the visitor asks otherwise.
        signed_out = TestClient(app).get("/login").text
        assert host_i18n.translate("cs", "env.mock_title") in signed_out
        assert "Nothing is being reported" in TestClient(app).get("/login?lang=en").text
    finally:
        _clean_accounts()




# The guest cookies W3.6 covers, by the helper in app/routes/guest.py that sets
# each one: _remember_owned, _remember_claim and _with_lang.
GUEST_COOKIE_NAMES = ("ubyhost_owned", "ubyhost_claim", "ubyhost_lang")

_GUEST_TOKEN = "security-cookie-token"
# A one-pixel PNG data URL: the only shape validation.parse_signature_data_url
# accepts, so the save gets as far as handing out the owned cookie.
_GUEST_SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c63000100000500010d7a1f0000000049454e44ae42"
        "6082"
    )
).decode()


def _clean_guest_cookie_fixture():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (_GUEST_TOKEN,)
    )
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _guest_cookie_fixture() -> int:
    """One apartment and one stay, so all three guest cookies can be set."""
    db.init_db()
    _clean_guest_cookie_fixture()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Security cookies", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Cookie flat",
            "permalink_token": _GUEST_TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "security-cookie-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _guest_save_payload() -> dict:
    return {
        "surname": "Smith",
        "first_name": "John",
        "birth_date": "01/01/1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "party_size": "2",
        "signature": _GUEST_SIGNATURE,
        "legal_ack": "1",
    }


def _secure_flags(*responses) -> dict:
    """Cookie name -> the Secure attribute the server actually sent.

    Read from Set-Cookie rather than from the client's cookie jar. A browser
    (and httpx) refuses a Secure cookie that arrives over http, so the jar
    would report the flag by the cookie's absence, for a reason that has
    nothing to do with what the server marked it with.
    """
    flags = {}
    for response in responses:
        for header in response.headers.get_list("set-cookie"):
            name, _, rest = header.partition("=")
            flags[name.strip()] = "secure" in rest.lower()
    return flags


def _drive_guest_cookies(deployment: str) -> dict:
    """Set all three guest cookies and report what the server marked them with."""
    stay_id = _guest_cookie_fixture()
    # https so the client keeps the cookies and the flow runs to the end. The
    # scheme is not what the app looks at; config.PUBLIC_BASE_URL is, and the
    # test leaves that on its http default.
    browser = TestClient(app, base_url="https://ubyhost.com")
    previous = config.DEPLOYMENT
    config.DEPLOYMENT = deployment
    try:
        lang = browser.get(f"/l/{_GUEST_TOKEN}/{stay_id}?lang=cs", follow_redirects=False)
        assert lang.status_code == 200, lang.text
        captured: list = []
        assert complete_guest_claim(browser, _GUEST_TOKEN, stay_id, capture=captured)
        saved = browser.post(
            f"/l/{_GUEST_TOKEN}/{stay_id}/save",
            data=_guest_save_payload(),
            follow_redirects=False,
        )
        assert saved.status_code == 303, saved.text
    finally:
        config.DEPLOYMENT = previous
    return _secure_flags(lang, captured[0], saved)


def test_guest_cookies_are_secure_in_production_without_an_https_base_url():
    """W3.6 [F25]: production must not depend on the base URL to be https.

    All three guest cookies were marked Secure only when ``PUBLIC_BASE_URL``
    started with ``https://``. ``env_guard`` only *warns* when a production
    deployment is left on the http default, so a production instance that never
    set ``UBYHOST_PUBLIC_BASE_URL`` handed out guest session cookies a browser
    was free to send over plain http. The deployment name is the signal that
    says a real instance is behind TLS, and it is now consulted as well.
    """
    try:
        # The misconfiguration being guarded, asserted rather than assumed.
        assert config.PUBLIC_BASE_URL.lower().startswith("http://")

        flags = _drive_guest_cookies("production")
        for name in GUEST_COOKIE_NAMES:
            assert name in flags, f"{name} was never set: the test drove no cookie"
            assert flags[name] is True, f"{name} was sent without Secure"

        # Counterfactual, so the assertion cannot pass on a hard-coded flag:
        # outside production, an http base URL still omits it.
        local_flags = _drive_guest_cookies("local")
        for name in GUEST_COOKIE_NAMES:
            assert local_flags[name] is False, f"{name} is Secure outside production"
    finally:
        _clean_guest_cookie_fixture()
