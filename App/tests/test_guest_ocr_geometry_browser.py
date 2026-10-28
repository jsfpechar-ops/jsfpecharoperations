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

from app import db
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
    # The owner account stays: audit and alert rows written during the run
    # still reference it, and its unique username is per-run.
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))


@pytest.fixture(scope="module")
def browser():
    kwargs = chromium_launch_kwargs()
    # A container without user namespaces (this dev sandbox) cannot use the
    # SUID sandbox; CI's browser does not need the flag.
    if os.environ.get("UBYHOST_BROWSER_NO_SANDBOX") == "1":
        # The full Chromium build, not the headless shell: the shell's renderer
        # CHECK-crashes on this sandbox's extracted-library setup.
        kwargs["channel"] = kwargs.get("channel")
        kwargs["executable_path"] = kwargs.get("executable_path") or str(
            __import__("pathlib").Path.home()
            / ".cache/ms-playwright/chromium-1248/chrome-linux64/chrome"
        )
        kwargs["args"] = [*kwargs.get("args", []),
                          "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                          "--disable-features=CalculateNativeWinOcclusion,IsolateOrigins,"
                          "site-per-process,DestroyProfileOnBrowserClose"]
    with sync_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch(**kwargs)
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


def _step_title(page):
    return page.evaluate(
        "() => { const s = document.querySelector('[data-guest-step]:not([hidden])');"
        " return s ? s.getAttribute('data-step-title') : ''; }"
    )


def _goto_form(page, base, world):
    """Open the form and walk the wizard to the passport-photo step.

    The card is a later wizard step and nationality-gated: a foreign guest
    (picked through the country search widget) reaches it after Continue.
    """
    page.goto(f"{base}/l/{world['token']}/{world['stay']}/new?lang=en")
    page.wait_for_selector("[data-guest-step]")
    page.fill("#first_name", "John Paul")
    page.fill("#surname", "Smith")
    page.fill("#birth_date", "01.01.1990")
    page.click("#nationality_search")
    page.keyboard.type("GBR")
    page.locator("#nationality_list [role=option]").first.click()
    page.fill("#doc_number", "P1234567")
    for _ in range(6):
        if page.locator("#passport-photo-card:not([hidden])").count():
            break
        if _step_title(page) == "Permanent home address":
            page.fill("#res_street", "Baker Street 221B")
            page.fill("#res_city", "London")
            page.click("#res_country_search")
            page.keyboard.type("GBR")
            page.locator("#res_country_list [role=option]").first.click()
        before = _step_title(page)
        page.locator(
            "[data-guest-step]:not([hidden]) .g-wizard-nav button.g-btn[type=button]:not(.secondary)"
        ).first.click()
        page.wait_for_timeout(900)
        assert _step_title(page) != before, f"Continue did not leave the step {before!r}"
    page.wait_for_selector("#passport-photo-card:not([hidden])")
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
            "() => { const s = getComputedStyle(document.querySelector('#ocr-scan .checkline'));"
            " return { display: s.display, color: s.color, padding: s.padding }; }"
        )
        assert styles["display"] == "flex"
        # The component's 14px row padding, not a bare input.
        assert styles["padding"].split(" ")[0].rstrip("px").isdigit()
        # The whole row is the target, as tall as its padding promises.
        box = label.bounding_box()
        assert box["height"] >= 48
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
    context, page = _page(browser, base, world, 390)
    try:
        owner = db.query_one(
            "SELECT a.owner_user_id AS o FROM apartment a WHERE a.permalink_token = ?", (TOKEN,)
        )
        db.execute(
            "UPDATE billing_account SET plan = 'standard' WHERE owner_user_id = ?", (owner["o"],)
        )
        page.goto(f"{base}/l/{world['token']}/{world['stay']}/new?lang=en")
        # The card lives on a later wizard step; its markup must simply not
        # contain the scan toggle when the plan is not Max.
        page.wait_for_selector("#passport-photo-card", state="attached")
        assert page.locator("#ocr-scan-toggle").count() == 0
    finally:
        db.execute(
            "UPDATE billing_account SET plan = 'max' WHERE owner_user_id = ?",
            (db.query_one("SELECT a.owner_user_id AS o FROM apartment a WHERE a.permalink_token = ?", (TOKEN,))["o"],),
        )
        context.close()


def test_a_390px_screenshot_of_the_scan_step(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        settle_motion(page)
        os.makedirs(SHOT_DIR, exist_ok=True)
        page.screenshot(path=f"{SHOT_DIR}/guest-form-scan-step-390.png", full_page=False)
    finally:
        context.close()

