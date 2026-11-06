"""0080: stay detail groups, saved guest facts and wrapping at phone and desktop widths."""
from __future__ import annotations

import os
from pathlib import Path

from app import auth
from tests.test_host_stay_actions_browser import (  # noqa: F401 (fixtures)
    REQUIRE_BROWSER,
    _browser,
    stay_actions_base,
    stay_actions_host,
    sync_api,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0080-evidence"


def test_stay_detail_groups_facts_and_wraps(stay_actions_host, stay_actions_base):
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    ids = stay_actions_host["ids"]
    capture = os.environ.get("UBYHOST_CAPTURE_0080") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        page = context.new_page()
        for locale in ("en", "cs"):
            for width in (360, 390, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                for key in ("ready", "failed", "incomplete"):
                    page.goto(f"{stay_actions_base}/reservations/{ids[key]}?lang={locale}")
                    page.wait_for_load_state("networkidle")
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (key, width)
                    # One ordered page, mockup order: guests, reporting, settings; nothing folded.
                    # below 1024 the settings card is hidden (compact phone rule, still on desktop)
                    order_ids = ['guests', 'reports', 'stay-quick-edit'] if width >= 1024 else ['guests', 'reports']
                    order = page.evaluate(
                        "ids => ids.map(i => document.getElementById(i).getBoundingClientRect().top)", order_ids
                    )
                    assert order == sorted(order), order
                    if width < 1024:
                        assert page.locator("#stay-quick-edit").is_hidden()
                    assert page.locator("#stay-quick-edit").evaluate("e => e.tagName") == "DETAILS"
                    # 0525 standing rule: the jump tabs were removed in 0524, so the nav geometry
                    # checks no longer apply; the page must have none.
                    assert page.locator("nav.stay-jump a").count() == 0
                    if key != "incomplete":
                        # One fact grid (0179), visible on the page itself.
                        assert page.locator("#guests .guest-table:visible, #guests .guest-list:visible").count() == 1
                        text = page.locator("#guests .guest-table:visible, #guests .guest-list:visible").first.inner_text()
                        assert "SAMPLE" in text.upper()  # 0529: the table shows name, document type and state; the old fact grid is gone
                        for dd in page.locator("#guests .guest-list:visible .row, #guests .guest-table:visible td").all():
                            box = dd.bounding_box()
                            assert box["x"] + box["width"] <= width + 1
                    if key == "ready":
                        form = page.locator(f'form[action="/reservations/{ids[key]}/submit"]')
                        assert form.count() == 1
                        assert form.locator('input[name="_csrf"]').count() == 1
                        assert form.locator('input[name="return_to"]').count() == 1
                    if capture and key == "ready":
                        page.screenshot(path=str(EVIDENCE / f"stay-detail-{locale}-{width}.png"), full_page=True)
        context.close()
        browser.close()


def test_add_guest_and_invoice_forms_keep_the_v2_host_shell(stay_actions_host, stay_actions_base):
    """0961: guest admin + detailed invoice stay on the v2 shell (sidebar, font, content lane)."""
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    stay = stay_actions_host["ids"]["ready"]
    urls = {
        "stay": f"/reservations/{stay}",
        "guest": f"/reservations/{stay}/guests/new",
        "invoice": f"/invoices/new?reservation_id={stay}",
    }
    probe = """(() => ({v2: document.body.classList.contains('v2'),
        sidebar: !!document.querySelector('#app-sidebar'),
        font: getComputedStyle(document.body).fontFamily,
        left: Math.round(document.querySelector('#main-content').getBoundingClientRect().left),
        path: location.pathname}))()"""
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        page = context.new_page()
        for locale in ("en", "cs"):
            for width in (390, 768, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                seen = {}
                for key, url in urls.items():
                    page.goto(f"{stay_actions_base}{url}{'&' if '?' in url else '?'}lang={locale}")
                    page.wait_for_load_state("networkidle")
                    seen[key] = page.evaluate(probe)
                    assert seen[key]["path"] == url.split("?")[0], (key, width, seen[key])
                    assert seen[key]["v2"] and seen[key]["sidebar"], (key, width, locale)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (key, width)
                for key in ("guest", "invoice"):
                    assert seen[key]["font"] == seen["stay"]["font"], (key, width)
                    assert seen[key]["left"] == seen["stay"]["left"], (key, width)
        browser.close()
