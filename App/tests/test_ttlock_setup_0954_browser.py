"""0954 browser: the Smart lock status block at 390, 768 and 1280 px, in each state."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import db
from tests.browser_support import chromium_launch_kwargs
from tests.property_host_fixture import LOCK, host  # noqa: F401
from tests.test_property_navigation_browser import _context, base  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0954"
WIDTHS = (390, 768, 1280)
STATES = ("on", "off", "offline", "times")


def _set_state(host, state):
    """The fixture host is 'on'; change the stored values for each state."""
    apartment, owner = host["apartment"], host["owner"]
    base_fields = {"lock_provider": "ttlock", "lock_id": LOCK["lock_id"], "checkin_hour": 15, "checkout_hour": 10}
    if state == "off":
        base_fields["lock_provider"] = None
    if state == "times":
        base_fields["checkin_hour"] = None
    db.update("apartment", apartment, base_fields)
    status = "reauth_needed" if state == "offline" else "ok"
    db.execute("UPDATE lock_account SET status = ? WHERE owner_user_id = ?", (status, owner))


def _restore(host):
    db.update("apartment", host["apartment"], {"lock_provider": "ttlock", "lock_id": LOCK["lock_id"], "checkin_hour": 15, "checkout_hour": 10})
    db.execute("UPDATE lock_account SET status = 'ok' WHERE owner_user_id = ?", (host["owner"],))


def _probe(page, token):
    """The computed colour of a token, read from a probe element (no hard-coded rgb)."""
    return page.evaluate(
        """(token) => { const p = document.createElement('i'); p.style.color = 'var(' + token + ')';
           document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; }""",
        token,
    )


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("state", STATES)
def test_status_block_fits_and_shows_its_state(base, host, state, width):  # noqa: F811
    SHOTS.mkdir(parents=True, exist_ok=True)
    _set_state(host, state)
    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            page = _context(browser, base, host).new_page()
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(f"{base}/apartments/{host['apartment']}?view=settings&section=lock&lang=en")
            section = page.locator("#sec-lock")
            section.locator(".lock-state").wait_for(state="visible", timeout=5000)
            # 0987 owner: connected + codes off shows Turn on (#lock-connected-off). Fixture has account+locks.
            block = section.locator("#lock-connected-off")
            assert block.get_attribute("data-state") == state
            # No horizontal page scroll at this width.
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            assert overflow <= 0, overflow
            box = block.bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
            border = page.evaluate("() => getComputedStyle(document.querySelector('.lock-state')).borderTopColor")
            if state == "on":
                assert border == _probe(page, "--green")
            elif state == "off":
                assert border != _probe(page, "--green")
            primary = block.locator("form button, a.ui-btn").first
            assert primary.is_visible()
            tag = primary.evaluate("el => el.tagName")
            assert tag in ("BUTTON", "A"), tag
            if width < 1024:
                assert primary.bounding_box()["height"] >= 44
            # The time labels carry the red star.
            stars = section.locator('label[for="lock_checkin_hour"] .req-star, label[for="lock_checkout_hour"] .req-star')
            assert stars.count() == 2
            assert stars.first.evaluate("s => getComputedStyle(s).color") == _probe(page, "--red")
            SHOTS.joinpath(f"{state}-{width}.png").write_bytes(section.screenshot())
            browser.close()
    finally:
        _restore(host)
