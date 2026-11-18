"""1857 Go-only: phone Show more JS append (run with UBYHOST_GO_PATHS=/reservations)."""
from __future__ import annotations

import pytest

from tests.go_stack import go_paths_enabled
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_1857_stays_more_browser import (  # noqa: F401
    _cookie,
    stays_more_host,
)
from tests.test_host_quiet_dashboard_browser import (  # noqa: F401
    _launch,
    base,
    sync_api,
)

pytestmark = pytest.mark.skipif(
    not go_paths_enabled(),
    reason="UBYHOST_GO_PATHS must include /reservations",
)


def test_phone_show_more_appends_rows(base, stays_more_host):
    client, _apartment_id = stays_more_host
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, _cookie(client), "/reservations?range=all", 390)
        rows = page.locator(".stays-desk tbody tr")
        assert rows.count() == 5
        more = page.locator("[data-stays-more] a")
        assert more.count() == 1, "expected Go GET /reservations (data-stays-more)"
        more.click()
        page.wait_for_timeout(400)
        assert rows.count() == 6
        assert page.locator("[data-stays-more]").count() == 0
        assert "page=2" in page.url
        assert page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2")
        context.close()
        browser.close()