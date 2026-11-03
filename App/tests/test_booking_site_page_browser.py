"""Brief 0818: browser geometry for the public booking page (touch targets, no
horizontal scroll, accent colour, no-JS calendar navigation)."""
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

from app import auth, booking_site, config, db, property_page
from app.main import app
from tests.browser_support import chromium_launch_kwargs

OWNER = "browserbook"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT = REPO_ROOT / "docs" / "tasks" / "screenshots-0818" / "booking-390.png"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture(scope="module")
def seeded():
    db.init_db()
    _cleanup()
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "STRIPE_MODE", "test")
    mp.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    mp.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)
    auth.create_account(f"{OWNER}@example.test", "Browser Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Browser Flat",
                                      "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 1800, "cleaning_fee_czk": 600,
                                     "cancellation_policy": "moderate"})
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 50 WHERE id = ?", (aid,))
    property_page.publish_page(aid, published=True)
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_site", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    db.insert("reservation", {"apartment_id": aid, "source": "manual", "uid": "browser-1",
                              "date_from": "2027-03-20", "date_to": "2027-03-22",
                              "status": "active", "created_at": now, "updated_at": now})
    slug = property_page.account_row(aid)["slug"]
    try:
        yield slug
    finally:
        mp.undo()
        _cleanup()


@pytest.fixture(scope="module")
def base(seeded):
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
        pytest.fail("the booking page test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for booking page geometry coverage")


@pytest.mark.parametrize("width", [360, 390, 1280])
def test_booking_page_geometry(base, seeded, width):
    url = (f"{base}/p/{seeded}?lang=cs&month=2027-03&date_from=2027-03-10"
           f"&date_to=2027-03-13&guests=2")
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context = browser.new_context(viewport={"width": width, "height": 900})
            page = context.new_page()
            page.goto(url)
            page.wait_for_load_state("load")

            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

            for selector, min_width in ((".pp-bk-day", 0), (".pp-bk-nav", 44),
                                        (".pp-bk-card .ui-btn", 0), (".pp-bk-lang a", 44)):
                for el in page.locator(selector).all():
                    box = el.bounding_box()
                    if box is None:
                        continue
                    assert box["height"] >= 44, f"{selector} is {box['height']} px high"
                    if min_width:
                        assert box["width"] >= min_width, f"{selector} is {box['width']} px wide"

            pay = page.locator(".pp-bk-card .ui-btn").filter(has_text="Zaplatit")
            assert pay.count() >= 1
            assert "Zaplatit" in pay.first.inner_text()

            start_bg = page.locator('.pp-bk-day[data-state="start"]').first.evaluate(
                "el => getComputedStyle(el).backgroundColor")
            accent_bg = page.evaluate("""() => {
                const probe = document.createElement('span');
                probe.style.backgroundColor = 'var(--accent)';
                document.body.appendChild(probe);
                const value = getComputedStyle(probe).backgroundColor;
                probe.remove();
                return value;
            }""")
            assert start_bg == accent_bg

            if width == 390:
                SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SCREENSHOT), full_page=True)
            context.close()
        finally:
            browser.close()


def test_calendar_works_without_javascript(base, seeded):
    url = (f"{base}/p/{seeded}?lang=cs&month=2027-03&date_from=2027-03-10"
           f"&date_to=2027-03-13&guests=2")
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context = browser.new_context(viewport={"width": 390, "height": 900},
                                          java_script_enabled=False)
            page = context.new_page()
            page.goto(url)
            with page.expect_navigation():
                page.locator('a.pp-bk-day[href*="date_from=2027-03-14"]').first.click()
            assert "date_from=2027-03-14" in page.url
            assert 'name="terms"' not in page.content()
            context.close()
        finally:
            browser.close()
