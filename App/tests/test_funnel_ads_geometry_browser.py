"""Computed geometry for the Funnel page ads export (0164 follow-up).

Markup cannot prove that the two ads-export buttons share a height, sit in
one row with the token gap, and that both funnel sections share the page
lane. The browser CI job installs Chromium and sets UBYHOST_REQUIRE_BROWSER,
so this runs on every pull request and is skipped without Playwright.
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

from app import auth, config, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    original = config.SIGNUP_ENABLED
    config.SIGNUP_ENABLED = True
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
    config.SIGNUP_ENABLED = original
    server.should_exit = True
    thread.join(timeout=5)


def _browser_session_cookie(username: str) -> str:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    return token


def test_funnel_ads_export_geometry(base):
    username = f"funnelgeom{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Funnel Geometry", role="admin", username=username)
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + "/admin/funnel?lang=en")
        page.wait_for_selector("#funnel-ads-export", timeout=30000)
        measured = page.evaluate(
            """() => {
              const lane = (el) => { if (!el) return null; const r = el.getBoundingClientRect();
                                     return [Math.round(r.left), Math.round(r.right)]; };
              const ads = document.querySelector('#funnel-ads-export');
              const posthog = document.querySelector('#funnel-posthog');
              const group = ads.querySelector('.ui-btn-group');
              const buttons = [...group.querySelectorAll('.ui-btn')].filter((b) => b.offsetParent !== null);
              const boxes = buttons.map((b) => { const box = b.getBoundingClientRect();
                return { top: box.top, right: box.right, bottom: box.bottom, left: box.left,
                         height: Math.round(box.height),
                         clipped: b.scrollWidth > b.clientWidth + 1 }; });
              const forms = [...group.querySelectorAll('form')].map((f) => f.getBoundingClientRect());
              return { ads: lane(ads), posthog: lane(posthog),
                       gap: getComputedStyle(group).gap,
                       formGaps: forms,
                       boxes,
                       sections: [...document.querySelectorAll('main .ui-section, body .ui-section')].length };
            }"""
        )
        browser.close()

    assert measured["ads"], "the ads export section must exist while signup is on"
    assert measured["posthog"], "the PostHog section must stay on the funnel page"
    assert measured["ads"] == measured["posthog"], "both funnel sections must share the page lane"
    boxes = measured["boxes"]
    assert len(boxes) == 2, "the ads export renders a download and a download-again button"
    assert len({box["height"] for box in boxes}) == 1, "neighboring buttons must share a height"
    assert boxes[0]["height"] == 40, f"buttons must be 40px tall like every ui-btn, got {boxes[0]['height']}"
    assert not any(box["clipped"] for box in boxes), "no button label may clip"
    assert measured["gap"] == "8px", f"the button group must use the token gap, got {measured['gap']}"
    tops = sorted({round(box["top"]) for box in boxes})
    assert len(tops) == 1, "the two buttons must sit in one row"
    assert boxes[0]["right"] <= boxes[1]["left"] + 1, "the buttons must not overlap"
    assert len(measured["formGaps"]) == 2


def test_funnel_ads_export_fits_the_phone(base):
    """No horizontal scroll, no clipped label, at the phone width."""
    username = f"funnelphone{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Funnel Phone", role="admin", username=username)
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + "/admin/funnel?lang=en")
        page.wait_for_selector("#funnel-ads-export", timeout=30000)
        measured = page.evaluate(
            """() => {
              const doc = document.documentElement;
              const section = document.querySelector('#funnel-ads-export');
              const sr = section.getBoundingClientRect();
              const btns = [...section.querySelectorAll('.ui-btn')].map((b) => {
                const r = b.getBoundingClientRect();
                return { top: Math.round(r.top), height: Math.round(r.height),
                         clipped: b.scrollWidth > b.clientWidth + 1 };
              });
              return { overflowX: doc.scrollWidth > doc.clientWidth + 1,
                       inLane: sr.left >= 0 && sr.right <= doc.clientWidth + 1,
                       btns, lane: [Math.round(sr.left), Math.round(sr.right)] };
            }"""
        )
        browser.close()

    assert not measured["overflowX"], "the funnel page must not scroll sideways on a phone"
    assert measured["inLane"], "the ads section must stay inside the phone lane"
    assert not any(btn["clipped"] for btn in measured["btns"]), "no button label may clip on a phone"
    assert len({btn["height"] for btn in measured["btns"]}) == 1, "buttons share a height on a phone"
    assert all(btn["height"] == 44 for btn in measured["btns"]), (
        f"buttons must keep the phone token height 44px, got {measured['btns']}"
    )
    assert measured["btns"], "the ads export must render while signup is on"
