"""0995: /apartments/<id>#sec-messages opens and scrolls to Guest experience.

Also checks that the Guest link card keeps its label and Copy link button on one row at 1280 px.
"""
from __future__ import annotations

import os

import pytest

from app import auth
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_property_controls_browser import base, host  # noqa: F401  (shared fixtures)

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")


def _session_cookie(host):
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie


def test_property_deeplink_opens_guest_experience_and_card_row(host, base):
    url = f"{base}/apartments/{host['apartment']}?lang=en#sec-messages"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _session_cookie(host), "url": base + "/"}])
            page = context.new_page()
            page.goto(url, wait_until="load")
            page.wait_for_function(
                "() => { const d = document.getElementById('sec-messages'); return d && d.open; }"
            )
            # The section summary must sit inside the viewport after the deep link scroll.
            summary = page.locator("#sec-messages > summary").first.bounding_box()
            assert summary is not None
            assert 0 <= summary["y"] <= 900, summary

            card = page.locator(".prop-strip div.sc.sc-link")
            assert card.count() == 1
            label = card.locator("b").first.bounding_box()
            copy = card.locator(".sc-actions .btn").first.bounding_box()
            assert label is not None and copy is not None
            assert abs(label["y"] - copy["y"]) <= 60, (label, copy)
        finally:
            browser.close()
