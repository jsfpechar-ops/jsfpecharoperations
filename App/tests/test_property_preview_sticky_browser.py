"""0955 step 5a: the property page's Preview aside stays in view while a long page scrolls (1024 px and up).

Uses a property whose setup is unfinished, so the aside holds its cards. Synthetic data only.
Chromium only here; CI also runs webkit (untested locally).
"""
from __future__ import annotations

import pytest

from tests.test_host_unsaved_changes_browser import _page, base, browser, host  # noqa: F401

ASIDE = "aside.preview"
BAR = ".savebar[data-for='property-settings-form']"


@pytest.mark.parametrize("width,height", [(1280, 900), (1440, 900)])
def test_the_preview_aside_stays_in_view_on_desktop(browser, base, host, width, height):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    aside = page.locator(ASIDE)
    assert aside.count() == 1 and aside.is_visible(), "the aside must exist for this property"
    page.evaluate("() => document.querySelectorAll('details.prop-sec').forEach(d => { d.open = true; })")
    page.evaluate("() => window.scrollTo(0, 1200)")
    page.wait_for_timeout(300)
    box = aside.bounding_box()
    assert 0 <= box["y"] <= 120, f"aside top {box['y']} is not within 0-120 px after scrolling 1200 px"
    assert box["y"] + box["height"] <= height + 1 or box["height"] <= height, "aside taller than the viewport"
    assert page.evaluate("() => getComputedStyle(document.querySelector('aside.preview')).position") == "sticky"
    page.context.close()


def test_the_preview_aside_is_static_below_1024(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, 768, 1024)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    assert page.evaluate("() => getComputedStyle(document.querySelector('aside.preview')).position") == "static"
    page.context.close()
