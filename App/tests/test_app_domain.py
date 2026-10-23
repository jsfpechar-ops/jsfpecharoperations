"""Domain migration: redirects, host links and unchanged guest/PWA behavior."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient

from app import claim, config, db, filing_watchdog, mail, mail_notify, security, site_urls
from app.main import app

PUBLIC = "https://ubyhost.test"
PORTAL = "https://app.ubyhost.test"


@pytest.fixture
def split_site(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", PUBLIC)
    monkeypatch.setattr(config, "APP_BASE_URL", PORTAL)


@pytest.mark.parametrize("path", ["/login", "/login/", "/login/link"])
def test_old_login_get_moves_to_the_app_without_consuming_a_link(split_site, path):
    client = TestClient(app, base_url=PUBLIC)
    response = client.get(path + "?t=example&next=%2Fsettings", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == PORTAL + path.rstrip("/") + "?t=example&next=%2Fsettings"
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["referrer-policy"] == "no-referrer"


def test_redirect_is_limited_to_public_host_login_gets(split_site):
    assert site_urls.login_redirect_url(
        "app.ubyhost.test", "/login", "",
        public_base_url=PUBLIC, app_base_url=PORTAL,
    ) == ""
    assert site_urls.login_redirect_url(
        "evil.example", "/login", "",
        public_base_url=PUBLIC, app_base_url=PORTAL,
    ) == ""
    for path in ("/", "/l/example", "/login/passkey/options", "/account/email/confirm", "/signup/verify"):
        assert site_urls.login_redirect_url(
            "ubyhost.test", path, "", public_base_url=PUBLIC, app_base_url=PORTAL,
        ) == ""


def test_single_domain_keeps_existing_login_behavior(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", PUBLIC)
    monkeypatch.setattr(config, "APP_BASE_URL", "")
    assert config.app_base_url() == PUBLIC
    assert site_urls.login_redirect_url(
        "ubyhost.test", "/login", "", public_base_url=PUBLIC, app_base_url=config.app_base_url(),
    ) == ""


def test_host_links_move_while_guest_and_public_links_keep_their_origin(split_site):
    assert mail_notify._app("/login/link?t=example") == PORTAL + "/login/link?t=example"
    assert mail_notify._app("/account/email/confirm?t=example").startswith(PORTAL + "/")
    assert filing_watchdog._stay_url(123) == PORTAL + "/reservations/123"
    assert mail_notify._public("/privacy") == PUBLIC + "/privacy"
    assert claim._stay_link(
        {"permalink_token": "existing-guest-link"}, {"id": 123},
    ) == PUBLIC + "/l/existing-guest-link/123"


def test_public_guest_path_is_not_redirected_to_the_host_app(split_site):
    db.init_db()
    response = TestClient(app, base_url=PUBLIC).get("/l/nonexistent-link", follow_redirects=False)
    assert response.status_code == 404
    assert not response.headers.get("location", "").startswith(PORTAL)


def test_app_login_and_pwa_assets_are_served_without_a_redirect_loop(split_site):
    db.init_db()
    client = TestClient(app, base_url=PORTAL)
    assert client.get("/login", follow_redirects=False).status_code == 200
    manifest = client.get("/manifest.webmanifest").json()
    assert manifest["start_url"] == "/login" and manifest["scope"] == "/"
    worker = client.get("/sw.js")
    assert worker.status_code == 200
    assert worker.headers["cache-control"] == "no-cache"


def _post_request(origin, *, cookie="", token=""):
    headers = [(b"host", b"app.ubyhost.test"), (b"origin", origin.encode())]
    if cookie:
        headers.append((b"cookie", (security.CSRF_COOKIE + "=" + cookie).encode()))
    if token:
        headers.append((security.CSRF_HEADER.encode(), token.encode()))
    return Request({
        "type": "http", "method": "POST", "scheme": "https", "server": ("app.ubyhost.test", 443),
        "path": "/login", "root_path": "", "query_string": b"", "headers": headers,
    })


def test_subdomain_forms_keep_host_only_csrf_cookies_and_require_a_token(split_site, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "secret_key", lambda: "domain-test-signing-key")
    request = _post_request(PORTAL)
    token = security.csrf_token(request)
    nonce = request.state.csrf_nonce
    response = Response()
    security.attach_csrf_cookie(request, response)
    cookie = response.headers["set-cookie"].lower()
    assert "domain=" not in cookie and "secure" in cookie and "httponly" in cookie
    valid = _post_request(PORTAL, cookie=nonce, token=token)
    asyncio.run(security.protect_host_post(valid))
    with pytest.raises(security.ExpiredFormError):
        asyncio.run(security.protect_host_post(_post_request(PORTAL, token="bad")))
    with pytest.raises(HTTPException) as failure:
        asyncio.run(security.protect_host_post(_post_request("https://evil.example", token="bad")))
    assert failure.value.status_code == 403



@pytest.mark.parametrize("kind", ["login_link", "account_invite", "email_confirm"])
def test_auth_mail_uses_the_app_origin_without_storing_the_token_in_the_body(
    split_site, monkeypatch, kind,
):
    queued = {}
    def capture(**kwargs):
        queued.update(kwargs)
        return 123
    monkeypatch.setattr(mail, "enqueue", capture)
    monkeypatch.setattr(db, "encrypt_field", lambda value: "encrypted:" + value)
    result = mail_notify.link_mail(
        kind=kind, user_id=7, to_email="host@example.test",
        token="private-login-token", minutes=15, lang="en",
    )
    assert result == 123
    payload = queued["payload"]
    path = mail_notify.LINK_MAIL[kind][1]
    assert PORTAL + path + "?t=" in payload["text"]
    assert PORTAL + path + "?t=" in payload["html"]
    assert PUBLIC + path not in payload["text"]
    assert "private-login-token" not in payload["text"] + payload["html"]
    assert payload[mail.CLAIM_SECRET_KEY] == "encrypted:private-login-token"


def test_post_to_old_login_is_not_forwarded_across_origins(split_site):
    db.init_db()
    client = TestClient(app, base_url=PUBLIC)
    response = client.post(
        "/login", data={"_csrf": "", "email": "nobody@example.test"}, follow_redirects=False,
    )
    assert response.status_code != 302
    assert not response.headers.get("location", "").startswith(PORTAL)



def test_signed_out_app_root_renders_login_without_redirecting(split_site):
    db.init_db()
    client = TestClient(app, base_url=PORTAL)
    response = client.get("/?lang=en", follow_redirects=False)
    assert response.status_code == 200
    assert response.url.path == "/"
    assert 'action="/login"' in response.text
    assert 'name="_csrf"' in response.text
    assert "landing.css" not in response.text
    assert 'rel="canonical"' not in response.text
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "no-store" in response.headers["cache-control"]


def test_public_root_and_single_domain_still_render_marketing(split_site, monkeypatch):
    db.init_db()
    public = TestClient(app, base_url=PUBLIC).get("/", follow_redirects=False)
    assert public.status_code == 200
    assert "landing.css" in public.text
    monkeypatch.setattr(config, "APP_BASE_URL", "")
    single = TestClient(app, base_url=PUBLIC).get("/", follow_redirects=False)
    assert single.status_code == 200
    assert "landing.css" in single.text


def test_signed_in_app_root_still_renders_the_dashboard(split_site, monkeypatch):
    from app import auth
    from tests.conftest import login_as

    db.init_db()
    username = "domain-root-host"
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (username,))
    if account is None:
        user_id = auth.create_account("domain-root@example.test", "Root Host", username=username)
    else:
        user_id = account["id"]
    client = TestClient(app, base_url=PORTAL)
    try:
        login_as(client, username, url="/login?lang=en")
        response = client.get("/?lang=en", follow_redirects=False)
        assert response.status_code == 200
        assert "data-calendar" in response.text
        assert 'action="/login"' not in response.text
        assert "landing.css" not in response.text
    finally:
        for table in ("login_token", "webauthn_challenge", "legal_acceptance", "email_outbox", "audit"):
            column = "owner_user_id" if table in {"email_outbox", "audit"} else "user_account_id"
            db.execute(f"DELETE FROM {table} WHERE {column} = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))



def test_app_root_login_keeps_host_languages(split_site):
    db.init_db()
    response = TestClient(app, base_url=PORTAL).get("/?lang=vi")
    assert response.status_code == 200
    assert '<html lang="vi"' in response.text
