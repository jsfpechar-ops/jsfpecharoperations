"""0153: the content lane starts right of the rail and the header buttons keep
their v2 styles, collapsed and expanded, at 1280 and 2000 px (MASTER 6.2)."""
import os
import secrets

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

PAGES = ("/", "/onboarding", "/reservations", "/invoices", "/settings")
HAS_PRIMARY = ("/", "/reservations")  # migrated page headers with a primary action; the rest are checked when present
PRIMARY_BG = "rgb(173, 73, 66)"  # --accent = --coral-600 #ad4942
SECONDARY_BORDER = "rgb(201, 201, 194)"  # --line-strong = --sand-400 #c9c9c2
GEOMETRY = """(() => {
  const rail = document.querySelector('.ui-sidebar').getBoundingClientRect();
  const main = document.querySelector('#main-content');
  const under = [];
  for (const el of main.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.left < rail.right - 0.5) under.push(el.tagName + '.' + String(el.className).slice(0, 40) + '@' + Math.round(r.left));
    if (under.length >= 5) break;
  }
  const btn = (sel) => [...document.querySelectorAll(sel)].filter(b => b.getBoundingClientRect().height > 0).map(b => {
    const c = getComputedStyle(b); return {bg: c.backgroundColor, border: c.borderTopWidth + ' ' + c.borderTopColor, h: Math.round(b.getBoundingClientRect().height)}; });
  return {railRight: rail.right, mainLeft: main.getBoundingClientRect().left, under,
          scrollLeft: document.scrollingElement.scrollLeft, scrollWidth: document.documentElement.scrollWidth, innerWidth: innerWidth,
          primary: btn('.ui-ph-acts .ui-btn-primary'), secondary: btn('.ui-ph-acts .ui-btn-secondary')};
})()"""


def _account():
    username = f"lane{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Lane", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Lane s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {"internal_name": "Lane flat", "owner_user_id": owner, "legal_entity_id": entity,
                            "permalink_token": f"ln{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username


@pytest.mark.parametrize("width", [1280, 2000])
@pytest.mark.parametrize("collapsed", [False, True])
def test_main_starts_right_of_the_rail_and_header_buttons_keep_v2_styles(base, width, collapsed):
    username = _account()
    cookie = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        if collapsed:
            context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '1'); } catch (e) {}")
        page = context.new_page()
        rail_w = 64 if collapsed else 240
        for path in PAGES:
            page.goto(base + path + "?lang=en")
            page.wait_for_selector("#main-content", timeout=30000)
            assert page.evaluate("document.body.classList.contains('sidebar-collapsed')") is collapsed, path
            page.wait_for_function(  # app.css animates margin-left for 0.26 s
                "w => getComputedStyle(document.querySelector('.wrap.with-sidebar')).marginLeft === w + 'px'", arg=rail_w, timeout=3000)
            g = page.evaluate(GEOMETRY)
            assert round(g["railRight"]) == rail_w, (path, g["railRight"])
            assert g["scrollLeft"] == 0 and g["scrollWidth"] <= g["innerWidth"], (path, g)
            assert g["mainLeft"] >= g["railRight"], (path, g["mainLeft"], g["railRight"])
            assert g["under"] == [], (path, width, collapsed, g["under"])
            if path in HAS_PRIMARY:
                assert g["primary"], (path, "no visible primary header button")
            for b in g["primary"]:
                assert b["bg"] == PRIMARY_BG and b["h"] == 40, (path, b)
            for b in g["secondary"]:
                assert b["border"] == f"1px {SECONDARY_BORDER}" and b["h"] == 40, (path, b)
        browser.close()
