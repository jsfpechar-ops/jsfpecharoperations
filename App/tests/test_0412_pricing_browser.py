"""0412: the /cenik calculator in a real browser: numbers update, nothing scrolls sideways."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn

from app import db, signup
from app.main import app
from tests.browser_support import chromium_launch_kwargs

EVIDENCE = Path(os.environ.get("UBYHOST_SHOTS_DIR", str(Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-pricing-panel")))


@pytest.fixture(scope="module")
def base():
    db.init_db()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the pricing test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _browser(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the pricing calculator test")



def _number(locator):
    return int(locator.inner_text().replace("\u00a0", "").replace(",", ""))


def _geometry(page, width):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    plans = page.locator(".pricing-plans").bounding_box()
    controls = page.locator("[data-pricing-calc]").bounding_box()
    if controls:
        assert 0 <= plans["y"] - (controls["y"] + controls["height"]) <= 33
    bands = page.locator(".pricing-bands").bounding_box()
    assert 0 <= bands["y"] - (plans["y"] + plans["height"]) <= 20
    if width >= 1024:
        boxes = [page.locator(f'[data-plan="{plan}"] .pricing-button').bounding_box()
                 for plan in ("standard", "max")]
        assert abs(boxes[0]["y"] - boxes[1]["y"]) <= 1, boxes
        assert abs(boxes[0]["height"] - boxes[1]["height"]) <= 1, boxes


@pytest.mark.parametrize("lang", ["cs", "en"])
@pytest.mark.parametrize("width", [360, 390, 1024, 1280])
def test_the_calculator_updates_and_aligns(base, monkeypatch, lang, width):
    monkeypatch.setattr(signup, "enabled", lambda: True)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{base}/cenik?lang={lang}")
        page.wait_for_load_state("networkidle")
        assert page.locator("[data-pricing-calc]").is_visible()
        std = page.locator('[data-plan="standard"] [data-total]')
        top = page.locator('[data-plan="max"] [data-total]')
        assert (_number(std), _number(top)) == (99, 159)
        assert page.locator('[data-plan="standard"] [data-ttlock]').count() == 1
        assert page.locator('[data-plan="max"] [data-ttlock]').count() == 0
        assert page.locator(".pricing-founder").count() == 0
        assert page.locator(".pricing-badge-slot, .pricing-total-label").count() == 0
        std_features = page.locator('[data-plan="standard"] .pricing-features').inner_text()
        max_features = page.locator('[data-plan="max"] .pricing-features').inner_text()
        assert "Havel" in std_features and "Leon Lite" in std_features
        assert page.locator('[data-plan="max"]').inner_text().count("TTLock") == 1
        assert "Leon" in max_features and "Havel" in max_features and "24/7" in max_features
        assert page.locator('[data-plan="standard"] .pricing-features > li:not(.pricing-option)').count() == 6
        assert page.locator('[data-plan="max"] .pricing-features > li').count() == 6
        assert page.locator('[data-plan="max"] .pricing-badge').is_visible()
        assert page.locator('[data-plan="max"] .pricing-option').count() == 0
        assert page.locator(".pricing-coming-soon svg").count() == 0
        assert not page.locator(".pricing-bands").get_attribute("open")
        page.locator(".pricing-bands summary").click()
        assert page.locator(".pricing-bands > p").is_visible()
        page.locator(".pricing-bands summary").click()
        assert page.locator(".pricing-plans-section [data-band]").count() == 3
        assert page.locator(".pricing-plans-section [data-addon]").count() == 1
        assert "40" in page.locator('[data-addon="ttlock"]').inner_text()
        _geometry(page, width)
        if (width == 390 or (width == 1280 and lang == "en")) and (
            os.environ.get("UBYHOST_SHOTS_DIR") or os.environ.get("UBYHOST_CAPTURE_0412") == "1"
        ):
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(EVIDENCE / f"cenik-{lang}-{width}.png"), full_page=True)
        count = 1
        for n, annual, monthly in ((1, 1190, 149), (4, 4760, 596),
                                   (5, 5710, 715), (9, 9510, 1191),
                                   (10, 10300, 1290), (50, 41900, 5250)):
            for _ in range(n - count):
                page.locator('[data-step="1"]').click()
            count = n
            for interval in ("year", "month"):
                page.locator(f'[data-interval="{interval}"]').click()
                assert [_number(page.locator(f'[data-band="{i}"]')) for i in range(3)] == (
                    [99, 79, 66] if interval == "year" else [149, 119, 99]
                )
                assert "40" in page.locator('[data-addon="ttlock"]').inner_text()
                max_annual = annual + min(n, 4) * 718 + min(max(n - 4, 0), 5) * 570 + max(n - 9, 0) * 370
                max_monthly = monthly + min(n, 4) * 80 + min(max(n - 4, 0), 5) * 59 + max(n - 9, 0) * 39
                max_price = (max_annual * 2 + 12) // 24 if interval == "year" else max_monthly
                assert _number(top) == max_price
                for lock in (False, True):
                    page.locator("[data-ttlock]").set_checked(lock)
                    expected = ((annual + (480 * n if lock else 0)) * 2 + 12) // 24 if interval == "year" else monthly + (40 * n if lock else 0)
                    assert _number(std) == expected, (lang, width, n, interval, lock)
                    assert _number(top) == max_price
                    assert page.locator("[data-ttlock-selected]").is_visible() == lock
                    _geometry(page, width)
                    for plan in ("standard", "max"):
                        href = page.locator(f'[data-plan="{plan}"] [data-cta-plan]').get_attribute("href")
                        assert f"plan={plan}" in href and f"interval={interval}" in href and f"apts={n}" in href
                        assert ("ttlock=1" in href) == (lock and plan == "standard")
                    if n == 5 and interval == "month":
                        assert _number(top) == 1094
                page.locator("[data-ttlock]").uncheck()
        assert page.locator('[data-step="1"]').is_disabled()
        assert not errors, errors
        page.close()
        browser.close()


@pytest.mark.parametrize("lang", ["cs", "en"])
def test_no_javascript_has_truthful_annual_prices_and_login_fallback(base, monkeypatch, lang):
    monkeypatch.setattr(signup, "enabled", lambda: False)
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        page = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 900})
        page.goto(f"{base}/cenik?lang={lang}")
        assert not page.locator("[data-pricing-calc]").is_visible()
        assert not page.locator("[data-ttlock-control]").is_visible()
        assert [_number(page.locator(f'[data-plan="{plan}"] [data-total]')) for plan in ("standard", "max")] == [99, 159]
        assert "40" in page.locator('[data-addon="ttlock"]').inner_text()
        assert "Havel" in page.locator('[data-plan="standard"] .pricing-features').inner_text()
        assert page.locator('[data-addon="whitelabel"]').count() == 0
        assert all("/login?lang=" in href for href in page.locator("a[data-cta-plan]").evaluate_all("(links) => links.map(link => link.getAttribute('href'))"))
        _geometry(page, 390)
        browser.close()
