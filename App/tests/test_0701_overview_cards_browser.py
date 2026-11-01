"""0701: Overview at computer width: "What needs you" as cards, and the simple Today table."""
from __future__ import annotations

import os

from app import auth
from tests.test_host_quiet_dashboard_browser import (  # the quiet overview's fixtures and helpers
    CARD_JS,
    _check_card,
    _launch,
    _open,
    base,
    dashboard_host,
    dashboard_rich_host,
    sync_api,
)

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]


def test_needs_you_lines_sit_side_by_side_as_cards_at_1280(dashboard_rich_host, base):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, errors = _open(browser, base, cookie, "en", 1280)
        assert not errors, errors
        items = page.locator(".needs-you-list > .needs-you-item")
        assert items.count() >= 2
        first, second = items.nth(0).bounding_box(), items.nth(1).bounding_box()
        assert abs(first["y"] - second["y"]) <= 1, (first, second)
        assert second["x"] >= first["x"] + first["width"] - 1, (first, second)
        _check_card(page.evaluate(CARD_JS), 1280, "cards/en/1280")
        browser.close()


def test_needs_you_lines_stack_on_a_phone(dashboard_rich_host, base):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, errors = _open(browser, base, cookie, "en", 390)
        assert not errors, errors
        items = page.locator(".needs-you-list > .needs-you-item")
        assert items.count() >= 2
        first, second = items.nth(0).bounding_box(), items.nth(1).bounding_box()
        assert abs(first["x"] - second["x"]) <= 1, (first, second)
        assert second["y"] >= first["y"] + first["height"] - 1, (first, second)
        _check_card(page.evaluate(CARD_JS), 390, "cards/en/390")
        browser.close()


def test_today_table_has_four_plain_columns_and_arrival_nights(dashboard_rich_host, base):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, errors = _open(browser, base, cookie, "en", 1280)
        assert not errors, errors
        headers = [text.strip() for text in page.locator(".dashboard-today thead th").all_text_contents()]
        assert headers[:4] == ["Guest", "Property", "Dates", "Status"], headers
        rows = page.locator(".dashboard-today tr.dashboard-row")
        assert rows.count() >= 1
        # The "waiting" stay arrives today and leaves in two nights.
        assert "Check-in · 2 nights" in rows.first.inner_text(), rows.first.inner_text()
        browser.close()


def test_0701_screenshots_cs(dashboard_rich_host, base, tmp_path):
    """Writes the report screenshots to UBYHOST_SHOTS_0701 when set, else to a temp folder."""
    out = os.environ.get("UBYHOST_SHOTS_0701") or str(tmp_path)
    os.makedirs(out, exist_ok=True)
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in (1280, 390):
            context, page, errors = _open(browser, base, cookie, "cs", width)
            assert not errors, errors
            page.screenshot(path=os.path.join(out, f"overview-cs-{width}.png"), full_page=True)
            context.close()
        browser.close()
