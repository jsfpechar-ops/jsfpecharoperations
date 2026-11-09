"""Brief 0821: browser checks for the guest booking page (paid state, geometry,
screenshot at 390 px, and the cancel flow with JavaScript switched off)."""
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

from app import auth, booking_checkout, booking_site, booking_webhook, config, db, property_page
from tests.conftest import mark_security_prompt_seen
from app import stripe_connect
from app.main import app
from tests.browser_support import chromium_launch_kwargs

OWNER = "browsermanage"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT = REPO_ROOT / "docs" / "tasks" / "screenshots-0821" / "guest-390.png"
CORRECTION_SCREENSHOT = REPO_ROOT / "docs" / "tasks" / "screenshots-0901" / "guest-correction-390.png"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM settings WHERE key = ?", ("invoice_purge_unlock",))
    db.insert("settings", {"key": "invoice_purge_unlock", "value": "1"})
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    for e in db.query("SELECT id FROM legal_entity WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM invoice_item WHERE invoice_id IN "
                   "(SELECT id FROM invoice WHERE legal_entity_id = ?)", (e["id"],))
        db.execute("DELETE FROM invoice WHERE legal_entity_id = ?", (e["id"],))
        db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id = ?", (e["id"],))
    db.execute("DELETE FROM settings WHERE key = ?", ("invoice_purge_unlock",))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


class _FakeRefunds:
    def create(self, params=None, options=None):
        return {"id": "re_browser_test"}


@pytest.fixture(scope="module")
def seeded():
    db.init_db()
    _cleanup()
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "STRIPE_MODE", "test")
    mp.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    mp.setattr(config, "STRIPE_MONTHLY_API_CALLS", 100)

    class _V1:
        pass

    v1 = _V1()
    v1.refunds = _FakeRefunds()

    class _Client:
        pass

    client = _Client()
    client.v1 = v1
    mp.setattr(stripe_connect, "_api", lambda: client)
    mp.setattr(stripe_connect, "_client", lambda: client)
    mark_security_prompt_seen(auth.create_account(f"{OWNER}@example.test", "Manage Host", username=OWNER))
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    entity = db.insert("legal_entity", {"owner_user_id": oid, "name": "Manage Host",
                                        "seat": "Praha 1", "ico": "04656679",
                                        "registry_entry": "ŽR", "vat_status": "non_payer",
                                        "contact_email": "host@example.test",
                                        "created_at": db.utcnow()})
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Manage Flat",
                                      "legal_entity_id": entity, "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 1800, "cleaning_fee_czk": 600,
                                     "cancellation_policy": "moderate"})
    property_page.publish_page(aid, published=True)
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_manage", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })
    q = booking_site.quote(aid, "2027-06-10", "2027-06-13", 2)
    hold = booking_checkout.hold_dates(aid, "2027-06-10", "2027-06-13")
    row = booking_site.create_pending(aid, oid, q, guest_name="Petr Svoboda",
                                      guest_email="petr@example.test", lang="cs", hold_id=hold)
    booking_site.attach_session(row["id"], "cs_browser_manage")
    booking_webhook.handle({"id": "evt_browser_manage", "type": "checkout.session.completed",
                            "data": {"object": {
                                "id": "cs_browser_manage", "payment_status": "paid",
                                "payment_intent": "pi_browser_manage",
                                "metadata": {"site_booking_id": str(row["id"])}}}})
    bid = int(row["id"])
    try:
        yield {"slug": property_page.account_row(aid)["slug"], "bid": bid,
               "token": booking_site.manage_token(bid)}
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
        pytest.fail("the guest booking page test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for guest booking page coverage")


def _url(base, seeded) -> str:
    return f"{base}/p/{seeded['slug']}/b/{seeded['bid']}/{seeded['token']}?lang=cs"


@pytest.mark.parametrize("width", [360, 390, 1280])
def test_guest_page_geometry(base, seeded, width):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context = browser.new_context(viewport={"width": width, "height": 900})
            page = context.new_page()
            page.goto(_url(base, seeded))
            page.wait_for_load_state("load")

            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            for selector in (".ui-btn", "summary", ".pp-bk-lang a"):
                for el in page.locator(selector).all():
                    if not el.is_visible():  # the danger button sits in the closed <details>
                        continue
                    box = el.bounding_box()
                    assert box["height"] >= 44, f"{selector} is {box['height']} px high"

            assert page.locator(".pp-bk-badge").inner_text().strip() == "Zaplaceno"
            if width == 390:
                SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(SCREENSHOT), full_page=True)
        finally:
            browser.close()


def test_guest_cancel_without_javascript(base, seeded):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context = browser.new_context(viewport={"width": 390, "height": 900},
                                          java_script_enabled=False)
            page = context.new_page()
            page.goto(_url(base, seeded))
            page.locator("summary").click()
            assert page.locator("details[open]").count() == 1
            page.locator(".ui-btn-danger").click()
            page.wait_for_load_state("load")
            assert page.locator(".pp-bk-badge").inner_text().strip() == "Zrušeno"
        finally:
            browser.close()


def test_guest_correction_button_390(base, seeded):
    from app import booking_cancel

    bid = seeded["bid"]
    if booking_site.get(bid)["status"] == "paid":
        assert booking_cancel.cancel(bid, by_host=True)["error"] is None
    invoice_id = int(booking_site.get(bid)["invoice_id"])
    assert db.query_one("SELECT id FROM invoice WHERE corrects_invoice_id = ?", (invoice_id,))
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context = browser.new_context(viewport={"width": 390, "height": 900})
            page = context.new_page()
            page.goto(_url(base, seeded))
            page.wait_for_load_state("load")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            links = page.locator(".pp-bk-actions a.ui-btn")
            labels = [text.strip() for text in links.all_inner_texts()]
            assert "Faktura (PDF)" in labels and "Opravný doklad (PDF)" in labels
            for el in links.all():
                box = el.bounding_box()
                assert box["height"] >= 44, f"button is {box['height']} px high"
            CORRECTION_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(CORRECTION_SCREENSHOT), full_page=True)
        finally:
            browser.close()
