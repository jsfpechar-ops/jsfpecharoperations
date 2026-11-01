"""0500: same-origin prefetch rules, rendered only in the signed-in host shell."""
from __future__ import annotations

import json
import re
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.main import app
from tests.test_signed_in_chrome import host_with_property  # noqa: F401  (fixture reuse)

RULES = re.compile(r'<script type="speculationrules">(.*?)</script>', re.S)
EXCLUSIONS = ("[data-no-prefetch]", "[target=_blank]", "[download]", "/logout*", "/lang*",
              "/api/*", "/admin/*", "/*export*", "/*.pdf*", "/*/pdf*", "/*.zip*")


def test_signed_in_shell_renders_prefetch_rules_with_exclusions(host_with_property):
    page = host_with_property.get("/?lang=en").text
    match = RULES.search(page)
    assert match, "speculation rules block missing from the signed-in shell"
    rule = json.loads(match.group(1))["prefetch"][0]
    assert rule["eagerness"] == "moderate"
    where = json.dumps(rule["where"])
    assert '"href_matches": "/*"' in where
    for pattern in EXCLUSIONS:
        assert pattern in where, pattern


def test_login_page_has_no_prefetch_rules():
    page = TestClient(app).get("/login?lang=en").text
    assert "speculationrules" not in page


@pytest.fixture
def live_host(host_with_property):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    base = f"http://127.0.0.1:{port}"
    cookies = [{"name": c.name, "value": c.value, "url": base + "/"}
               for c in host_with_property.cookies.jar]
    yield {"base": base, "cookies": cookies}
    server.should_exit = True
    thread.join(timeout=5)


def test_sidebar_link_still_navigates_with_prefetch_rules(live_host):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context()
            context.add_cookies(live_host["cookies"])
            page = context.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(f"{live_host['base']}/?lang=en")
            page.locator('.ui-sidebar a[href="/reservations"]').first.click()
            page.wait_for_url("**/reservations**", timeout=15000)
            assert "/reservations" in page.url
            blocked = [e for e in errors if "Content Security Policy" in e or "speculation" in e.lower()]
            assert not blocked, blocked
        finally:
            browser.close()
