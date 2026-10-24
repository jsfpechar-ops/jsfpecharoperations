"""Passkey client recovery on rendered login controls, Chromium and WebKit.

Network/WebAuthn promises are controlled to reproduce timing failures without
using a real account, a passkey, or the external Cloudflare service.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app import config, db, passkeys
from app.main import app

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

TESTS = Path(__file__).parent
SOURCE = (TESTS.parent / "app/static/passkeys.js").read_text(encoding="utf-8")
HARNESS = (TESTS / "passkeys_client_cases.js").read_text(encoding="utf-8")
CASES = [
    "late-capability", "late-options", "late-conditional-credential",
    "stalled-fetch", "stalled-body", "stalled-sheet", "stalled-login-post", "html-challenge", "null-credential",
    "redirected-response", "invalid-json", "missing-challenge", "missing-redirect", "rate-limit",
    "cancel-and-retry", "duplicate-click", "capability-unavailable", "success", "add-timeout",
]
ENGINE = os.environ.get("PASSKEY_BROWSER", "chromium")
SHOT_DIR = Path(os.environ.get("UBYHOST_PASSKEY_SHOTS", "/tmp/passkey-login-shots"))


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            instance = getattr(playwright, ENGINE).launch(headless=True)
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"{ENGINE} is required for passkey browser checks")
        yield instance
        instance.close()


@pytest.mark.parametrize("width", [390, 820, 1024, 1180, 1280])
@pytest.mark.parametrize("case", CASES)
def test_passkey_login_recovers_on_rendered_controls(browser, monkeypatch, width, case):
    db.init_db()
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://ubyhost.test")
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    monkeypatch.setattr(passkeys, "available", lambda: True)
    with TestClient(app) as client:
        response = client.get("/login?lang=en", follow_redirects=True)
        assert response.status_code == 200
        # The harness executes the real passkey source exactly once and controls
        # fetch/system sheets; other scripts and real challenges are unnecessary.
        html = re.sub(r"<script\b[^>]*>.*?</script>", "", response.text, flags=re.S)
        assert "data-passkey-login-button" in html
        context = browser.new_context(
            viewport={"width": width, "height": 1000},
            has_touch=width < 1280,
            service_workers="block",
        )

        def serve(route):
            parsed = urlsplit(route.request.url)
            if parsed.path == "/login":
                route.fulfill(status=200, content_type="text/html", body=html)
            elif parsed.path.startswith("/static/"):
                asset = client.get(parsed.path)
                route.fulfill(
                    status=asset.status_code,
                    content_type=asset.headers.get("content-type", "application/octet-stream"),
                    body=asset.content,
                )
            else:
                route.abort()

        context.route("**/*", serve)
        try:
            page = context.new_page()
            page.goto("https://ubyhost.test/login?lang=en")
            result = page.evaluate(
                "async (args) => {"
                + HARNESS
                + "; return await runPasskeyClientCase(args.source, args.name, document); }",
                {"source": SOURCE, "name": case},
            )
            assert result == case
            assert not page.locator("[data-passkey-login-button]").is_disabled()
            assert page.locator('[data-login-form] button[type="submit"]').is_enabled()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), f"login overflows at {width}px"
            if width == 390 and case in ("success", "stalled-fetch"):
                SHOT_DIR.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SHOT_DIR / f"login-{ENGINE}-{case}-390.png"), full_page=True)
        finally:
            context.close()
