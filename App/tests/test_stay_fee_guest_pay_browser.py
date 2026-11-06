"""0897: guest-pay block in the browser: live QR preview while typing, floating Save bar."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import config, db
from tests.browser_support import chromium_launch_kwargs
from tests.property_host_fixture import host  # noqa: F401
from tests.test_property_navigation_browser import _context, base  # noqa: F401

SHOTS = Path("/opt/cursor/artifacts")


def _open_fee(page, url):
    page.goto(url)
    if not page.evaluate("() => document.getElementById('sec-fee').open"):
        page.locator("#sec-fee > summary").first.click()
    page.locator("#stay-fee-guest-pay").scroll_into_view_if_needed()


def test_stored_account_and_live_preview_without_reload(host, base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    db.update("legal_entity", host["entities"][0], {"iban": None, "bank_account": None})
    url = f"{base}/apartments/{host['apartment']}?lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _context(browser, base, host)
        page = context.new_page()
        _open_fee(page, url)
        page.evaluate("() => { window.__same = true; }")
        page.check("#stay_fee_collect")
        page.locator("input[name='stay_fee_guest_rails'][value='iban']").check()
        box = page.locator("#stay-fee-guest-preview")
        assert not box.is_visible()
        page.fill("#stay_fee_guest_operator_account", "19-2000145399/0800")
        box.wait_for(state="visible", timeout=5000)
        assert page.evaluate("() => window.__same === true")
        assert page.locator("[data-preview-account]").inner_text().replace(" ", "").startswith("CZ")
        assert page.locator("[data-preview-qr]").get_attribute("src").startswith("data:image/png;base64,")
        page.fill("#stay_fee_guest_operator_account", "123")
        page.locator("[data-preview-invalid]").wait_for(state="visible", timeout=5000)
        assert not box.is_visible()
        page.fill("#stay_fee_guest_operator_account", "19-2000145399/0800")
        box.wait_for(state="visible", timeout=5000)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "guest-pay-live-preview-1280.png"))
        bar = page.locator(".savebar[data-for='property-settings-form']")
        assert bar.is_visible()
        box_bar = bar.bounding_box()
        viewport = page.viewport_size["height"]
        assert box_bar["y"] + box_bar["height"] <= viewport + 1, (box_bar, viewport)
        browser.close()


def test_account_saved_in_invoice_settings_shows_up_in_the_row(host, base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    db.update("legal_entity", host["entities"][0], {"iban": "CZ6508000000192000145399", "bank_account": "19-2000145399/0800"})
    url = f"{base}/apartments/{host['apartment']}?lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        _open_fee(page, url)
        page.check("#stay_fee_collect")
        page.locator("input[name='stay_fee_guest_rails'][value='iban']").check()
        assert page.input_value("#stay_fee_guest_operator_account") == "19-2000145399/0800"
        assert page.locator("#stay-fee-guest-preview").is_visible()
        browser.close()


def test_each_method_shows_its_details_and_the_switch_hides_all(host, base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    db.update("legal_entity", host["entities"][0], {"iban": "CZ6508000000192000145399", "bank_account": "19-2000145399/0800"})
    db.update("apartment", host["apartment"], {"stay_fee_collect": 0, "stay_fee_guest_rails": ""})
    url = f"{base}/apartments/{host['apartment']}?lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        _open_fee(page, url)
        assert not page.locator(".gp-body").is_visible()
        page.check("#stay_fee_collect")
        assert page.locator(".gp-body").is_visible()
        assert not page.locator(".gp-account").is_visible()
        assert not page.locator(".gp-revolut").is_visible()
        assert not page.locator(".gp-cash").is_visible()
        page.locator("input[name='stay_fee_guest_rails'][value='revolut']").check()
        assert page.locator(".gp-revolut").is_visible()
        page.locator("input[name='stay_fee_guest_rails'][value='iban']").check()
        assert page.locator(".gp-account").is_visible()
        options = page.locator("#stay_fee_guest_default_rail option[data-rail]")
        enabled = [o.get_attribute("data-rail") for o in options.all() if not o.is_disabled()]
        assert sorted(enabled) == ["iban", "revolut"]
        page.select_option("#stay_fee_guest_default_rail", "revolut")
        page.locator("input[name='stay_fee_guest_rails'][value='revolut']").uncheck()
        assert page.input_value("#stay_fee_guest_default_rail") == "iban"
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.locator("input[name='stay_fee_guest_rails'][value='cash']").check()
        page.locator("#stay-fee-guest-pay").scroll_into_view_if_needed()
        page.screenshot(path=str(SHOTS / "guest-pay-settings-1280.png"))
        mobile = _context(browser, base, host).new_page()
        mobile.set_viewport_size({"width": 390, "height": 900})
        _open_fee(mobile, url)
        mobile.check("#stay_fee_collect") if not mobile.is_checked("#stay_fee_collect") else None
        mobile.locator("#stay-fee-guest-pay").scroll_into_view_if_needed()
        mobile.screenshot(path=str(SHOTS / "guest-pay-settings-390.png"))
        assert mobile.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()


_LABEL_STYLE = """(id) => {
  const l = document.querySelector('label[for=' + id + ']');
  const cs = getComputedStyle(l);
  const tail = l.querySelector('.tip-tail');
  return {fs: cs.fontSize, fw: cs.fontWeight, ls: cs.letterSpacing, lh: cs.lineHeight, mb: cs.marginBottom,
          rowMb: getComputedStyle(l.parentElement).marginBottom, tail: tail ? getComputedStyle(tail).display : null};
}"""


def test_section_four_labels_look_like_the_labels_in_sections_one_to_three(host, base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    url = f"{base}/apartments/{host['apartment']}?lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        _open_fee(page, url)
        page.check("#stay_fee_collect")
        for rail in ("iban", "revolut", "cash"):
            page.locator(f"input[name='stay_fee_guest_rails'][value='{rail}']").check()
        reference = page.evaluate(_LABEL_STYLE, "stay_fee_council_account")
        assert reference["tail"] == "inline-block"
        for field in ("stay_fee_guest_operator_account", "stay_fee_guest_revolut_link",
                      "stay_fee_guest_cash_note", "stay_fee_guest_default_rail"):
            assert page.evaluate(_LABEL_STYLE, field) == reference, field
        browser.close()
