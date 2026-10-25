"""0402: the STATE column of every guide topic table shares one right edge at desktop width."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures)
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0402"
EDGES = """(selector) => [...document.querySelectorAll(selector)]
  .map(e => Math.round(e.getBoundingClientRect().right))"""


@pytest.mark.parametrize("width", [1280, 390])
def test_guide_state_column_lines_up(wide_host, wide_base, width):  # noqa: F811
    apartment_id = wide_host["apartments"][0]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=2)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/"}])
        page = context.new_page()
        page.goto(f"{wide_base}/apartments/{apartment_id}/guide?lang=en")
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        if width >= 1024:
            # th and td have different side padding, so headers and badges are checked as two groups.
            for selector in ("[id^=topic-] td[data-card=badge] .ui-badge", "[id^=topic-] th:last-child"):
                edges = page.evaluate(EDGES, selector)
                assert len(edges) > 4
                assert max(edges) - min(edges) <= 2, (selector, edges)
        page.locator("[id^=topic-]").nth(1).scroll_into_view_if_needed()
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"guide-table-{width}.png"))
        context.close()
        browser.close()
