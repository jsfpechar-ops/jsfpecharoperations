"""Opening Havel from the sidebar must not blank the page behind the sheet.

Regression: skeleton.js loads before shell.js, so its click listener saw the
launcher link as a plain navigation and armed the page skeleton. The sheet
opened over a blank page until the 15 s safety timer ran out.
"""
from __future__ import annotations

import os

import pytest

from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_submission_retry_cap import host as host  # noqa: F401

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")


def test_havel_launcher_does_not_arm_the_navigation_skeleton(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        page.locator("#havel-sheet[open]").wait_for()
        page.wait_for_timeout(700)
        skeleton = page.locator("[data-page-skeleton]")
        sync_api.expect(skeleton).to_be_hidden()
        page.keyboard.press("Escape")
        page.wait_for_timeout(700)
        sync_api.expect(skeleton).to_be_hidden()
        sync_api.expect(page.locator("main .ui-page").first).to_be_visible()
        assert page.url == origin[0] + "/"
        browser.close()
