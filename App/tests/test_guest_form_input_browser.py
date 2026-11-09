"""2026-11-09 QA, new-guest form input: Enter, rejected text, a dropped connection, no JavaScript.

Browser tests; run with UBYHOST_REQUIRE_BROWSER=1 so a missing Chromium fails instead of skipping.
Screenshots: UBYHOST_SHOTS_DIR=<dir> writes guest-input-<lang>-<width>.png.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest

from app import i18n, mail
from tests.test_guest_browser_e2e import Guest, _fee_seed, browser, live_server  # noqa: F401

__all__ = ["browser", "live_server"]


def _shot(page, name):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / name), full_page=True)


def _fill_step_one(page, guest, first="Synthetica", surname="Testovic"):
    page.fill("#first_name", first)
    page.fill("#surname", surname)
    page.click("#birth_date")
    page.keyboard.type("01011980")
    guest.pick_country("nationality", "CZE")
    page.fill("#doc_number", "SYN1109X")


def _fill_step_two(page, guest, city="Testov"):
    page.fill("#res_street", "Examplova 5")
    page.fill("#res_city", city)
    page.evaluate("() => { document.querySelector('#res_country').value = 'CZE'; }")


def _open_url(live_server, monkeypatch, part, lang="en"):
    from app import config

    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    token = f"browser-1109-{part}-{secrets.token_hex(4)}"
    stay = _fee_seed(token, signed=False)
    return f"{live_server}/l/{token}/{stay}/new?lang={lang}"


def _left_the_form(page):
    page.wait_for_function("() => !location.pathname.endsWith('/new')", timeout=10000)


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_1109_enter_continues_and_saves_never_the_language_button(live_server, browser, monkeypatch, lang):
    """The first submit button in page order was a language button. Enter now
    presses the visible step's own button and never posts to /relang."""
    url = _open_url(live_server, monkeypatch, "enter", lang)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    guest = Guest(page, 390, lang=lang)
    try:
        page.goto(url)
        _fill_step_one(page, guest)
        first_step = guest.step()
        page.press("#doc_number", "Enter")
        page.wait_for_timeout(900)
        assert guest.step() != first_step, "Enter did not continue to the next step"
        assert page.get_attribute("html", "lang") == lang
        _fill_step_two(page, guest)
        page.press("#res_city", "Enter")
        page.wait_for_timeout(900)
        guest.sign()
        page.check("#legal_ack")
        page.press("#legal_ack", "Enter")
        _left_the_form(page)
        assert not [u for u in posts if "/relang" in u], posts
        assert any("/save" in u for u in posts), posts
        assert page.get_attribute("html", "lang") == lang
    finally:
        page.close()


def test_1109_enter_without_javascript_saves_not_the_language_button(live_server, browser, monkeypatch):
    """No script: the hidden default button comes before the language buttons,
    so Enter posts the form to Save (which says what is missing), not /relang."""
    url = _open_url(live_server, monkeypatch, "enternojs")
    context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 812})
    page = context.new_page()
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    try:
        page.goto(url)
        page.fill("#first_name", "Synthetica")
        page.fill("#surname", "Testovic")
        page.fill("#birth_date", "01.01.1980")
        page.fill("#doc_number", "SYN1109X")
        page.fill("#res_street", "Examplova 5")
        page.fill("#res_city", "Testov")
        page.select_option("#nationality", "CZE")
        page.select_option("#res_country", "CZE")
        page.check("#legal_ack")
        page.press("#doc_number", "Enter")
        page.wait_for_load_state()
        assert any("/save" in u for u in posts), posts
        assert not [u for u in posts if "/relang" in u], posts
    finally:
        context.close()


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_1109_a_script_name_is_kept_and_named_in_its_own_language(live_server, browser, monkeypatch, lang):
    """Names and a city in another alphabet are still refused (UbyPort takes
    Latin letters only) but come back as typed, and the summary says which
    field and why instead of "City is required"."""
    url = _open_url(live_server, monkeypatch, "latin", lang)
    t = i18n.translator(lang)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    guest = Guest(page, 390, lang=lang)
    try:
        page.goto(url)
        _fill_step_one(page, guest, first="Иван", surname="王小明")
        guest.next()
        _fill_step_two(page, guest, city="Москва")
        guest.next()
        guest.sign()
        page.check("#legal_ack")
        page.click("[data-guest-save]")
        page.wait_for_selector(".g-err li")
        summary = page.inner_text(".g-err")
        for key in ("first_name", "surname", "res_city"):
            assert t("latin_only_error", field=t(key)) in summary, (lang, key, summary)
        assert "City is required" not in summary and "Město je povinné" not in summary
        assert page.input_value("#first_name") == "Иван"
        assert page.input_value("#surname") == "王小明"
        assert page.input_value("#doc_number") == "SYN1109X"
        assert page.input_value("#nationality") == "CZE"
        page.locator(".g-err li a").first.click()
        page.wait_for_timeout(900)
        assert page.input_value("#first_name") == "Иван"
        guest.next() if guest.step() == t("your_details") else None
        assert page.input_value("#res_city") == "Москва"
        for width in (390, 768, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            _shot(page, f"guest-input-latin-{lang}-{width}.png")
    finally:
        page.close()


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_1109_a_dropped_connection_keeps_the_form_and_says_so(live_server, browser, monkeypatch, lang):
    url = _open_url(live_server, monkeypatch, "net", lang)
    t = i18n.translator(lang)
    page = browser.new_page(viewport={"width": 390, "height": 812})
    guest = Guest(page, 390, lang=lang)
    try:
        page.goto(url)
        _fill_step_one(page, guest)
        guest.next()
        _fill_step_two(page, guest)
        guest.next()
        guest.sign()
        page.check("#legal_ack")
        page.context.set_offline(True)
        page.click("[data-guest-save]")
        page.wait_for_selector("#save-net-error:not([hidden])")
        assert page.inner_text("#save-net-error").strip() == t("save_network_error")
        assert page.input_value("#first_name") == "Synthetica"
        assert page.input_value("#res_city") == "Testov"
        assert page.is_checked("#legal_ack")
        assert page.locator("[data-guest-save]").is_enabled()
        assert page.url.endswith("/new?lang=" + lang), page.url
        for width in (390, 768, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            _shot(page, f"guest-input-offline-{lang}-{width}.png")
        page.context.set_offline(False)
        page.wait_for_function("() => document.getElementById('save-net-error').hidden")
        page.click("[data-guest-save]")
        _left_the_form(page)
    finally:
        page.close()


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_1109_without_javascript_the_form_says_javascript_is_needed(live_server, browser, monkeypatch, lang):
    url = _open_url(live_server, monkeypatch, "nojs", lang)
    for width in (390, 768, 1280):
        context = browser.new_context(java_script_enabled=False, viewport={"width": width, "height": 900})
        page = context.new_page()
        try:
            page.goto(url)
            assert i18n.translator(lang)("nojs_needed") in page.inner_text("#guest-form")
            note = page.locator(".g-nojs-note")
            assert note.is_visible()
            assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
            _shot(page, f"guest-input-nojs-{lang}-{width}.png")
        finally:
            context.close()
