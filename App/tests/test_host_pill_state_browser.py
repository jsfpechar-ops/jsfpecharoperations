"""Stays and archive filter pills keep the current pill dark on hover and focus (0950)."""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

RGB = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.%]+)\s*)?\)")
WIDTHS = (390, 768, 1280)


def parse_rgb(value: str) -> tuple[list[float], float]:
    match = RGB.fullmatch(value.strip())
    assert match, f"unparsed colour {value!r}"
    channels = [float(match.group(index)) for index in (1, 2, 3)]
    alpha = match.group(4)
    if alpha is None:
        return channels, 1.0
    if alpha.endswith("%"):
        return channels, float(alpha[:-1]) / 100
    return channels, float(alpha)


def relative_luminance(channels: list[float]) -> float:
    def linear(value: float) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(value) for value in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: list[float], background: list[float]) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"pillstate-{secrets.token_hex(4)}"
    owner = auth.create_account(
        f"{username}@example.test", "Pill State Test", role="host", username=username
    )
    entity = db.insert("legal_entity", {
        "name": "Pill State Test s.r.o.", "owner_user_id": owner, "created_at": db.utcnow(),
    })
    apartment = db.insert("apartment", {
        "internal_name": "Pill State Property",
        "owner_user_id": owner,
        "legal_entity_id": entity,
        "permalink_token": f"pillstate{secrets.token_hex(3)}",
        "active": 1,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner, "entity": entity, "apartment": apartment}
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


@pytest.fixture
def playwright_api():
    with sync_api.sync_playwright() as playwright:
        yield playwright


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base(host):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the pill-state browser server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _open(playwright, host, base, path, width, lang="en"):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(
        viewport={"width": width, "height": 1000},
        has_touch=width <= 600,
    )
    context.add_cookies([{
        "name": auth.SESSION_COOKIE,
        "value": host["client"].cookies.get(auth.SESSION_COOKIE),
        "url": base + "/",
    }])
    page = context.new_page()
    page.goto(base + path + ("&" if "?" in path else "?") + "lang=" + lang)
    page.wait_for_load_state("networkidle")
    return browser, page


def _ink_rgb(page) -> tuple[list[float], float]:
    value = page.evaluate("""() => {
        const probe = document.createElement('div');
        probe.style.background = 'var(--ink)';
        document.body.appendChild(probe);
        const colour = getComputedStyle(probe).backgroundColor;
        probe.remove();
        return colour;
    }""")
    return parse_rgb(value)


def _assert_current_pill_dark(page, selector):
    locator = page.locator(selector).first
    expected_bg, _ = _ink_rgb(page)
    text_rgb, _ = parse_rgb(locator.evaluate("el => getComputedStyle(el).color"))
    bg_rgb, _ = parse_rgb(locator.evaluate("el => getComputedStyle(el).backgroundColor"))
    assert bg_rgb == expected_bg, f"current pill background {bg_rgb} != --ink {expected_bg}"
    ratio = contrast_ratio(text_rgb, bg_rgb)
    assert ratio >= 4.5, f"current pill contrast {ratio:.2f} below 4.5"


@pytest.mark.parametrize("width", WIDTHS)
def test_stays_current_pill_stays_dark_on_hover_and_focus(playwright_api, host, base, width):
    browser, page = _open(playwright_api, host, base, "/reservations", width)
    try:
        current = page.locator(".stays-pills .settings-pill.is-current").first
        assert page.locator(".stays-pills .settings-pill.is-current").count() == 1, "no current Stays pill"
        current.hover()
        _assert_current_pill_dark(page, ".stays-pills .settings-pill.is-current")
        current.focus()
        _assert_current_pill_dark(page, ".stays-pills .settings-pill.is-current")
        other = page.locator(".stays-pills .settings-pill:not(.is-current)").first
        other.hover()
        bg = other.evaluate("el => getComputedStyle(el).backgroundColor")
        assert bg == "rgb(228, 228, 228)", f"non-current hover background {bg}"
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            target = Path(shots) / "0950"
            target.mkdir(parents=True, exist_ok=True)
            page.locator(".stays-pills .settings-pill.is-current").first.hover()
            page.screenshot(path=str(target / f"reservations-{width}.png"), full_page=False)
    finally:
        browser.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_archive_current_pill_stays_dark_on_hover_and_focus(playwright_api, host, base, width):
    browser, page = _open(playwright_api, host, base, "/settings/archived", width)
    try:
        current = page.locator(".settings-pill.is-current").first
        assert current.count() == 1, "no current archive pill"
        current.hover()
        _assert_current_pill_dark(page, ".settings-pill.is-current")
        current.focus()
        _assert_current_pill_dark(page, ".settings-pill.is-current")
    finally:
        browser.close()


def _assert_phone_filters_fit(page):
    nav = page.locator(".stays-pills .settings-pills")
    assert nav.locator(".settings-pill").count() == 5
    geometry = nav.evaluate("""el => {
        const bounds = el.getBoundingClientRect();
        return {
            left: bounds.left, right: bounds.right,
            clientWidth: el.clientWidth, scrollWidth: el.scrollWidth,
            viewportWidth: innerWidth,
            pageWidth: document.documentElement.scrollWidth,
            pills: [...el.querySelectorAll('.settings-pill')].map(pill => {
                const box = pill.getBoundingClientRect();
                const range = document.createRange();
                range.selectNodeContents(pill);
                const text = range.getBoundingClientRect();
                return {
                    label: pill.textContent.trim(), left: box.left, right: box.right,
                    top: box.top, width: box.width, height: box.height,
                    textLeft: text.left, textRight: text.right,
                    textLines: range.getClientRects().length
                };
            })
        };
    }""")
    assert geometry["scrollWidth"] <= geometry["clientWidth"] + 1, geometry
    assert geometry["pageWidth"] <= geometry["viewportWidth"] + 1, geometry
    assert geometry["left"] >= 0 and geometry["right"] <= geometry["viewportWidth"] + 1, geometry
    for pill in geometry["pills"]:
        assert pill["width"] >= 44 and pill["height"] >= 44, pill
        assert pill["left"] >= geometry["left"] - 1, pill
        assert pill["right"] <= geometry["right"] + 1, pill
        assert pill["textLeft"] >= pill["left"] - 1, pill
        assert pill["textRight"] <= pill["right"] + 1, pill
        assert pill["textLines"] == 1, pill
    assert max(pill["top"] for pill in geometry["pills"]) > min(
        pill["top"] for pill in geometry["pills"]
    ), "phone filters should wrap instead of hiding options in a scroller"


@pytest.mark.parametrize("width", (320, 390))
@pytest.mark.parametrize("lang", ("cs", "en"))
def test_phone_stays_filters_are_visible_and_preserve_selection(playwright_api, host, base, width, lang):
    path = f"/reservations?status=all&apartment={host['apartment']}"
    browser, page = _open(playwright_api, host, base, path, width, lang=lang)
    try:
        page.evaluate("() => document.fonts.ready")
        _assert_phone_filters_fit(page)
        pills = page.locator(".stays-pills .settings-pill")
        pills.first.focus()
        for index in range(1, pills.count()):
            page.keyboard.press("Tab")
            assert pills.nth(index).evaluate("el => el === document.activeElement")
        _assert_phone_filters_fit(page)
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            target = Path(shots) / "0950-fix-1"
            target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / f"stays-{lang}-{width}.png"), full_page=False)

        pills.last.click()
        page.wait_for_url(re.compile(r"range=archive"))
        page.wait_for_load_state("networkidle")
        query = parse_qs(urlparse(page.url).query)
        assert query["range"] == ["archive"]
        assert query["status"] == ["all"]
        assert query["apartment"] == [str(host["apartment"])]
        assert page.locator(".stays-pills .settings-pill.is-current").count() == 1
        assert page.locator(".stays-pills .settings-pill").last.get_attribute("aria-current") == "page"
        _assert_phone_filters_fit(page)
        current = page.locator(".stays-pills .settings-pill.is-current")
        current.hover()
        _assert_current_pill_dark(page, ".stays-pills .settings-pill.is-current")
        current.focus()
        _assert_current_pill_dark(page, ".stays-pills .settings-pill.is-current")
        if shots:
            page.screenshot(path=str(target / f"stays-archive-{lang}-{width}.png"), full_page=False)
    finally:
        browser.close()
