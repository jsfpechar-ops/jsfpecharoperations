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
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as



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
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    return token


def test_dashboard_actions_share_height_and_gap(base):
    username = f"geometry{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Geometry", role="host", username=username)
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
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
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


def _open_month_filter(page):
    panel = page.locator('form[data-filter-panel][id="list-filter-panel"]')
    if not panel.is_visible():
        page.locator('button[data-filter-toggle][aria-controls="list-filter-panel"]').click()
    panel.wait_for(state="visible", timeout=30000)


def test_the_month_filter_shares_its_page_edges(base):
    """The filter row must share the page lane and read as one control group.

    The wrap auto-centres its children; a filter that resets margin to 0
    hangs west of the content. An auto margin on the stepper creates the
    opposite problem by stranding Previous/Next at the east edge.
    """
    username = f"geomfilter{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Geometry", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Geometry s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {
        "internal_name": "Geometry loft", "owner_user_id": owner, "legal_entity_id": entity,
        "permalink_token": f"gf{secrets.token_hex(4)}",
        "active": 1, "created_at": db.utcnow(),
    })
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_cookies(
            [{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}]
        )
        page = context.new_page()
        measured = {}
        for route in ("/stay-fees?lang=en", "/invoices?lang=en"):
            page.goto(base + route)
            _open_month_filter(page)
            measured[route] = page.evaluate(
                """() => {
                  const box = (selector) => document.querySelector(selector).getBoundingClientRect();
                  const edges = (selector) => {
                    const rect = box(selector);
                    return [Math.round(rect.left), Math.round(rect.right)];
                  };
                  const filter = box('.list-filter');
                  const control = box('.month-control');
                  const stepper = box('.month-row .month-step:last-child');
                  return {
                    filter: edges('.list-filter'),
                    table: edges('.panel, table'),
                    title: edges('.page-header, h1'),
                    controlGap: Math.round(stepper.left - control.right),
                    rightSlack: Math.round(filter.right - stepper.right),
                  };
                }"""
            )
        responsive = {}
        for width in (1280, 1024, 390, 360):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                for path in ("/stay-fees", "/invoices"):
                    route = f"{path}?lang={lang}"
                    page.goto(base + route)
                    _open_month_filter(page)
                    responsive[(width, route)] = page.evaluate(
                        """() => {
                          const root = document.documentElement;
                          const filter = document.querySelector('.list-filter');
                          const bounds = filter.getBoundingClientRect();
                          const children = [...filter.children].filter(
                            (element) => getComputedStyle(element).display !== 'none'
                          );
                          const buttons = [...filter.querySelectorAll('.month-step')];
                          return {
                            overflow: root.scrollWidth > root.clientWidth + 1,
                            childOutside: children.some((element) => {
                              const box = element.getBoundingClientRect();
                              return box.left < bounds.left - 1 || box.right > bounds.right + 1;
                            }),
                            clippedText: children.concat(buttons).some(
                              (element) => element.scrollWidth > element.clientWidth + 1
                            ),
                            buttonHeights: buttons.map(
                              (button) => Math.round(button.getBoundingClientRect().height)
                            ),
                          };
                        }"""
                    )
        browser.close()
    for route, geometry in measured.items():
        assert geometry["filter"] == geometry["table"], f"{route}: filter must align with the table below"
        assert geometry["filter"][0] == geometry["title"][0], f"{route}: filter must align with the title"
        assert 8 <= geometry["controlGap"] <= 24, f"{route}: period controls must remain one compact group"
        assert geometry["rightSlack"] > 40, f"{route}: stepper must not be stranded at the far edge"
    for (width, route), geometry in responsive.items():
        assert not geometry["overflow"], f"{width}px {route}: page must not scroll sideways"
        assert not geometry["childOutside"], f"{width}px {route}: filter controls must stay in their lane"
        assert not geometry["clippedText"], f"{width}px {route}: translated controls must not clip"
        expected_height = 44 if width <= 600 else 42
        assert geometry["buttonHeights"] == [expected_height, expected_height]
