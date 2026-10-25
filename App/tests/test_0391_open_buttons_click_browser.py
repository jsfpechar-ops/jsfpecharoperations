"""0391: every visible Open cue is a real link to the row's own target, so a click
on Open opens the same place as a click on the row."""
from __future__ import annotations

import re
import secrets
from pathlib import Path
from urllib.parse import urljoin

import jinja2
import pytest
from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

# Every page here must show a visible Open with demo data; none may be skipped.
REQUIRED_PAGES = (
    "/reservations?range=all",
    "/apartments",
    "/housebook",
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

ROW_OPEN_CALL = re.compile(r"row_open\(\s*\)")
OPEN_SPAN = re.compile(r'<span[^>]*\bclass="row-open"')


def _client():
    db.init_db()
    user = f"open-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Open Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return client


def _open_page(page, path_or_url, base_url):
    page.goto(urljoin(base_url, path_or_url))
    page.wait_for_load_state("load")
    return page.url


def _click_open(page, found):
    start = page.url
    target = urljoin(start, found["href"])
    # a real pointer click: a covering overlay that takes the click elsewhere must still land on the same href
    page.locator("a.row-open, a.host-property-card-open").nth(found["index"]).click(force=True)
    page.wait_for_url(lambda url: url == target, timeout=10000)
    assert page.url == target, (start, target)
    assert page.url != start, (start, target)


@pytest.mark.parametrize("width", (390, 1280))
def test_open_buttons_open_their_row(base, width):
    client = _client()
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    clicked = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        for path in REQUIRED_PAGES:
            _open_page(page, path, base)
            found = page.evaluate(FIRST_OPEN)
            assert found is not None, (width, path, "no visible Open")
            _click_open(page, found)
            clicked.append(path)

        # the first property overview, with its Guest links card Open
        _open_page(page, "/apartments", base)
        overview = page.evaluate(FIRST_PROPERTY)
        assert overview is not None, (width, "no property row on /apartments")
        _open_page(page, overview, page.url)
        found = page.evaluate(FIRST_OPEN)
        assert found is not None, (width, "no visible Open on the property overview")
        _click_open(page, found)
        clicked.append("property overview")


        context.close()
        browser.close()
    print(f"width {width}: clicked {clicked}")


def test_row_open_always_gets_its_target():
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), undefined=jinja2.StrictUndefined)
    env.globals["t"] = lambda key, **kw: key
    no_target, span_open = [], []
    for path in sorted(TEMPLATES.glob("**/*.html")):
        text = path.read_text(encoding="utf-8")
        name = str(path.relative_to(TEMPLATES))
        if ROW_OPEN_CALL.search(text):
            no_target.append(name)
        if OPEN_SPAN.search(text):
            span_open.append(name)
    assert no_target == [], no_target
    assert span_open == [], span_open
    html = env.from_string('{% from "_components.html" import row_open %}{{ row_open("/x") }}').render()
    assert '<a class="row-open" href="/x"' in html, html
