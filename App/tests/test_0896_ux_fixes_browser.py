"""Brief 0896: notification X in the corner, plain help "?", profile menu in the sidebar corner, no Add cleaning on Overview."""

import os
import secrets
from pathlib import Path

import pytest

from app import alerts, auth, db
from tests.conftest import mark_security_prompt_seen
from tests.browser_support import chromium_launch_kwargs
from tests.test_0705_v2_shell_browser import _sync_playwright
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0896"
WIDTHS = [320, 390, 768, 1024, 1280, 1440, 1920]


def _account(admin=False):
    username = f"ux{secrets.token_hex(3)}"
    owner = mark_security_prompt_seen(auth.create_account(f"{username}@example.test", "Ux", role="admin" if admin else "host", username=username))
    entity = db.insert("legal_entity", {"name": "Ux s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {"internal_name": "Ux flat", "owner_user_id": owner, "legal_entity_id": entity,
                            "permalink_token": f"ux{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    for kind, level, message in (("apartment_setup", "warning", "Ux flat: police setup is not finished."),
                                 ("police_overdue", "critical", "Ux flat: report is overdue by a very long time so the text wraps")):
        alerts.raise_alert(level, kind, message, owner_user_id=owner, dedupe_key=f"{kind}:{username}")
    return username


def _page(playwright, base, width, username):
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
            raise
        pytest.skip(f"Chromium is not available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    return browser, context.new_page()


def _shot(page, name, width):
    if os.environ.get("UBYHOST_TASK_SHOTS") == "1" and width in (390, 768, 1280):
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"{name}-{width}.png"))


@pytest.mark.parametrize("width", WIDTHS)
def test_notification_x_sits_in_the_top_right_corner_of_every_bubble(base, width):
    username = _account()
    with _sync_playwright().sync_playwright() as playwright:
        browser, page = _page(playwright, base, width, username)
        page.goto(base + "/reservations?lang=en")
        page.wait_for_selector("[data-notification]", state="attached", timeout=30000)
        bubbles = page.locator("[data-notification]")
        assert bubbles.count() >= 2
        for i in range(bubbles.count()):
            bubble = bubbles.nth(i)
            box = bubble.bounding_box()
            x = bubble.locator("[data-notification-dismiss] button").bounding_box()
            assert x["x"] + x["width"] <= box["x"] + box["width"] + 0.5
            assert box["x"] + box["width"] - (x["x"] + x["width"]) <= 12, (i, box, x)
            assert x["y"] - box["y"] <= 12, (i, box, x)
            assert x["width"] >= 44 and x["height"] >= 44
            text = bubble.locator(".notification-link .grow").bounding_box()
            assert text["x"] + text["width"] <= x["x"] + 0.5, "text runs under the X"
            assert text["x"] + text["width"] <= box["x"] + box["width"]
        for i in range(bubbles.count() - 1):  # bubbles never overlap and keep 12 px
            a, b = bubbles.nth(i).bounding_box(), bubbles.nth(i + 1).bounding_box()
            assert b["y"] - (a["y"] + a["height"]) >= 11.5
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        _shot(page, "notifications", width)
        browser.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_page_help_is_a_plain_round_question_mark_without_chevron(base, width):
    username = _account()
    with _sync_playwright().sync_playwright() as playwright:
        browser, page = _page(playwright, base, width, username)
        page.goto(base + "/reservations?lang=en")
        page.wait_for_selector(".page-help-btn", state="attached", timeout=30000)
        info = page.evaluate("""() => { const b = document.querySelector('.page-help-btn'); const d = b.querySelector('.page-help-dot'); const dr = d.getBoundingClientRect(); const r = b.getBoundingClientRect();
            const row = b.closest('.stays-title-row') || b.closest('.props-title-row'); const h1 = row && row.querySelector('h1');
            const hr = h1 ? h1.getBoundingClientRect() : {right: 0};
            return {after: getComputedStyle(b, '::after').content, w: r.width, dot: dr.width, right: r.right, dright: dr.right, h1: hr.right}; }""")
        assert info["after"] in ("none", "normal"), info
        assert info["dot"] <= 20 and info["w"] <= 44
        _shot(page, "help", width)
        browser.close()


@pytest.mark.parametrize("width", [1024, 1280, 1440, 1920])
@pytest.mark.parametrize("admin", [False, True])
def test_profile_bubble_opens_menu_with_settings_funnel_and_admin(base, width, admin):
    username = _account(admin=admin)
    with _sync_playwright().sync_playwright() as playwright:
        browser, page = _page(playwright, base, width, username)
        page.goto(base + "/?lang=en")
        page.wait_for_selector(".side .me-menu", timeout=30000)
        page.wait_for_load_state("networkidle")
        assert page.locator(".side-nav a[href='/settings']").count() == 0
        assert page.locator(".me-menu-list").is_hidden()
        page.click(".me-menu > summary")
        page.wait_for_selector(".me-menu-list", state="visible", timeout=3000)
        for href, expected in (("/settings", True), ("/admin/fakturace#funnel", admin), ("/admin", admin), ("/guide", True)):
            assert (page.locator(f".me-menu-list a[href='{href}']").count() == 1) == expected, href
        list_box = page.locator(".me-menu-list").bounding_box()
        assert list_box["x"] >= 0 and list_box["y"] >= 0 and list_box["x"] + list_box["width"] <= width
        items = page.locator(".me-menu-list > a, .me-menu-list button").all()
        boxes = [i.bounding_box() for i in items]
        for a, b in zip(boxes, boxes[1:]):
            assert b["y"] >= a["y"] + a["height"] - 0.5
        if admin:
            _shot(page, "profile-menu", width)
        page.click("main")
        page.wait_for_selector(".me-menu-list", state="hidden", timeout=3000)
        page.click(".me-menu > summary")
        page.wait_for_selector(".me-menu-list", state="visible", timeout=3000)
        page.click(".me-menu-list a[href='/settings']")
        page.wait_for_url("**/settings*")
        browser.close()


def test_overview_has_no_add_cleaning_link(base):
    username = _account()
    with _sync_playwright().sync_playwright() as playwright:
        browser, page = _page(playwright, base, 1280, username)
        page.goto(base + "/?lang=en")
        page.wait_for_selector("h1", timeout=30000)
        assert page.locator("a[href='/cleaning/new']").count() == 0
        browser.close()
