"""0500: a sidebar link still navigates with the prefetch rules in place (real Chromium)."""
import os
import secrets
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    db.init_db()
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _session_cookie(username):
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    return token


def test_sidebar_link_still_navigates_with_prefetch_rules(base):
    username = f"prefetch{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Prefetch QA", role="host", username=username)
    session = _session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(f"{base}/?lang=en")
            page.locator('#app-sidebar a[href="/reservations"]').first.click()
            page.wait_for_url("**/reservations**", timeout=15000)
            assert "/reservations" in page.url
            blocked = [e for e in errors if "Content Security Policy" in e or "speculation" in e.lower()]
            assert not blocked, blocked
        finally:
            browser.close()
