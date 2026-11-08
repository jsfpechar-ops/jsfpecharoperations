"""Booking site setup page in Chromium (brief 0819): fit, target size, one primary button."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, booking_checkout, booking_site, booking_webhook, db, mail
from tests.browser_support import chromium_launch_kwargs
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures are re-created here)
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

GUARD = (Path(__file__).parent / "design_guard.js").read_text()
SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0819"

SMALL_TARGETS_JS = """() => Array.from(document.querySelectorAll('button, a.ui-btn, input:not([type=hidden]), select'))
  // A help-tip button is 24px drawn; its 44px hit area is the ::after overlay (host.css).
  .filter(el => !el.matches('.help-tip-btn'))
  .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
  .map(el => {
    // A radio or checkbox is hit through its wrapping label, so measure that.
    const box = (el.matches('input[type=radio], input[type=checkbox]') && el.closest('label')) || el;
    return [el.tagName, (el.textContent || el.value || '').trim().slice(0, 40), box.getBoundingClientRect().height];
  })
  .filter(row => row[2] < 44)"""

PRIMARY_PER_FORM_JS = """() => Array.from(document.forms)
  .map(form => form.querySelectorAll('.ui-btn-primary').length)
  .filter(count => count > 1)"""


HOST_SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0822"


@pytest.fixture
def paid_booking(wide_host, monkeypatch):
    """Brief 0822: one paid site booking for the page's first apartment, removed afterwards."""
    aid = wide_host["apartments"][0]
    monkeypatch.setattr(mail, "enqueue", lambda **kw: 1)
    oid = int(db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (aid,))["owner_user_id"])
    booking_site.save_settings(aid, {"nightly_price_czk": 2000, "cleaning_fee_czk": 500,
                                     "cancellation_policy": "moderate"})
    q = booking_site.quote(aid, "2027-06-10", "2027-06-13", 2)
    hold = booking_checkout.hold_dates(aid, "2027-06-10", "2027-06-13")
    row = booking_site.create_pending(aid, oid, q, guest_name="Jana Novak",
                                      guest_email="jana@example.test", lang="cs", hold_id=hold)
    booking_site.attach_session(row["id"], f"cs_host_browser_{row['id']}")
    booking_webhook.handle({"id": f"evt_host_browser_{row['id']}", "type": "checkout.session.completed",
                            "data": {"object": {
                                "id": f"cs_host_browser_{row['id']}", "payment_status": "paid",
                                "payment_intent": f"pi_host_browser_{row['id']}",
                                "metadata": {"site_booking_id": str(row["id"])}}}})
    try:
        yield aid
    finally:
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (aid,))


@pytest.mark.parametrize("width", (390, 1280))
def test_host_bookings_section_fits(paid_booking, wide_host, wide_base, width):
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the booking site browser test")
        context, page = _open(browser, wide_host, wide_base, width)
        assert "Rezervace z webu" in page.inner_text("body"), f"bookings section missing at {width}px"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), \
            f"page scrolls sideways at {width}px"
        findings = page.evaluate(GUARD, width < 1024)
        assert not findings, f"layout guard at {width}px: {findings[:10]}"
        if width == 390:
            danger = page.locator("form[action$='/booking-site/cancel'] button").first
            assert danger.bounding_box()["height"] >= 44, "host cancel button shorter than 44px at 390px"
            HOST_SHOT_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(HOST_SHOT_DIR / "host-390.png"), full_page=True)
        context.close()
        browser.close()


def _open(browser, wide_host, wide_base, width: int):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wide_host["cookie"],
                          "url": wide_base + "/"}])
    page = context.new_page()
    path = f"/apartments/{wide_host['apartments'][0]}/booking-site?lang=cs"
    response = page.goto(f"{wide_base}{path}")
    assert response and response.status < 400, f"booking-site/{width}: HTTP {response.status if response else 'none'}"
    _wait_for_host_layout(page)
    _dismiss_optional_security_prompt(page)
    return context, page


@pytest.mark.parametrize("width", (390, 1280))
def test_booking_site_fits_and_has_one_primary_per_form(wide_host, wide_base, width):
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the booking site browser test")
        context, page = _open(browser, wide_host, wide_base, width)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), \
            f"page scrolls sideways at {width}px"
        findings = page.evaluate(GUARD, width < 1024)
        assert not findings, f"layout guard at {width}px: {findings[:10]}"
        assert not page.evaluate(PRIMARY_PER_FORM_JS), "more than one ui-btn-primary in a form"
        if width == 390:
            assert not page.evaluate(SMALL_TARGETS_JS), "controls shorter than 44px at 390px"
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT_DIR / "booking-site-390.png"), full_page=True)
        context.close()
        browser.close()
