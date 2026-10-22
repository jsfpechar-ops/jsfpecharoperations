"""0281: Properties and Business rows are outlined cards on phone.

Each card row has a 1 px border on all four sides, and on the business
edit view the business name link never overlaps a button in its row.
"""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
BORDER_PROBE = r"""(selector) => [...document.querySelectorAll(selector)].map(row => {
  const s = getComputedStyle(row);
  return [s.borderTopWidth, s.borderLeftWidth, s.borderRightWidth, s.borderBottomWidth];
})"""
OVERLAP_PROBE = r"""() => {
  const hits = [];
  const overlap = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  for (const row of document.querySelectorAll('.lc-entities tbody tr')) {
    const name = row.querySelector('.row-primary-link');
    if (!name) continue;
    const nb = name.getBoundingClientRect();
    for (const btn of row.querySelectorAll('.ui-btn, .btn')) {
      if (overlap(nb, btn.getBoundingClientRect())) hits.push(name.textContent.trim().slice(0, 40));
    }
  }
  return hits;
}"""


def test_phone_rows_have_full_border_and_buttons_do_not_cover_names(base):
    db.init_db()
    user = f"cards-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Card Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, user_agent=PHONE,
        )
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": client.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
        page = context.new_page()

        page.goto(base + "/apartments?lang=en")
        page.wait_for_timeout(200)
        rows = page.evaluate(BORDER_PROBE, ".lc-properties tbody tr")
        assert rows, "no property rows on /apartments"
        for sides in rows:
            assert sides == ["1px", "1px", "1px", "1px"], sides

        page.goto(base + "/entities?lang=en")
        page.wait_for_timeout(200)
        rows = page.evaluate(BORDER_PROBE, ".lc-entities tbody tr")
        assert rows, "no business rows on /entities"
        for sides in rows:
            assert sides == ["1px", "1px", "1px", "1px"], sides

        page.goto(base + "/entities?edit=1&lang=en")
        page.wait_for_timeout(200)
        assert page.evaluate(OVERLAP_PROBE) == []
        context.close()
        browser.close()
