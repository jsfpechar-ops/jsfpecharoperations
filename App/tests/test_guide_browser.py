"""0316: the Help & guide at phone and computer width (rule 7): no sideways scroll,
and a 390 px screenshot of each beginner section that exists. Briefs 0317, 0318
and 0328 rerun it for their own sections."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.test_submission_retry_cap import host as host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-guide"
SECTIONS = ("finding", "glossary", "cleaning", "guest_links", "business", "stays", "setup", "stay_fee", "invoices", "overview", "settings", "archive", "privacy_requests")


@pytest.fixture
def origin(host):
    db.init_db()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", host.cookies.get(auth.SESSION_COOKIE)
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_the_guide_fits_a_phone_and_a_computer(origin, lang):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the guide browser test")
        for width in (390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": origin[1], "url": origin[0] + "/"}])
            page = context.new_page()
            page.goto(f"{origin[0]}/guide?lang={lang}")
            page.locator("#finding").wait_for()
            assert page.evaluate("document.documentElement.scrollWidth") <= width, (lang, width)
            if width == 390 and lang in ("en", "vi"):
                suffix = "" if lang == "en" else "-vi"
                for section in SECTIONS:
                    if page.locator(f"#{section}").count():
                        page.locator(f"#{section}").screenshot(path=str(SHOTS / f"guide-{section}-390{suffix}.png"))
            context.close()
        browser.close()
