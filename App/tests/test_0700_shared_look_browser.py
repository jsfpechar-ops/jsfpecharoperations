"""0700 shared look: mockup v2 buttons, header, tables, badges and canvas (computed styles)."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures are re-created here)
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

ROUTES = ("/", "/reservations", "/apartments", "/cleaning")
CANVAS = "rgb(246, 246, 244)"
# origin/main: .ui-btn-primary has no radius of its own and inherits --control-radius (--radius-2 = 8px).
PHONE_PRIMARY_RADIUS = "8px"

PRIMARY_RADII = "() => Array.from(document.querySelectorAll('.ui-btn-primary')).filter(e => e.offsetParent !== null).map(e => getComputedStyle(e).borderRadius)"
PH_BORDERS = "() => Array.from(document.querySelectorAll('.ui-ph')).map(e => getComputedStyle(e).borderBottomWidth)"
MAIN_BG = "() => { const m = document.querySelector('main'); return m ? getComputedStyle(m).backgroundColor : null; }"
FIRST_TH = """() => { const th = document.querySelector('.ui-table th');
  if (!th) return null; const s = getComputedStyle(th);
  return { textTransform: s.textTransform, background: s.backgroundColor }; }"""
ROW_GAP = """() => { const rows = Array.from(document.querySelectorAll('tr.ui-row'));
  if (rows.length < 2) return null;
  return rows[1].getBoundingClientRect().top - rows[0].getBoundingClientRect().bottom; }"""


def _open(browser, wide_host, wide_base, path, width):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/"}])
    context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}")
    page = context.new_page()
    response = page.goto(f"{wide_base}{path}?lang=en")
    assert response and response.status < 400, f"{path}: HTTP {response.status if response else 'none'}"
    _wait_for_host_layout(page)
    _dismiss_optional_security_prompt(page)
    return context, page


def _launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the 0700 shared look test")


def test_computer_width_shared_look(wide_host, wide_base):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for path in ROUTES:
            context, page = _open(browser, wide_host, wide_base, path, 1280)
            try:
                radii = page.evaluate(PRIMARY_RADII)
                assert radii, f"{path}: no visible .ui-btn-primary to check"
                for radius in radii:
                    assert float(radius.replace("px", "")) >= 999, f"{path}: primary radius {radius}"
                borders = page.evaluate(PH_BORDERS)
                assert all(b == "0px" for b in borders), f"{path}: .ui-ph border-bottom {borders}"
                assert page.evaluate(MAIN_BG) == CANVAS, f"{path}: main background"
                if path == "/reservations":
                    th = page.evaluate(FIRST_TH)
                    assert th is not None, "/reservations: no .ui-table th"
                    assert th["textTransform"] == "none", th
                    assert th["background"] == "rgba(0, 0, 0, 0)", th
                    gap = page.evaluate(ROW_GAP)
                    assert gap is not None, "/reservations: fewer than two tr.ui-row"
                    assert gap == 0, f"/reservations: row gap {gap}px"
            finally:
                context.close()
        browser.close()


def test_phone_width_primary_radius_unchanged(wide_host, wide_base):
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open(browser, wide_host, wide_base, "/", 390)
        try:
            radii = page.evaluate(PRIMARY_RADII)
            assert radii, "/: no visible .ui-btn-primary at 390 px"
            assert set(radii) == {PHONE_PRIMARY_RADIUS}, radii
            assert page.evaluate(MAIN_BG) == CANVAS, "/ at 390 px: main background"
        finally:
            context.close()
            browser.close()
