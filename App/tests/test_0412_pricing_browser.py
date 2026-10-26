"""0412: the /cenik calculator in a real browser: numbers update, nothing scrolls sideways."""
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

from app import db
from app.main import app
from tests.browser_support import chromium_launch_kwargs

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0412"


@pytest.fixture(scope="module")
def base():
    db.init_db()
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
        pytest.fail("the pricing test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _browser(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the pricing calculator test")


def test_the_calculator_updates_and_fits_a_phone(base):
    capture = os.environ.get("UBYHOST_CAPTURE_0412") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        for width in (390, 1280):
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(f"{base}/cenik?lang=cs")
            page.wait_for_load_state("networkidle")
            assert page.locator("[data-pricing-calc]").is_visible(), width
            std = page.locator('[data-plan="standard"] [data-total]')
            top = page.locator('[data-plan="max"] [data-total]')
            assert (std.inner_text(), top.inner_text()) == ("99", "163"), width
            if capture and width == 390:
                page.screenshot(path=str(EVIDENCE / "cenik-390.png"), full_page=True)
            for _ in range(4):
                page.locator('[data-step="1"]').click()
            assert page.locator("[data-count]").inner_text() == "5", width
            assert std.inner_text() == "476", width  # 5 710 / 12
            assert page.locator('[data-plan="standard"] [data-apts]').inner_text() == "5 apartmánů", width
            page.locator('[data-interval="month"]').click()
            assert (std.inner_text(), top.inner_text()) == ("715", "1 090"), width
            page.locator("[data-ttlock]").check()
            assert std.inner_text() == "960", width  # 715 + 5 x 49
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), width
            page.close()
        browser.close()
