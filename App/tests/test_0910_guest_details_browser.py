"""0910 Parts A and B: guest birth date, nationality and document number on the stay page and the stay-fee detail.

Screenshots: UBYHOST_SHOTS_DIR=<dir> writes calendar-0910-stay-<width>.png and calendar-0910-fee-<width>.png.
"""
from __future__ import annotations

from app import auth
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_0766_phone_stays_browser import _cookie
from tests.test_dashboard_calendar_browser import shot
from tests.test_host_quiet_dashboard_browser import _launch, base, dashboard_host, dashboard_rich_host, sync_api  # noqa: F401
from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401

__all__ = ["base", "dashboard_rich_host", "host"]

_BOX_JS = """(el) => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }"""


def test_0910_stay_page_shows_guest_details(base, dashboard_rich_host):
    for width in (390, 768, 1280):
        with sync_api.sync_playwright() as playwright:
            browser = _launch(playwright)
            context, page = _open_app(browser, base, _cookie(dashboard_rich_host),
                                      f"/reservations/{dashboard_rich_host['ready']}", width)
            line = page.locator("[data-guest-id-line]:visible").first
            assert line.count() == 1
            text = line.inner_text()
            assert "01.01.1990" in text, (width, text)
            assert "P1234567" in text, (width, text)
            font_px = float(line.evaluate("el => parseFloat(getComputedStyle(el).fontSize)"))
            assert font_px >= 13, (width, font_px)
            name = line.evaluate("el => el.parentElement.querySelector('b').getBoundingClientRect().bottom")
            top = line.evaluate("el => el.getBoundingClientRect().top")
            assert top >= name - 1, (width, name, top)
            shot(page, f"0910-stay-{width}")
            context.close()
            browser.close()


def test_0910_fee_page_shows_guest_facts(base, host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Detail Shot Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{"first_name": "Adult"}, {"first_name": "Kid", "birth_date": "01012015"}])
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    for width in (390, 768, 1280):
        with sync_api.sync_playwright() as playwright:
            browser = _launch(playwright)
            context, page = _open_app(browser, base, cookie, f"/stay-fees/{apartment_id}?month=2026-08", width)
            facts = page.locator("[data-fee-guest-facts]:visible").first
            assert facts.count() == 1
            assert "Age 36 at check-in" in facts.inner_text(), (width, facts.inner_text())
            shot(page, f"0910-fee-{width}")
            context.close()
            browser.close()
