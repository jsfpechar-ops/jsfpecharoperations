"""0404: the Leon setup wizard in a real browser at 390 px (plus a 1280 px footer check).

0405 adds the test chat's empty and capped states. Every screenshot waits for the page to settle:
the host pages use cross-document view transitions, so a screenshot taken on URL change can catch
two pages overlapping.

Screenshots go to docs/tasks/screenshots-0404/. Skipped when Chromium is missing, unless
UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import config, db, guest_guide, guest_guide_import, leon, rate_limit
from tests.test_0251_tablet_browser import _context, base, host  # noqa: F401 (fixtures)
from tests.test_guest_browser_e2e import browser, live_server  # noqa: F401 (fixtures)

sync_api = pytest.importorskip("playwright.sync_api")
OUT = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0404"


@pytest.fixture
def leon_offered(monkeypatch, host):  # noqa: F811
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset())
    monkeypatch.setattr(config, "APIFY_TOKEN", "test-token")
    monkeypatch.setattr(guest_guide_import, "enabled", lambda: True)
    db.execute("UPDATE apartment SET leon_enabled = 0, leon_terms_version = NULL WHERE id = ?", (host["apartment"],))
    db.execute("DELETE FROM rate_limit_event WHERE scope = ?", ("leon_try",))
    return host["apartment"]


def _progress(live: bool):
    def progress(apartment_id):
        return {
            "done": 5 if live else 0, "total": 5, "answered": 5 if live else 0, "cards": 5, "check": 0,
            "must_have_done": 5 if live else 0, "must_have_total": 5, "live": live,
        }
    return progress


def _settle(page):
    """Wait until the wizard is drawn, the network is idle, no skeleton shows and no view transition runs."""
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("[data-leon-setup]", state="visible")
    page.wait_for_function(
        "() => !document.querySelector('[data-page-skeleton]:not([hidden])')"
        " && !document.activeViewTransition"
        " && document.getAnimations().every(a => a.playState !== 'running')"
    )


def _no_overflow(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def _footer_on_one_row(page) -> bool:
    back = page.locator(".setup-wizard-foot .setup-wizard-back").bounding_box()
    primary = page.locator(".setup-wizard-foot .ui-btn-primary").bounding_box()
    return abs(back["y"] - primary["y"]) <= 2


def test_setup_wizard_in_a_browser(live_server, browser, host, base, leon_offered, monkeypatch):  # noqa: F811
    OUT.mkdir(parents=True, exist_ok=True)
    apt = leon_offered
    monkeypatch.setattr(guest_guide, "progress", _progress(False))
    context = _context(browser, base, host, 390, 844)
    try:
        page = context.new_page()
        page.goto(f"{base}/apartments/{apt}/leon/setup?lang=en")
        assert page.url.endswith("/leon/setup/switch_on")
        _settle(page)
        assert _no_overflow(page)
        assert page.locator(".ui-btn-primary").count() == 1
        page.screenshot(path=str(OUT / "switch-on-390.png"), full_page=True)

        page.locator("#leon-terms").check()
        page.locator('button[form="leon-setup-on"]').click()
        page.wait_for_url(f"**/apartments/{apt}/leon/setup/import*")
        _settle(page)
        assert page.locator('input[name="booking_url"]').count() == 1
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "import-390.png"), full_page=True)

        page.locator('input[name="booking_url"]').fill("https://www.booking.com/hotel/cz/test-apartment.html")
        page.locator('input[name="airbnb_url"]').fill("https://www.airbnb.com/rooms/123456")
        page.locator('button[form="leon-setup-import"]').click()
        page.wait_for_selector("[data-leon-import-wait]")
        _settle(page)
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "import-waiting-390.png"), full_page=True)

        page.locator('button[name="action"][value="skip_import"]').click()
        page.wait_for_url(f"**/apartments/{apt}/leon/setup/cards")
        _settle(page)
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "cards-390.png"), full_page=True)

        page.set_viewport_size({"width": 1280, "height": 900})
        assert _footer_on_one_row(page)
        page.goto(f"{base}/apartments/{apt}/leon/setup/import?lang=en")
        _settle(page)
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "import-1280.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})

        monkeypatch.setattr(guest_guide, "progress", _progress(True))
        page.goto(f"{base}/apartments/{apt}/leon/setup/try?lang=en")
        _settle(page)
        assert _no_overflow(page)
        assert page.locator("#leon-try-input").is_enabled()
        page.screenshot(path=str(OUT / "try-390.png"), full_page=True)

        for _ in range(leon.TRY_MAX):
            rate_limit.record("leon_try", str(apt))
        page.goto(f"{base}/apartments/{apt}/leon/setup/try?lang=en")
        _settle(page)
        assert _no_overflow(page)
        assert page.locator("[data-leon-try-cap]").is_visible()
        assert page.locator("#leon-try-input").is_disabled()
        page.screenshot(path=str(OUT / "try-cap-390.png"), full_page=True)

        page.locator('button[name="action"][value="finish"]').click()
        page.wait_for_url(f"**/apartments/{apt}/leon/setup/done")
        _settle(page)
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "done-390.png"), full_page=True)
    finally:
        context.close()


# --- 0973: the labelled four-step progress, the property line apart from the title, the terms ---
import os  # noqa: E402
import tempfile  # noqa: E402

OUT_0973 = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "0973-leon-setup"
LONG_NAME = "Penthouse Vinohrady with a very long property name above the river Vltava"
STEPS_0973 = ("import", "cards", "try", "done")


def _stepper(page):
    return page.evaluate(
        """() => {
          const ol = document.querySelector('[data-leon-stepper]');
          const items = [...ol.querySelectorAll(':scope > li')];
          const box = ol.getBoundingClientRect();
          return {
            states: items.map(li => li.getAttribute('data-state')),
            labels: items.map(li => li.querySelector('.fee-stepper-label').textContent.trim()),
            current: items.filter(li => li.getAttribute('aria-current') === 'step').length,
            listStyle: getComputedStyle(items[0]).listStyleType,
            clipped: items.some(li => { const l = li.querySelector('.fee-stepper-label'); return l.scrollWidth > l.clientWidth + 1; }),
            inView: box.left >= 0 && box.right <= window.innerWidth,
            display: getComputedStyle(ol).display,
            broken: items.some(li => {
              const l = li.querySelector('.fee-stepper-label');
              const name = l.firstChild.textContent.trim();
              if (name.includes(' ')) return false;
              const r = document.createRange(); r.selectNodeContents(l.firstChild);
              return new Set([...r.getClientRects()].map(x => Math.round(x.top))).size > 1;
            }),
          };
        }"""
    )


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_setup_progress_and_terms_0973(live_server, browser, host, base, leon_offered, monkeypatch, lang):  # noqa: F811
    OUT_0973.mkdir(parents=True, exist_ok=True)
    apt = leon_offered
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (LONG_NAME, apt))
    monkeypatch.setattr(guest_guide, "progress", _progress(False))
    for width in (390, 768, 1280):
        context = _context(browser, base, host, width, 900)
        try:
            page = context.new_page()
            db.execute("UPDATE apartment SET leon_enabled = 0, leon_terms_version = NULL WHERE id = ?", (apt,))
            page.goto(f"{base}/apartments/{apt}/leon/setup/switch_on?lang={lang}")
            _settle(page)
            st = _stepper(page)
            assert st["states"] == ["current", "todo", "todo", "todo"], st
            assert st["current"] == 1 and st["listStyle"] == "none" and st["display"] == "flex", st
            assert all(st["labels"]) and len(st["labels"]) == 4 and not st["clipped"] and not st["broken"] and st["inView"], st
            # The page title is the setup heading; the property name is its own line outside the heading.
            assert page.locator("h1").inner_text().strip() not in ("", LONG_NAME)
            assert LONG_NAME not in page.locator("h1").inner_text()
            assert page.locator("[data-leon-setup-property]").inner_text().strip() == LONG_NAME
            assert page.locator("[data-leon-setup-property]").evaluate("e => !e.closest('h1')")
            assert page.locator("[data-leon-exit-note]").is_visible()
            # One primary action; the agreement stays visible and required; the extra terms expand.
            assert page.locator(".ui-btn-primary").count() == 1
            assert page.locator("#leon-terms").is_visible() and page.locator("#leon-terms").get_attribute("required") is not None
            more = page.locator("[data-leon-terms-more]")
            assert more.evaluate("e => e.open") is False
            page.screenshot(path=str(OUT_0973 / f"switch_on-{lang}-{width}.png"), full_page=True)
            more.locator("summary").click()
            assert more.evaluate("e => e.open") is True and more.locator("li").count() == 4
            assert page.locator("#leon-terms").is_visible()
            assert _no_overflow(page)
            page.screenshot(path=str(OUT_0973 / f"switch_on-{lang}-{width}-open.png"), full_page=True)
            # Nothing is accepted here: the box stays unticked and the form is not submitted.
            assert not page.locator("#leon-terms").is_checked()

            # The later steps are reached by setting the sandbox workspace's own flag, not by accepting terms.
            db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = ? WHERE id = ?", (leon.LEON_TERMS_VERSION, apt))
            for step in STEPS_0973:
                page.goto(f"{base}/apartments/{apt}/leon/setup/{step}?lang={lang}")
                _settle(page)
                st = _stepper(page)
                if step == "done":
                    assert st["states"] == ["done"] * 4 and st["current"] == 0, st
                else:
                    at = STEPS_0973.index(step) + 1
                    assert st["states"][at] == "current" and st["current"] == 1 and st["states"][0] == "done", (step, st)
                    assert "current" not in st["states"][:at] + st["states"][at + 1:], (step, st)
                assert all(st["labels"]) and not st["clipped"] and not st["broken"] and st["inView"] and st["listStyle"] == "none", (step, st)
                assert _no_overflow(page)
                assert page.locator("a.ui-btn-secondary", has_text=page.locator(".setup-wizard-exit a").inner_text()).count() >= 1
                if step != "done":
                    assert page.locator("[data-leon-exit-note]").is_visible()
                page.screenshot(path=str(OUT_0973 / f"{step}-{lang}-{width}.png"), full_page=True)
        finally:
            context.close()
