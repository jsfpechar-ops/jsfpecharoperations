"""Geometry for the document-scanning tickbox in the guest form (rule 7).

Markup cannot show that the tickbox row overflows a phone or that its label
loses baseline with the upload buttons, so these load the guest form in
Chromium at 390 and 1280 px, in the style of tests/test_wp28_geometry.py.
Skipped without Playwright unless UBYHOST_REQUIRE_BROWSER=1.
"""
import os
import secrets
import socket
import threading
import time

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, claim, db
from app import doc_ocr
from app.main import app
from app.routes import guest
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.conftest import complete_guest_claim
from tests.test_guest_navigation import (
    _cleanup,
    _make_apartment_with_stays,
    TOKEN,
)

NO_SIDEWAYS_SCROLL = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"

SHOT_DIR = os.environ.get("UBYHOST_SCREENSHOT_DIR", "/tmp/ubyhost-shots")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module", autouse=True)
def scan_world_on():
    """The live server must see billing on and the engine present."""
    from app import config
    from _pytest.monkeypatch import MonkeyPatch

    patcher = MonkeyPatch()
    patcher.setattr(config, "BILLING_ENABLED", True)
    patcher.setattr(doc_ocr, "TESSERACT", doc_ocr.TESSERACT or "/usr/bin/tesseract")
    yield
    patcher.undo()


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


@pytest.fixture(scope="module")
def world():
    """A Max property with the photo step on, its guest form claimed."""
    db.init_db()
    token, stay, _other = _make_apartment_with_stays()
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    db.update("apartment", apartment["id"], {"passport_photo_policy": "required_foreign"})
    owner_id = db.insert(
        "user_account",
        {
            "username": f"ocrgeo{secrets.token_hex(3)}",
            "password_hash": "x",
            "created_at": "2026-01-01",
            "must_change_password": 0,
        },
    )
    db.update("apartment", apartment["id"], {"owner_user_id": owner_id})
    db.execute(
        "INSERT INTO billing_account (owner_user_id, status, plan, updated_at) "
        "VALUES (?, 'active', 'max', '2026-01-01') ON CONFLICT(owner_user_id) DO UPDATE SET "
        "status = 'active', plan = 'max'",
        (owner_id,),
    )
    client = TestClient(app)
    client.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(client, token, stay, party_size=2)
    claim_cookie = client.cookies.get(guest.CLAIM_COOKIE)
    assert claim_cookie, "the claim must be confirmed before the form opens"
    yield {
        "token": token,
        "stay": stay,
        "claim_cookie": claim_cookie,
        "tesseract": doc_ocr.TESSERACT,
    }
    _cleanup()
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        yield chromium
        chromium.close()


def _page(browser, base, world, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([
        {"name": guest.LANG_COOKIE, "value": "en", "url": base + "/"},
        {"name": guest.CLAIM_COOKIE, "value": world["claim_cookie"], "url": base + "/"},
    ])
    return context, context.new_page()


def _goto_form(page, base, world):
    page.goto(f"{base}/l/{world['token']}/{world['stay']}/new?lang=en")
    page.wait_for_selector("#passport-photo-card")
    # The photo step is nationality-gated in JS; a foreign guest sees it.
    page.select_option("#nationality", "GBR")
    page.wait_for_selector("#ocr-scan-toggle")


@pytest.mark.parametrize("width", [390, 1280])
def test_the_scan_tickbox_fits_its_card_without_sideways_scroll(base, world, browser, width):
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        settle_motion(page)
        assert page.evaluate(NO_SIDEWAYS_SCROLL) <= 1
        box = page.locator("#ocr-scan").bounding_box()
        card = page.locator("#passport-photo-card").bounding_box()
        assert box["width"] <= card["width"]
        assert box["x"] >= card["x"] - 0.5
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_the_tickbox_uses_the_checkline_component(base, world, browser, width):
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        # The design's checkbox row: card-like, full-width tap target, the
        # help text inside the label, not under it.
        label = page.locator("#ocr-scan .checkline")
        assert label.count() == 1
        assert label.locator("small").count() == 1
        styles = page.evaluate(
            "() => { const el = document.querySelector('#ocr-scan .checkline');"
            " const s = getComputedStyle(el);"
            " return { display: s.display, radius: s.borderRadius, border: s.borderTopWidth }; }"
        )
        assert styles["display"] == "flex"
        assert styles["radius"].startswith("var") or float(styles["radius"].rstrip("px")) >= 8
        # The whole row is the target, as tall as its padding promises.
        box = label.bounding_box()
        assert box["height"] >= 19
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_the_status_line_appears_inside_the_card_when_scanning(base, world, browser, width, monkeypatch):
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        # Without a photo the tick still answers, and the message stays in the card.
        page.check("#ocr-scan-toggle")
        page.wait_for_selector("#ocr-scan-status:not([hidden])")
        settle_motion(page)
        assert page.evaluate(NO_SIDEWAYS_SCROLL) <= 1
        card = page.locator("#passport-photo-card").bounding_box()
        status = page.locator("#ocr-scan-status").bounding_box()
        assert status["x"] >= card["x"] - 0.5
        assert status["x"] + status["width"] <= card["x"] + card["width"] + 0.5
    finally:
        context.close()


def test_the_scan_tickbox_is_absent_when_the_plan_is_not_max(base, world, browser, monkeypatch):
    context, page = _page(browser, 390)
    try:
        owner = db.query_one(
            "SELECT a.owner_user_id AS o FROM apartment a WHERE a.permalink_token = ?", (TOKEN,)
        )
        db.execute(
            "UPDATE billing_account SET plan = 'standard' WHERE owner_user_id = ?", (owner["o"],)
        )
        page.goto(f"{base}/l/{world['token']}/{world['stay']}/new?lang=en")
        page.wait_for_selector("#passport-photo-card")
        assert page.locator("#ocr-scan-toggle").count() == 0
    finally:
        db.execute(
            "UPDATE billing_account SET plan = 'max' WHERE owner_user_id = ?",
            (db.query_one("SELECT a.owner_user_id AS o FROM apartment a WHERE a.permalink_token = ?", (TOKEN,))["o"],),
        )
        context.close()


def test_a_390px_screenshot_of_the_scan_step(base, world, browser):
    context, page = _page(browser, 390)
    try:
        _goto_form(page, base, world)
        settle_motion(page)
        os.makedirs(SHOT_DIR, exist_ok=True)
        page.screenshot(path=f"{SHOT_DIR}/guest-form-scan-step-390.png", full_page=False)
    finally:
        context.close()
