"""0284: one hover/press state for every clickable row, card and button, and
the "What needs you" lines: buttons line up and the whole line opens its fix."""
from __future__ import annotations

import secrets

import pytest

from fastapi.testclient import TestClient

from app import auth, config, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

@pytest.fixture(autouse=True)
def _own_database(tmp_path):
    """Seed into a private database so later tests see the shared one untouched."""
    patcher = pytest.MonkeyPatch()
    db.close_connections()
    patcher.setattr(config, "DB_PATH", tmp_path / "states.sqlite3")
    patcher.setattr(demo.icalsync, "fetch_feed", lambda *_a, **_k: None)
    try:
        yield
    finally:
        db.close_connections()
        patcher.undo()


STYLE = "e => { const c = getComputedStyle(e); return [c.backgroundColor, c.color, c.borderTopColor].join('|'); }"
WHITE = "rgb(255, 255, 255)"


def _session(base):
    db.init_db()
    user = f"states-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "States Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flat = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))["id"]
    return client.cookies.get(auth.SESSION_COOKIE), flat


def _page(playwright, base, cookie, width=1280):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    return browser, context.new_page()


def test_hover_changes_every_clickable_thing(base):
    cookie, flat = _session(base)
    targets = [
        ("/apartments", "table.properties-table tbody tr.clickable-row"),
        ("/reservations?range=all", "tbody tr.clickable-row"),
        ("/", ".needs-you-item:has([data-needs-you-go])"),
        ("/", "[data-needs-you-go]"),
        (f"/apartments/{flat}?view=overview", "a.host-property-card"),
        ("/reservations?range=all", "a.ui-chip:not([aria-current])"),
    ]
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser, page = _page(playwright, base, cookie)
        for path, selector in targets:
            page.goto(base + path + ("&" if "?" in path else "?") + "lang=en")
            element = page.locator(selector + ":visible").first
            assert element.count(), (path, selector)
            page.mouse.move(1, 1)
            page.wait_for_timeout(250)
            before = element.evaluate(STYLE)
            element.hover()
            page.wait_for_timeout(250)
            after = element.evaluate(STYLE)
            if before == after or after.split("|")[0] == WHITE:
                problems.append((path, selector, before, after))
        browser.close()
    assert not problems, problems


def test_needs_you_buttons_line_up_and_the_line_opens(base):
    cookie, _flat = _session(base)
    with sync_api.sync_playwright() as playwright:
        browser, page = _page(playwright, base, cookie)
        page.goto(base + "/?lang=en")
        rights = page.evaluate(
            "() => [...document.querySelectorAll('.needs-you-list > .needs-you-item [data-needs-you-go]')]"
            ".filter(e => e.offsetParent).map(e => Math.round(e.getBoundingClientRect().right))"
        )
        assert rights, "no What needs you line with a button"
        assert max(rights) - min(rights) <= 1, rights
        dismiss = page.locator(".needs-you-list .needs-you-dismiss button:visible")
        if dismiss.count():
            hit = dismiss.first.evaluate(
                "e => { const r = e.getBoundingClientRect(); const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !!(h && h.closest('.needs-you-dismiss')); }"
            )
            assert hit, "the dismiss x is covered by the stretched link"
        item = page.locator(".needs-you-list > .needs-you-item:has([data-needs-you-go])").first
        href = item.locator("[data-needs-you-go]").get_attribute("href")
        box = item.locator(".needs-you-copy").bounding_box()
        page.mouse.click(box["x"] + 10, box["y"] + box["height"] / 2)
        page.wait_for_url("**" + href.split("#")[0].split("?")[0] + "**")
        browser.close()
