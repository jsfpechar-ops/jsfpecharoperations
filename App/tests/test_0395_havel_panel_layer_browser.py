"""0395: the Havel panel sits above the calendar's sticky rows; a stale start screen is never restored."""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from tests import test_havel_browser as hb  # noqa: E402
from tests.test_submission_retry_cap import host  # noqa: E402,F401
from tests.test_dashboard_calendar import calendar_workspace  # noqa: E402,F401
from tests.test_dashboard_calendar_browser import calendar_origin, launch, open_page  # noqa: E402,F401

origin = hb.origin
_context = hb._context

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0395"
KEY = "ubyhost.havel.chat"


def _open(page):
    page.locator("[data-havel-fab]").click()
    dialog = page.locator("#havel-sheet[open]")
    dialog.wait_for()
    return dialog


def _z(page):
    return page.evaluate("getComputedStyle(document.getElementById('havel-sheet')).zIndex")


def _set_saved(page, html):
    page.evaluate(
        """([k, html]) => {
            let s = null;
            try { s = JSON.parse(sessionStorage.getItem(k) || 'null'); } catch (e) {}
            if (!s) s = { owner: document.getElementById('havel-sheet').dataset.havelOwner, saved: Date.now() };
            s.html = html;
            s.open = true;
            sessionStorage.setItem(k, JSON.stringify(s));
        }""",
        [KEY, html],
    )


def test_panel_above_calendar(calendar_workspace, calendar_origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser = launch(pw)
        context, page = open_page(browser, calendar_workspace, calendar_origin)
        page.locator(".cal-gantt-header").first.wait_for()
        _open(page)
        assert _z(page) == "60"

        page.evaluate(
            """() => {
                const h = document.querySelector('.cal-gantt-header');
                const d = document.getElementById('havel-sheet').getBoundingClientRect();
                window.scrollBy(0, h.getBoundingClientRect().top - (d.top + d.height / 2));
            }"""
        )
        inside = page.evaluate(
            """() => {
                const h = document.querySelector('.cal-gantt-header').getBoundingClientRect();
                const d = document.getElementById('havel-sheet').getBoundingClientRect();
                return h.top >= d.top && h.bottom <= d.bottom;
            }"""
        )
        assert inside, "calendar header is not inside the panel's box after the scroll"
        hit = page.evaluate(
            """() => {
                const h = document.querySelector('.cal-gantt-header').getBoundingClientRect();
                const d = document.getElementById('havel-sheet').getBoundingClientRect();
                const el = document.elementFromPoint(d.left + d.width / 2, h.top + h.height / 2);
                return !!(el && el.closest('#havel-sheet'));
            }"""
        )
        assert hit
        page.screenshot(path=str(SHOTS / "panel-calendar-1280.png"))
        context.close()
        browser.close()


def test_stale_start_screen_not_restored(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/")
        _open(page)
        page.evaluate("document.getElementById('havel-sheet').close()")
        page.locator("#havel-sheet:not([open])").wait_for(state="attached")

        _set_saved(page, '<div class="havel-topics" data-havel-topics><p>STALE</p></div>')
        page.reload()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator("[data-havel-other]")).to_be_visible()
        assert "STALE" not in dialog.inner_text()

        _set_saved(
            page,
            '<div class="havel-msg havel-msg-host"><div class="havel-bubble"><p>KEEP ME</p></div></div>',
        )
        page.reload()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        assert "KEEP ME" in dialog.inner_text()


def test_phone_panel_above_tabbar(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        _open(page)
        assert _z(page) == "60"
        page.screenshot(path=str(SHOTS / "panel-390.png"))
