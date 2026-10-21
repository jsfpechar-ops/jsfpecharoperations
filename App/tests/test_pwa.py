"""Brief 0219: the installable app (manifest, icons, service worker, offline page)."""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, db
from app.main import app
from tests.conftest import login_as

APP_DIR = Path(__file__).resolve().parent.parent / "app"
STATIC = APP_DIR / "static"


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def _signed_in() -> TestClient:
    db.init_db()
    username = f"pwa{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Pwa Host", role="host", username=username)
    client = _client()
    login_as(client, username, url="/login?lang=en")
    return client


def test_the_manifest_makes_an_installable_standalone_app():
    response = _client().get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/login"
    assert manifest["scope"] == "/" and manifest["id"] == "/"
    assert manifest["theme_color"] == manifest["background_color"] == "#f7f7f5"
    purposes = {(icon["sizes"], icon["purpose"]) for icon in manifest["icons"]}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= purposes


def test_every_manifest_icon_exists_at_its_stated_size_and_is_opaque():
    for icon in _client().get("/manifest.webmanifest").json()["icons"]:
        path = STATIC / icon["src"].split("?")[0].removeprefix("/static/")
        width, height = icon["sizes"].split("x")
        with Image.open(path) as image:
            assert image.size == (int(width), int(height)), icon["src"]
            assert image.mode == "RGB", icon["src"]
    with Image.open(STATIC / "icons" / "badge-96.png") as badge:
        assert badge.size == (96, 96) and badge.mode == "RGBA"


def test_the_service_worker_is_served_from_the_root_and_always_revalidated():
    response = _client().get("/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-cache"


def test_the_service_worker_stores_only_the_offline_page():
    # Pages are no-store (they carry passport numbers) and /static is versioned
    # and cached by the browser, so the worker must never keep either.
    source = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert source.count("cache.put(") == 1
    assert "cache.put(OFFLINE_URL, response)" in source
    assert "addAll(" not in source and "cache.add(" not in source
    assert 'req.mode !== "navigate"' in source
    assert "/^\\/l(\\/|$)/.test(url.pathname)" in source


@pytest.mark.parametrize(
    "lang,title", [("en", "You are offline"), ("cs", "Jste offline"), ("vi", "Bạn đang ngoại tuyến")]
)
def test_the_offline_page_speaks_the_requested_language(lang, title):
    response = _signed_in().get(f"/offline?lang={lang}")
    assert response.status_code == 200
    assert response.headers["content-language"] == lang
    assert title in response.text
    assert "noindex" in response.headers["x-robots-tag"]


def test_login_and_host_pages_link_the_manifest_and_the_app_script():
    login_page = _client().get("/login?lang=en").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in login_page
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in login_page
    assert "/static/pwa.js?v=" in login_page
    if "data-passkey-login-button" in login_page:  # the hint sits with the passkey button
        assert "data-pwa-standalone" in login_page
    settings = _signed_in().get("/settings?lang=en").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in settings
    assert "/static/pwa.js?v=" in settings
    assert 'id="settings-group-phone"' in settings
    assert 'href="#settings-group-phone"' in settings
    # Without JavaScript the generic how-to is the one visible line.
    assert "<p class=\"ui-sub\" data-pwa-other>" in settings


def test_guest_pages_never_offer_the_host_app():
    guest_base = (APP_DIR / "templates" / "guest" / "base.html").read_text(encoding="utf-8")
    assert "manifest" not in guest_base and "pwa.js" not in guest_base
