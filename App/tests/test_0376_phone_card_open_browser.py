"""0376: on phone/tablet Properties row cards the Open cue sits bottom-right on
its own line, below every field; the actions cell is see-through and cells
carry no background of their own."""
from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

CARDS = """() => {
  const visible = el => el.getClientRects().length > 0;
  const hit = (a, b) => a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1;
  return [...document.querySelectorAll('table.properties-table tbody tr.clickable-row')].filter(tr => {
    const thead = tr.closest('table').querySelector('thead');
    return visible(tr) && thead && getComputedStyle(thead).display === 'none';
  }).map(tr => {
    const tds = [...tr.children].filter(td => td.tagName === 'TD');
    const open = tr.querySelector('.row-open');
    const info = {open: !!open && visible(open), overlaps: [], above: [],
                  bgs: tds.map(td => getComputedStyle(td).backgroundColor)};
    if (!info.open) return info;
    const ob = open.getBoundingClientRect();
    for (const td of tds) {
      if (td.contains(open)) continue;
      for (const el of td.querySelectorAll('strong, a, span, .pill, .ui-badge')) {
        if (visible(el) && hit(ob, el.getBoundingClientRect())) overlaps.push(el.className || el.tagName);
      }
      if (td.matches('td.row-actions') || !visible(td)) continue;
      if (ob.top < td.getBoundingClientRect().bottom - 1) above.push(td.className || td.tagName);
    }
    return info;
  });
}"""


def _client():
    db.init_db()
    user = f"cards-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Cards Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return client


@pytest.mark.parametrize("lang", ("en", "cs"))
@pytest.mark.parametrize("width", (390, 820))
def test_phone_card_open_has_its_own_line(base, width, lang):
    client = _client()
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + f"/apartments?lang={lang}")
        page.wait_for_selector("table.properties-table tbody tr.clickable-row", state="attached")
        rows = page.evaluate(CARDS)
        context.close()
        browser.close()
    assert rows, (width, lang)
    for index, row in enumerate(rows):
        where = (width, lang, index)
        assert row["open"], where
        assert not row["overlaps"], (where, row["overlaps"])
        assert not row["above"], (where, row["above"])
        assert all(bg == "rgba(0, 0, 0, 0)" for bg in row["bgs"]), (where, row["bgs"])
