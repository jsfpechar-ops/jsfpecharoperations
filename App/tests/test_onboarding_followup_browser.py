"""0102: quiet row actions, uniform hover and aligned host detail navigation."""
from __future__ import annotations

import pytest

from app import auth, db, host_i18n, property_setup
from tests.test_host_stay_actions_browser import (  # noqa: F401 (shared fixtures)
    _browser, stay_actions_base, stay_actions_host, sync_api,
)
from tests.test_onboarding_wizard_browser import (  # noqa: F401 (shared fixtures)
    _create, _shot, base_url as wizard_base, host as wizard_host,
)


def _t(lang, key):
    return host_i18n.translate(lang, key)


def _ready(page):
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()


def _fits(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [360, 390, 1440, 1920, 2048])
def test_rows_hover_as_one_surface_and_use_compact_menus(stay_actions_host, stay_actions_base, lang, width):
    host, base = stay_actions_host, stay_actions_base
    stay_id = host["ids"]["waiting"]
    db.update("reservation", stay_id, {"reservation_url": "https://www.airbnb.com/hosting/reservations/details/SYNTHETIC"})
    with sync_api.sync_playwright() as p:
        browser = _browser(p)
        context = browser.new_context(viewport={"width": width, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/reservations?range=all&lang={lang}")
        _ready(page)
        row = page.locator(f'tr[data-href^="/reservations/{stay_id}?"]')
        assert row.locator(".stay-portal-link").count() == 0
        assert row.locator(".row-open").count() == 1  # 0252: visible Open cue
        assert row.locator('.row-actions > button[data-copy]').count() == 0
        assert row.locator('button[data-copy]').is_hidden()
        row.scroll_into_view_if_needed()
        before = row.bounding_box()
        target = row if width < 1024 else row.locator("td").first
        initial = target.evaluate("el => getComputedStyle(el).backgroundColor")
        row.hover()
        page.wait_for_timeout(180)
        assert target.evaluate("el => getComputedStyle(el).backgroundColor") != initial
        if width >= 1024:
            cell_colours = row.locator("td").evaluate_all("cells => cells.map(el => getComputedStyle(el).backgroundColor)")
            assert len(set(cell_colours)) == 1 and cell_colours[0] != initial, cell_colours
        else:
            assert row.locator("td").evaluate_all("cells => cells.every(el => getComputedStyle(el).backgroundColor === 'rgba(0, 0, 0, 0)')")
        after = row.bounding_box()
        assert all(abs(before[key] - after[key]) <= 1 for key in ("x", "y", "width", "height")), (before, after)
        _fits(page)
        _shot(page, f"36-uniform-stays-hover-{lang}-{width}.png")

        trigger = row.locator(".row-menu-trigger")
        trigger.click()
        menu = page.locator(".row-menu-panel.is-open")
        assert menu.get_by_role("menuitem", name=_t(lang, "host.copy_guest_form_link"), exact=True).is_visible()
        menu.get_by_role("menuitem", name=_t(lang, "common.open"), exact=True).click()
        page.wait_for_url(f"**/reservations/{stay_id}?**")
        _fits(page)
        # Every direct child retains the same centered content lane on wide screens.
        boxes = [page.locator(selector).bounding_box() for selector in (".ui-ph", ".stay-property-line", ".stay-jump", "#now")]
        assert all(boxes)
        assert max(box["x"] for box in boxes) - min(box["x"] for box in boxes) <= 1
        assert max(box["x"] + box["width"] for box in boxes) - min(box["x"] + box["width"] for box in boxes) <= 1
        assert page.locator('#now > .stay-command-main > .stay-command-actions > button[data-copy]').count() == 0
        _shot(page, f"37-centered-stay-detail-{lang}-{width}.png")

        page.goto(f"{base}/reservations?range=all&lang={lang}")

        _ready(page)
        row = page.locator(f'tr[data-href^="/reservations/{stay_id}?"]')
        row.focus()
        page.keyboard.press("Enter")
        page.wait_for_url(f"**/reservations/{stay_id}?**")
        page.goto(f"{base}/reservations?range=all&lang={lang}")
        _ready(page)
        page.locator(f'tr[data-href^="/reservations/{stay_id}?"] .stay-col-guests').click()
        page.wait_for_url(f"**/reservations/{stay_id}?**")

        page.goto(f"{base}/apartments?lang={lang}")

        _ready(page)
        property_row = page.locator(".properties-table tbody .clickable-row").first
        assert property_row.locator(".row-actions > a.btn").count() == 0
        property_row.locator(".row-menu-trigger").click()
        menu = page.locator(".row-menu-panel.is-open")
        assert menu.get_by_role("menuitem", name=_t(lang, "common.open"), exact=True).is_visible()
        page.keyboard.press("Escape")
        property_row.locator(".row-primary-link").click()
        page.wait_for_url("**/apartments/*")

        page.goto(f"{base}/?lang={lang}")

        _ready(page)
        dashboard_row = page.locator(".dashboard-row").first
        assert dashboard_row.is_visible()
        assert dashboard_row.locator(".dashboard-open").count() == 0
        dashboard_row.locator(".row-menu-trigger").click()
        menu = page.locator(".row-menu-panel.is-open")
        assert menu.get_by_role("menuitem", name=_t(lang, "common.open"), exact=True).is_visible()
        page.keyboard.press("Escape")
        _fits(page)

        if width >= 1440:
            page.evaluate("document.body.classList.add('sidebar-collapsed')")
            account = page.locator("[data-host-account] > summary")
            avatar = account.locator(".sidebar-user-avatar")
            assert account.get_attribute("aria-label")
            assert "⌃" not in account.inner_text()
            center = lambda box: box["x"] + box["width"] / 2
            assert abs(center(account.bounding_box()) - center(avatar.bounding_box())) <= 1
            assert avatar.locator("..").evaluate("el => el.scrollWidth <= el.clientWidth")
            account.focus()
            page.keyboard.press("Enter")
            assert page.locator("[data-host-account]").evaluate("el => el.open")
            assert page.locator(".host-account-menu").is_visible()
            _shot(page, f"38-centered-account-{lang}-{width}.png")
            page.keyboard.press("Escape")
            assert not page.locator("[data-host-account]").evaluate("el => el.open")
            assert account.evaluate("el => document.activeElement === el")
        context.close()
        browser.close()


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [390, 1280])
def test_current_property_name_demo_label_and_distinct_setup_status(wizard_host, wizard_base, lang, width):
    flat = _create(wizard_host)
    apartment_id = flat["id"]
    current_name = "Updated Garden & Loft"
    db.update("apartment", apartment_id, {"internal_name": current_name})
    property_setup.mark(apartment_id, "police", "waiting")
    property_setup.mark(apartment_id, "calendar", "skipped")
    property_setup.mark(apartment_id, "guest_link", "done")
    property_setup.mark(apartment_id, "try_it", "skipped")
    with sync_api.sync_playwright() as p:
        browser = _browser(p)
        context = browser.new_context(viewport={"width": width, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wizard_host["client"].cookies.get(auth.SESSION_COOKIE), "url": wizard_base + "/"}])
        page = context.new_page()
        base = f"{wizard_base}/apartments/{apartment_id}"
        page.goto(f"{base}/setup/guest_link?lang={lang}")
        _ready(page)
        message = page.locator("#wizard-guest-message").input_value()
        assert current_name in message and "[PROPERTY_NAME]" not in message
        assert "%(" not in message
        page.goto(f"{base}/setup/try_it?lang={lang}")
        _ready(page)
        assert current_name in page.locator(".setup-demo-bubble").inner_text()
        assert page.locator(".setup-demo-disclaimer").inner_text() == _t(lang, "wizard.try_it.model_note")
        assert page.locator("#demo-message-heading .ui-badge").is_visible()
        _shot(page, f"39-labeled-demo-message-{lang}-{width}.png")
        property_setup.finish(apartment_id)
        page.goto(f"{base}?view=overview&lang={lang}")
        _ready(page)
        status = page.locator("[data-setup-status]")
        assert status.is_visible()
        assert status.locator(".setup-status-tile").count() == 8
        assert status.locator(".host-property-card").count() == 0
        assert status.locator(".setup-status-tile a").count() == 0
        assert not status.locator(".setup-readiness-help").evaluate("el => el.open")
        police = status.locator('[data-overview-setup-step="police"]')
        assert police.locator('[data-tone="amber"]').is_visible()
        assert police.locator('[data-tone="green"]').count() == 0
        tile = status.locator(".setup-status-tile").first
        color = tile.evaluate("el => getComputedStyle(el).backgroundColor")
        tile.hover()
        assert tile.evaluate("el => getComputedStyle(el).backgroundColor") == color
        assert tile.evaluate("el => getComputedStyle(el).cursor") == "default"
        assert page.locator(".host-property-grid > a.host-property-card").count() >= 5
        status.locator(".setup-readiness-help > summary").click()
        assert status.locator(".readiness").is_visible()
        status.locator(".setup-readiness-help > summary").click()
        _fits(page)
        _shot(page, f"40-overview-status-tiles-{lang}-{width}.png")
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [390, 1920])
def test_native_record_links_still_work_without_javascript(stay_actions_host, stay_actions_base, width):
    host, base = stay_actions_host, stay_actions_base
    stay_id = host["ids"]["waiting"]
    with sync_api.sync_playwright() as p:
        browser = _browser(p)
        context = browser.new_context(viewport={"width": width, "height": 1000}, java_script_enabled=False)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}/reservations?range=all&lang=en")
        _ready(page)
        page.locator(f'tr[data-href^="/reservations/{stay_id}?"] .row-primary-link').click()
        page.wait_for_url(f"**/reservations/{stay_id}?**")
        page.goto(f"{base}/apartments?lang=en")
        _ready(page)
        page.locator(".properties-table .row-primary-link").first.click()
        page.wait_for_url("**/apartments/*")
        context.close()
        browser.close()
