"""Browser checks for stay invoice pages (task 0020).

Markup cannot prove the picker and form fit every width. The browser CI job
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
from tests.invoice_stay_helper import make_stay


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


WIDTHS = (360, 390, 1280)
SHOTS = os.environ.get("UBYHOST_SHOTS_DIR")


def _host():
    username = f"invstay{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Stay Invoices", role="host", username=username)
    entity = db.insert("legal_entity", {
        "name": "Stay s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    stay = make_stay(owner)
    return username, entity, stay


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")


def test_stay_invoice_pages_fit_every_width(base):
    username, entity, stay = _host()
    session = _browser_session_cookie(username)
    pages = {
        "picker": "/invoices/new?lang=cs",
        "form": f"/invoices/new?reservation_id={stay}&entity={entity}&lang=cs",
        "stay": f"/reservations/{stay}?lang=cs",
    }
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in WIDTHS:
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            for name, path in pages.items():
                page.goto(base + path)
                page.wait_for_load_state("networkidle")
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth - window.innerWidth"
                )
                assert overflow <= 1, f"{name} overflows by {overflow}px at {width}px"
                if SHOTS:
                    page.screenshot(path=os.path.join(SHOTS, f"{name}-{width}.png"), full_page=True)
            context.close()
        browser.close()


def test_issue_with_javascript_off(base):
    username, entity, stay = _host()
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + f"/invoices/new?reservation_id={stay}&entity={entity}&lang=cs")
        page.fill("#buyer_name", "Jan Novák")
        page.fill('input[name="stay_price"]', "4500")
        page.click(".invoice-actions button.accent.primary")
        page.wait_for_load_state("load")
        assert "/invoices/" in page.url and "/invoices/new" not in page.url, page.url
        browser.close()
