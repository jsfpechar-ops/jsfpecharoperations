"""0541: on a phone the property page opens with the basics section closed."""
from __future__ import annotations

from app import auth
from tests.test_host_quiet_dashboard_browser import _launch, base, dashboard_host, sync_api  # noqa: F401  (0541 browser fixtures)
from tests.test_0710_v2_mockup_match_browser import _open_app, _path, dashboard_rich_host  # noqa: F401  (0541 browser fixtures)
from tests.v2_mockup import PAGES


def test_0541_phone_basics_closed_on_load(base, dashboard_rich_host):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    spec = next(s for s in PAGES if s["name"] == "property")
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, _path(spec, dashboard_rich_host), 390)
        try:
            assert page.locator("#sec-basics[open]").count() == 0
        finally:
            context.close()
            browser.close()
