"""0962: the property page has no Preview aside any more (it was 0955's sticky right column).

The six status pills are the only readiness summary and sit above the form at every width.
Synthetic data only. Chromium only here; CI also runs webkit (untested locally).
"""
from __future__ import annotations

import pytest

from tests.test_host_unsaved_changes_browser import _page, base, browser, host  # noqa: F401


@pytest.mark.parametrize("width,height", [(768, 1024), (1280, 900), (1440, 900)])
def test_the_preview_aside_is_gone_and_the_pills_lead(browser, base, host, width, height):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    assert page.locator("aside.preview, .setup-readiness-help, [data-setup-status]").count() == 0
    strip = page.locator("nav.prop-strip")
    assert strip.is_visible() and strip.locator(".sc").count() == 6
    form = page.locator("#property-settings-form").bounding_box()
    assert strip.bounding_box()["y"] < form["y"]
    page.context.close()
