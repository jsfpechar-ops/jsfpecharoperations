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
                    # One ordered page: next step, guests, reporting, settings; nothing folded.
                    order = page.evaluate(
                        "['now','guests','reports','stay-quick-edit'].map(i => document.getElementById(i).getBoundingClientRect().top)"
                    )
                    assert order == sorted(order), order
                    assert page.locator("#stay-quick-edit").evaluate("e => e.tagName") == "SECTION"
                    assert page.locator("nav.stay-jump a").count() == 4
                    # MASTER 5.2: tabs scroll horizontally on phone and never wrap, so the nav stays
                    # inside the lane and every link sits inside the nav's scroll extent.
                    nav_box = page.locator("nav.stay-jump").bounding_box()
                    assert nav_box and nav_box["x"] >= -1 and nav_box["x"] + nav_box["width"] <= width + 1, nav_box
                    extents = page.evaluate(
                        "(() => { const nav = document.querySelector('nav.stay-jump'); const n = nav.getBoundingClientRect();"
                        " return [...nav.querySelectorAll('a')].map(a => { const b = a.getBoundingClientRect();"
                        " return [b.left - n.left + nav.scrollLeft, b.right - n.left + nav.scrollLeft, nav.scrollWidth, getComputedStyle(nav).overflowX]; }); })()"
                    )
                    # 0252: the jump tabs wrap on phone instead of scrolling sideways.
                    assert all(-1 <= left and right <= scroll_w + 1 for left, right, scroll_w, overflow in extents), extents
                    if key != "incomplete":
                        # One fact grid (0179), visible on the page itself.
                        assert page.locator(".guest-card .guest-facts").count() == 1
                        text = page.locator(".guest-card").first.inner_text()
                        assert "P-" in text and "1990" in text
                        for dd in page.locator(".guest-card dd").all():
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
