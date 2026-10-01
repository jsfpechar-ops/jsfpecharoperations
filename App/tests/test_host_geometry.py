"""Computed geometry for grouped host actions.

Markup cannot prove two neighboring buttons share a height. The browser CI job
installs Chromium and sets UBYHOST_REQUIRE_BROWSER, so this runs on every pull
request and is skipped in environments without Playwright.
"""
import os
import secrets
import socket
import threading

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn

from app import auth, db
from app.main import app

PASSWORD = "Geometry-Host-123"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = __import__("time").time() + 15
    while not server.started and __import__("time").time() < deadline:
        __import__("time").sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_dashboard_actions_share_height_and_gap(base):
    db.init_db()
    username = f"geometry-{secrets.token_hex(4)}"
    owner = auth.create_account(username, PASSWORD, "Geometry", role="host", must_change_password=False)
    entity = db.insert("legal_entity", {"name": "Geometry s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {
        "internal_name": "Geometry loft", "owner_user_id": owner, "legal_entity_id": entity,
        "active": 1, "created_at": db.utcnow(),
    })
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(base + "/login?lang=en")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_selector(".dashboard-actions .action-group", timeout=60000)
        measured = page.locator(".action-group").first.evaluate(
            """(group) => {
              const buttons = [...group.querySelectorAll('.btn')];
              return {
                gap: getComputedStyle(group).gap,
                heights: buttons.map((button) => Math.round(button.getBoundingClientRect().height)),
              };
            }"""
        )
        browser.close()
    assert measured["gap"] == "8px"
    assert measured["heights"]
    assert len(set(measured["heights"])) == 1
    assert measured["heights"][0] == 42
