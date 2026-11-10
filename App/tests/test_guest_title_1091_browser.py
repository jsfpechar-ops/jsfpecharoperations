"""Brief 1091: the guest form title fits on one line at 390 px (en, de, uk), and brief 1093: cs, es, fr.

Browser tests; run with UBYHOST_REQUIRE_BROWSER=1 so a missing Chromium fails instead of skipping.
Test e writes docs/tasks/screenshots-1091/form-{390,768,1280}.png.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest

from app import i18n, mail
from tests.test_guest_browser_e2e import _fee_seed, browser, live_server  # noqa: F401

__all__ = ["browser", "live_server"]

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1091"
SHOTS_1093 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1093"
EXPECTED_1093 = {"cs": "Registrace hosta", "es": "Ficha de huésped", "fr": "Fiche voyageur"}
H1_JS = """async () => {
  await document.fonts.ready;
  const h1 = document.querySelector('.g-head h1');
  const cs = getComputedStyle(h1);
  const lh = parseFloat(cs.lineHeight);
  return {text: h1.textContent.trim(), size: cs.fontSize, lh: lh,
          height: h1.getBoundingClientRect().height,
          fits: h1.scrollWidth <= h1.clientWidth};
}"""
FIELDS = ("#guest-form", '[name="first_name"]', '[name="surname"]', '[name="birth_date"]',
          '[name="nationality"]', '[name="doc_number"]', '[name="legal_ack"]')


def _open_url(live_server, monkeypatch, part, lang="en"):
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-1091-{part}-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    return f"{live_server}/l/{token}/{stay}/new?lang={lang}"


def _measure(browser, url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    try:
        page = context.new_page()
        page.goto(url)
        info = page.evaluate(H1_JS)
        counts = {sel: page.locator(sel).count() for sel in FIELDS}
        return info, counts, page
    finally:
        context.close()


def _one_line(info):
    return info["height"] <= info["lh"] * 1.1 and info["fits"]


@pytest.mark.parametrize("lang", ["en", "de"])
def test_1091_a_title_is_one_line_at_24px_on_390(live_server, browser, monkeypatch, lang):
    url = _open_url(live_server, monkeypatch, f"a{lang}", lang)
    info, _, _ = _measure(browser, url, 390, 844)
    assert info["text"] == i18n.translator(lang)("title"), info
    assert _one_line(info), info
    assert info["size"] == "24px", info


@pytest.mark.parametrize("width,height", [(768, 1024), (1280, 800)])
def test_1091_b_wide_layouts_keep_28px(live_server, browser, monkeypatch, width, height):
    url = _open_url(live_server, monkeypatch, f"b{width}")
    info, _, _ = _measure(browser, url, width, height)
    assert info["size"] == "28px", info
    assert _one_line(info), info


def test_1091_c_nothing_is_hidden(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "c")
    _, counts, _ = _measure(browser, url, 390, 844)
    for sel, n in counts.items():
        assert n >= 1, sel


@pytest.mark.parametrize("lang", ["cs", "es", "fr", "uk"])
def test_1091_d_long_titles_wrap_but_are_not_cut(live_server, browser, monkeypatch, lang):
    url = _open_url(live_server, monkeypatch, f"d{lang}", lang)
    info, _, _ = _measure(browser, url, 390, 844)
    assert info["text"] != i18n.translator("en")("title"), info
    assert info["fits"], info
    print(f"1091 lines {lang}: {round(info['height'] / info['lh'])}")


def test_1091_e_screenshots(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "e")
    SHOTS.mkdir(parents=True, exist_ok=True)
    for width, height in ((390, 844), (768, 1024), (1280, 800)):
        context = browser.new_context(viewport={"width": width, "height": height})
        try:
            page = context.new_page()
            page.goto(url)
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(SHOTS / f"form-{width}.png"), full_page=False)
        finally:
            context.close()


@pytest.mark.parametrize("lang", ["cs", "es", "fr"])
@pytest.mark.parametrize("width,height", [(390, 844), (375, 812), (360, 740)])
def test_1093_f_title_is_one_line_cs_es_fr(live_server, browser, monkeypatch, lang, width, height):
    url = _open_url(live_server, monkeypatch, f"f{lang}{width}", lang)
    info, _, _ = _measure(browser, url, width, height)
    assert info["text"] == i18n.translator(lang)("title"), info
    assert info["text"] == EXPECTED_1093[lang], info
    assert _one_line(info), info
    assert info["size"] == "24px", info


def test_1093_g_screenshots(live_server, browser, monkeypatch):
    SHOTS_1093.mkdir(parents=True, exist_ok=True)
    for lang in ("cs", "es", "fr"):
        url = _open_url(live_server, monkeypatch, f"g{lang}", lang)
        for width, height in ((390, 844), (360, 740)):
            context = browser.new_context(viewport={"width": width, "height": height})
            try:
                page = context.new_page()
                page.goto(url)
                page.evaluate("document.fonts.ready")
                page.screenshot(path=str(SHOTS_1093 / f"form-{lang}-{width}.png"), full_page=False)
            finally:
                context.close()
