"""Brief 0900: browser checks for the public booking terms page (geometry at 390 px,
heading visible, CS/EN switch tap height, screenshot)."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn

from app.main import app
from tests.browser_support import chromium_launch_kwargs

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT = REPO_ROOT / "docs" / "tasks" / "screenshots-0900" / "terms-390.png"


@pytest.fixture(scope="module")
def base():
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
        pytest.fail("the booking terms test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for booking terms page coverage")


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_terms_page_geometry_390(base, lang):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context = browser.new_context(viewport={"width": 390, "height": 900})
            page = context.new_page()
            page.goto(f"{base}/terms/booking?lang={lang}")
            page.wait_for_load_state("load")

            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert page.locator("h1").first.is_visible()
            for el in page.locator(".pp-bk-lang a").all():
                box = el.bounding_box()
                assert box["height"] >= 44, f"language switch is {box['height']} px high"

            if lang == "cs":
                SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SCREENSHOT), full_page=True)
        finally:
            browser.close()
