"""0709: v2 Overview screenshots at 1280 and 390 px, and no sideways page scroll at 390 px."""
from __future__ import annotations

import os

from app import auth
from tests.test_host_quiet_dashboard_browser import (  # the quiet overview's fixtures and helpers
    _launch,
    _open,
    base,
    dashboard_host,
    dashboard_rich_host,
    sync_api,
)

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]


def test_v2_overview_screenshots_cs(dashboard_rich_host, base, tmp_path):
    """Writes the report screenshots to UBYHOST_SHOTS_V2 when set, else to a temp folder."""
    out = os.environ.get("UBYHOST_SHOTS_V2") or str(tmp_path)
    os.makedirs(out, exist_ok=True)
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in (1280, 390):
            context, page, errors = _open(browser, base, cookie, "cs", width)
            assert not errors, errors
            if width == 390:
                scroll = page.evaluate("document.documentElement.scrollWidth")
                assert scroll <= 390, f"page scrolls sideways at 390 px: {scroll}"
            page.screenshot(path=os.path.join(out, f"overview-cs-{width}.png"), full_page=True)
            context.close()
        browser.close()
