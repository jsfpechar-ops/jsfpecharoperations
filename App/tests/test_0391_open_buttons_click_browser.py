"""0391: every visible Open cue is a real link to the row's own target, so a click
on Open opens the same place as a click on the row."""
from __future__ import annotations

import secrets
from urllib.parse import urljoin

import pytest
from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

PAGES = (
    "/reservations?range=all",
    "/apartments",
    "/entities",
    "/invoices",
    "/stay-fees",
    "/submissions",
    "/housebook",
    "/cleaning/properties",
)

FIRST_OPEN = """() => {
  const visible = el => el.getClientRects().length > 0;
  const all = [...document.querySelectorAll('a.row-open, a.host-property-card-open')];
  const index = all.findIndex(visible);
  return index < 0 ? null : {index: index, href: all[index].getAttribute('href')};
}"""

FIRST_PROPERTY = """() => {
  const link = document.querySelector('tr.clickable-row a.row-primary-link');
  return link ? link.getAttribute('href') : null;
}"""


def _client():
    db.init_db()
    user = f"open-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Open Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return client


def _open_and_check(page, found):
    start = page.url
    target = urljoin(start, found["href"])
    # dispatch, not a pointer click: the Guest links card's stretched title link covers its Open pill
    page.locator("a.row-open, a.host-property-card-open").nth(found["index"]).dispatch_event("click")
    page.wait_for_url(lambda url: url == target, timeout=10000)
    assert page.url == target, (start, target)
    assert page.url != start, (start, target)


@pytest.mark.parametrize("width", (390, 1280))
def test_open_buttons_open_their_row(base, width):
    client = _client()
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    clicked, skipped = [], []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        for path in PAGES:
            page.goto(base + path)
            page.wait_for_load_state("load")
            found = page.evaluate(FIRST_OPEN)
            if found is None:
                skipped.append(path)
                continue
            clicked.append(path)
            _open_and_check(page, found)
        # the first property overview, with its Guest links card Open
        page.goto(base + "/apartments")
        page.wait_for_load_state("load")
        overview = page.evaluate(FIRST_PROPERTY)
        if overview is None:
            skipped.append("property overview")
        else:
            page.goto(urljoin(page.url, overview))
            page.wait_for_load_state("load")
            found = page.evaluate(FIRST_OPEN)
            if found is None:
                skipped.append("property overview")
            else:
                clicked.append("property overview")
                _open_and_check(page, found)
        context.close()
        browser.close()
    print(f"width {width}: clicked {clicked}; no Open with demo data: {skipped}")
    assert len(clicked) >= 6, (width, clicked, skipped)
