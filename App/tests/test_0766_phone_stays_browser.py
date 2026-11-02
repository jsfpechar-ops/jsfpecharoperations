"""0766: the phone stays list shows each stay's dates with weekdays; the stay page hides an empty CTA bar."""
from __future__ import annotations

from app import auth, claim
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_host_quiet_dashboard_browser import _launch, base, dashboard_host, dashboard_rich_host, sync_api

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _cookie(host):
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie


def test_phone_stay_card_without_name_shows_weekday_and_check_in(base, dashboard_rich_host):
    today = claim.prague_today()
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, _cookie(dashboard_rich_host), "/reservations", 390)
        card = page.locator(f'a.card.stay[href^="/reservations/{dashboard_rich_host["waiting"]}?"]')
        assert card.count() == 1
        text = card.locator(".in b").inner_text()
        assert f"{WEEKDAYS[today.weekday()]} {today.day}" in text, text
        context.close()
        browser.close()


def test_phone_stay_page_without_cta_hides_the_bar(base, dashboard_rich_host):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, _cookie(dashboard_rich_host), f"/reservations/{dashboard_rich_host['waiting']}", 390)
        assert not page.locator(".host-stay-detail .stay-head-cta").is_visible()
        context.close()
        browser.close()


def test_phone_stay_page_with_cta_keeps_the_bar(base, dashboard_rich_host):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, _cookie(dashboard_rich_host), f"/reservations/{dashboard_rich_host['ready']}", 390)
        assert page.locator(".host-stay-detail .stay-head-cta").is_visible()
        context.close()
        browser.close()
