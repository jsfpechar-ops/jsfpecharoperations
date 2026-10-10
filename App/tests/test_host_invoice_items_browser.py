"""Browser coverage for invoice item visibility and responsive geometry."""
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


@pytest.fixture(scope="module")
def base():
    db.init_db()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
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


def _host():
    username = f"invitems{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Invoice items", role="host", username=username)
    entity = db.insert("legal_entity", {
        "name": "Items s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    return username, entity, make_stay(owner)


def _session_cookie(username):
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client.cookies.get(auth.SESSION_COOKIE)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for invoice item browser coverage")


def _open_form(page, base, username, entity, stay, locale="en"):
    page.context.add_cookies([{
        "name": auth.SESSION_COOKIE,
        "value": _session_cookie(username),
        "url": base + "/",
    }])
    page.goto(base + f"/invoices/new?reservation_id={stay}&entity={entity}&lang={locale}")
    page.wait_for_load_state("networkidle")


def test_other_description_follows_kind_and_keeps_value(base):
    username, entity, stay = _host()
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        page = browser.new_page(viewport={"width": 390, "height": 900})
        _open_form(page, base, username, entity, stay)
        row = page.locator("[data-item-body] [data-item-row]").first
        description = row.locator("[data-other-description]")
        kind = row.locator(".input-kind")

        assert description.is_hidden()
        kind.select_option("other")
        assert description.is_visible()
        description.locator("input").fill("Extra towels")
        kind.select_option("cleaning")
        assert description.is_hidden()
        assert description.locator("input").input_value() == "Extra towels"
        kind.select_option("other")
        assert description.is_visible()

        unit = row.locator('input[name="item_unit"]')
        assert unit.input_value() == ""
        assert unit.is_enabled()

        page.locator("[data-add-item]").click()
        added = page.locator("[data-item-body] [data-item-row]").nth(1)
        added.locator(".input-kind").select_option("other")
        assert added.locator("[data-other-description]").is_visible()
        added.locator("[data-other-description] input").fill("Late arrival")
        added.locator(".input-kind").select_option("cleaning")
        assert added.locator("[data-other-description]").is_hidden()
        assert added.locator('[name="item_description"]').input_value() == "Late arrival"
        browser.close()


def test_no_javascript_keeps_labeled_other_description_available(base):
    username, entity, stay = _host()
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        page = context.new_page()
        _open_form(page, base, username, entity, stay)
        description = page.locator("[data-other-description]").first
        assert description.is_visible()
        assert description.locator("span").inner_text() == "Description"
        browser.close()


def test_invoice_item_geometry_and_localized_screenshots(base):
    username, entity, stay = _host()
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in ("en", "cs"):
            for width in (360, 390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                page = context.new_page()
                _open_form(page, base, username, entity, stay, locale)
                row = page.locator("[data-item-body] [data-item-row]").first
                row.locator(".input-kind").select_option("other")
                row.locator('[name="item_description"]').fill("Extra towels")
                overflow = page.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                assert overflow <= 1, f"page overflowed by {overflow}px at {width}px ({locale})"

                controls = [
                    row.locator('[name="item_quantity"]'),
                    row.locator('[name="item_unit"]'),
                    row.locator('[name="item_unit_price"]'),
                ]
                tops = [control.bounding_box()["y"] for control in controls]
                assert max(tops) - min(tops) <= 2, f"misaligned controls at {width}px ({locale}): {tops}"
                remove = row.locator("[data-remove-item]")
                remove_box = remove.bounding_box()
                assert abs(remove_box["height"] - controls[0].bounding_box()["height"]) <= 1, (
                    f"Remove height differs from the first control at {width}px ({locale})"
                )
                stay_price = page.locator('input[name="stay_price"]').bounding_box()
                extra_price = controls[-1].bounding_box()
                assert abs(stay_price["width"] - extra_price["width"]) <= 1, (
                    f"stay and extra price widths differ at {width}px ({locale})"
                )
                if width == 1280:
                    assert abs(remove_box["y"] - tops[0]) <= 2, (
                        f"Remove does not align with the first control at {locale}: {remove_box['y']} vs {tops[0]}"
                    )
                    header = page.locator("#item-rows thead tr").bounding_box()
                    header_cells = page.locator("#item-rows thead th").evaluate_all(
                        "cells => cells.map(cell => { const r = cell.getBoundingClientRect(); "
                        "return { x: r.x, y: r.y, width: r.width, height: r.height }; })"
                    )
                    assert len(header_cells) == 6
                    heights = [cell["height"] for cell in header_cells]
                    y_positions = [cell["y"] for cell in header_cells]
                    assert max(heights) - min(heights) <= 1, f"header cells have different heights: {heights}"
                    assert max(y_positions) - min(y_positions) <= 1, f"header cells have different tops: {y_positions}"
                    assert abs(header_cells[-1]["x"] + header_cells[-1]["width"] - (header["x"] + header["width"])) <= 1, (
                        "the blank removal header does not fill its track"
                    )
                if shots:
                    page.add_style_tag(content=".invoice-actions { position: static !important; }")
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=os.path.join(shots, f"invoice-items-{locale}-{width}.png"), full_page=True)

                if width == 1280:
                    table = page.locator("#item-rows")
                    table.evaluate("el => { el.style.maxWidth = '390px'; el.style.marginInline = '0 auto'; }")
                    embedded_overflow = page.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                    assert embedded_overflow <= 1, f"embedded invoice table overflowed ({locale})"
                    if shots:
                        page.evaluate("window.scrollTo(0, 0)")
                        page.screenshot(path=os.path.join(shots, f"invoice-items-embedded-{locale}-390.png"), full_page=True)
                context.close()
        browser.close()
