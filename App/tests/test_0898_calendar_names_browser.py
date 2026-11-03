"""0898: long property names in the dashboard calendar clamp to two lines and never overlap (real Chromium)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.test_0508_page_swap_browser import seed
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401,F811

SHOTS_DIR = Path("/tmp/claude-0")
LONG_NAMES = [
    "Cozy Modern Apartment • Balcony & Garage",
    "Spacious 3BR Apartment • 2 Bathrooms & Garage",
    "Prostorný třipokojový byt • 2 koupelny a garáž s terasou",
    "Útulný dvoupokojový apartmán v historickém centru města",
]
CLAMP_MAX_HEIGHT = 34
WIDTHS = [390, 768, 1024, 1280, 1440]

# Per calendar name cell: its box, its row's box and its client/scroll heights.
MEASURE_JS = """
() => [...document.querySelectorAll('.cal .crow .cn')].map((cn) => {
  const row = cn.closest('.crow');
  const a = cn.getBoundingClientRect();
  const b = row.getBoundingClientRect();
  return {
    title: cn.getAttribute('title'),
    text: cn.textContent.trim(),
    top: a.top, bottom: a.bottom, left: a.left, right: a.right,
    rowTop: b.top, rowBottom: b.bottom,
    clientHeight: cn.clientHeight, scrollHeight: cn.scrollHeight,
  };
})
"""


@pytest.fixture(scope="module")
def long_workspace(calendar_workspace):
    """Renames the three active fixture properties and adds a fourth, all with long names."""
    properties = calendar_workspace["properties"]
    for apartment_id, name in zip(properties, LONG_NAMES):
        db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (name, apartment_id))
    source = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (properties[0],))
    extra = db.insert("apartment", {
        "internal_name": LONG_NAMES[3], "owner_user_id": calendar_workspace["owner"],
        "legal_entity_id": source["legal_entity_id"], "active": 1, "archived_at": None,
        "created_at": db.utcnow(), "automation_mode": "manual",
        "permalink_token": secrets.token_hex(12),
    })
    yield {**calendar_workspace, "properties": [*properties, extra]}
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (extra,))
    db.execute("DELETE FROM apartment WHERE id = ?", (extra,))


def open_at_width(browser, ws, origin, width):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    page = context.new_page()
    page.goto(origin + "/?lang=en")
    page.wait_for_load_state()
    # Swap to a page that uses the old stylesheet set, then back to the dashboard (the old stylesheet set forces a full load).
    page.evaluate("() => window.Turbo.visit('/payments?lang=en')")
    page.wait_for_function("() => location.pathname === '/payments'", timeout=15000)
    page.evaluate("() => window.Turbo.visit('/?lang=en')")
    page.wait_for_function("() => location.pathname === '/'", timeout=15000)
    page.wait_for_selector(".cal .crow .cn", state="attached", timeout=15000)
    return context, page


def check_geometry(cells, width):
    assert len(cells) >= len(LONG_NAMES), f"width {width}: expected the long-name rows, got {len(cells)}"
    names = [cell["title"] for cell in cells]
    for name in LONG_NAMES:
        assert name in names, f"width {width}: missing title {name!r} in {names}"
    for cell in cells:
        assert cell["title"] == cell["text"], f"width {width}: title attribute differs from text {cell}"
        assert cell["bottom"] <= cell["rowBottom"] + 1, f"width {width}: name overflows its row {cell}"
        assert cell["top"] >= cell["rowTop"] - 1, f"width {width}: name starts above its row {cell}"
        assert cell["clientHeight"] <= CLAMP_MAX_HEIGHT, f"width {width}: name not clamped {cell}"
    for i, first in enumerate(cells):
        for second in cells[i + 1:]:
            overlap_y = min(first["bottom"], second["bottom"]) - max(first["top"], second["top"])
            overlap_x = min(first["right"], second["right"]) - max(first["left"], second["left"])
            assert not (overlap_x > 0 and overlap_y > 1), f"width {width}: names overlap {first} {second}"


@pytest.mark.parametrize("width", WIDTHS)
def test_long_calendar_names_clamp_and_do_not_overlap(long_workspace, calendar_origin, width):
    seed(long_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_at_width(browser, long_workspace, calendar_origin, width)
        visible = page.locator(".cal").first.is_visible()
        # The overview calendar is hidden under 1024 px on body.v2 by design (app2.css, max-width:1023px).
        assert visible == (width >= 1024), f"width {width}: calendar visible={visible}"
        if not visible:
            # Force the block visible only to measure the clamp at this width.
            page.add_style_tag(content=".ov-cal-block{display:block !important}")
            page.wait_for_selector(".cal .crow .cn", state="visible", timeout=15000)
        cells = page.evaluate(MEASURE_JS)
        check_geometry(cells, width)
        if width in (768, 1280):
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            page.locator(".cal").first.screenshot(path=str(SHOTS_DIR / f"cal_names_{width}.png"))
        context.close()
        browser.close()
