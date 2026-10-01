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
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Geometry-Host-123"


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
    deadline = __import__("time").time() + 15
    while not server.started and __import__("time").time() < deadline:
        __import__("time").sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _browser_session_cookie(username: str) -> str:
    """Log in through the ASGI app so CSRF and acceptance gates match other tests."""
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    return token


def test_dashboard_actions_share_height_and_gap(base):
    username = f"geometry{secrets.token_hex(4)}"
    owner = auth.create_account(username, PASSWORD, "Geometry", role="host", must_change_password=False)
    entity = db.insert("legal_entity", {"name": "Geometry s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {
        "internal_name": "Geometry loft", "owner_user_id": owner, "legal_entity_id": entity,
        "permalink_token": f"geom{secrets.token_hex(4)}",
        "active": 1, "created_at": db.utcnow(),
    })
    db.insert("ical_feed", {
        "apartment_id": apartment, "url": "https://calendar.example/geometry.ics",
        "active": 1, "created_at": db.utcnow(),
    })
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies(
            [{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}]
        )
        page = context.new_page()
        page.goto(base + "/?lang=en")
        page.wait_for_selector(".dashboard-actions .action-group", timeout=30000)
        aligned = page.evaluate(
            """() => {
              const rect = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; };
              return {
                stats: rect(document.querySelector('.dashboard-stats')),
                head: rect(document.querySelector('.host-today-head')),
                first: rect(document.querySelector('section, .panel.empty')),
              };
            }"""
        )
        assert aligned["stats"] == aligned["head"], "the stat tiles must span the header card exactly"
        assert aligned["stats"] == aligned["first"], "the stat tiles must align with the content below"
        measured = page.locator(".dashboard-actions .action-group").evaluate(
            """(group) => {
              const buttons = [...group.querySelectorAll('.btn')];
              const boxes = buttons.map((button) => {
                const box = button.getBoundingClientRect();
                return { top: box.top, right: box.right, bottom: box.bottom, left: box.left,
                         height: Math.round(box.height),
                         clipped: button.scrollWidth > button.clientWidth + 1 };
              });
              return { gap: getComputedStyle(group).gap, boxes };
            }"""
        )
        browser.close()
    boxes = measured["boxes"]
    assert measured["gap"] == "8px"
    assert boxes
    assert len({box["height"] for box in boxes}) == 1
    assert boxes[0]["height"] == 42
    assert not any(box["clipped"] for box in boxes)
    for left, right in zip(boxes, boxes[1:]):
        separated = left["right"] <= right["left"] + 1 or right["right"] <= left["left"] + 1
        stacked = left["bottom"] <= right["top"] + 1 or right["bottom"] <= left["top"] + 1
        assert separated or stacked


def test_the_month_filter_shares_its_page_edges(base):
    """The filter row must sit in the same lane as the table below it.

    The wrap auto-centres its children; a filter that resets margin to 0
    hangs west of the content, which a host spotted on Stay fee.
    """
    username = f"geomfilter{secrets.token_hex(4)}"
    owner = auth.create_account(username, PASSWORD, "Geometry", role="host", must_change_password=False)
    entity = db.insert("legal_entity", {"name": "Geometry s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {
        "internal_name": "Geometry loft", "owner_user_id": owner, "legal_entity_id": entity,
        "permalink_token": f"gf{secrets.token_hex(4)}",
        "active": 1, "created_at": db.utcnow(),
    })
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_cookies(
            [{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}]
        )
        page = context.new_page()
        page.goto(base + "/stay-fees?lang=en")
        page.wait_for_selector(".host-month-filter", timeout=30000)
        aligned = page.evaluate(
            """() => {
              const rect = (el) => { const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; };
              return {
                filter: rect(document.querySelector('.host-month-filter')),
                table: rect(document.querySelector('.panel, table')),
                title: rect(document.querySelector('.page-header, h1')),
              };
            }"""
        )
        browser.close()
    assert aligned["filter"] == aligned["table"], "the month filter must align with the table below it"
    assert aligned["filter"][0] == aligned["title"][0], "the month filter must align with the page title"
