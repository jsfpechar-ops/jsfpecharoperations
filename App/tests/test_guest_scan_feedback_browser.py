"""1074: guest scan feedback, smaller photo, nationality prompt, error example.

Browser tests stub the /scan answer, so they need no OCR engine. They reuse the
fixtures of test_guest_ocr_geometry_browser.py (Max property, claimed form).
Skipped without Playwright unless UBYHOST_REQUIRE_BROWSER=1.
"""
import io
import json
import os
import re
import tempfile
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api  # noqa: F401
else:
    pytest.importorskip("playwright.sync_api")

from app import i18n, validation_i18n
from tests.browser_support import settle_motion
from tests.test_guest_ocr_geometry_browser import (  # noqa: F401  (fixtures)
    _goto_form,
    _page,
    base,
    browser,
    scan_world_on,
    world,
)

SCAN = re.compile(r"/scan\?")
JSON = "application/json"
VALUES = {
    "surname": "MUSTERMANN",
    "first_name": "ERIKA",
    "birth_date": "12081964",
    "nationality": "DEU",
    "doc_number": "C01X00T47",
}
TINY = {"name": "passport.jpg", "mimeType": "image/jpeg", "buffer": b"\xff\xd8\xff\xd9"}
NO_SIDEWAYS = "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "1074"
LABEL = os.environ.get("SHOT_LABEL", "run")


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_first_step_screenshot(base, world, browser, width):
    OUT.mkdir(parents=True, exist_ok=True)
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        settle_motion(page)
        assert page.evaluate(NO_SIDEWAYS) <= 1
        page.screenshot(path=str(OUT / f"{LABEL}-form-{width}.png"), full_page=True)
    finally:
        context.close()


def _answer(route, payload, status=200):
    route.fulfill(status=status, content_type=JSON, body=json.dumps(payload))


def test_scan_button_is_primary_like_next(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        label = page.locator("#ocr-scan label[for='ocr-scan-file']")
        assert "secondary" not in (label.get_attribute("class") or "")
        fill = "(el) => getComputedStyle(el).backgroundColor"
        nxt = page.locator(".g-wizard-nav .g-btn:not(.secondary)").first
        assert label.evaluate(fill) == nxt.evaluate(fill)
        assert page.locator("#ocr-scan-hint").is_visible()
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_working_text_spinner_then_chips_that_go_when_edited(base, world, browser, width):
    OUT.mkdir(parents=True, exist_ok=True)
    context, page = _page(browser, base, world, width)
    try:
        _goto_form(page, base, world)
        held = []
        page.route(SCAN, lambda route: held.append(route))
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_selector("#ocr-scan-status .g-spin")
        status = page.locator("#ocr-scan-status")
        assert "10 seconds" in status.inner_text()
        assert page.locator("#ocr-scan-file").is_disabled()
        held[0].fulfill(status=200, content_type=JSON,
                        body=json.dumps({"kind": "values", "values": VALUES}))
        page.wait_for_selector(".g-scan-chip")
        assert page.locator("#ocr-scan-status .g-spin").count() == 0
        assert page.locator(".g-scan-chip").count() == 5
        assert page.locator("#surname").input_value() == "MUSTERMANN"
        assert page.locator("#birth_date").input_value() == "12.08.1964"
        chips = page.locator(".g-scan-chip")
        assert chips.first.inner_text() == "Please check"
        assert "Please check" not in i18n.STRINGS["en"]["ocr_scan_done"]
        card = page.locator("[data-guest-step]").first.bounding_box()
        for i in range(chips.count()):
            if chips.nth(i).is_visible():
                box = chips.nth(i).bounding_box()
                assert box["x"] >= card["x"] - 0.5
                assert box["x"] + box["width"] <= card["x"] + card["width"] + 0.5
        assert page.evaluate(NO_SIDEWAYS) <= 1
        assert page.evaluate("document.activeElement && document.activeElement.id") != "nationality_search"
        page.wait_for_timeout(300)
        assert page.locator(".g-scan-chip").count() == 5, "a chip must stay until the guest edits"
        settle_motion(page)
        page.screenshot(path=str(OUT / f"{LABEL}-scanned-{width}.png"), full_page=True)
        page.fill("#surname", "MUSTERMANN2")
        assert page.locator(".g-scan-chip").count() == 4
    finally:
        context.close()


def test_unreadable_nationality_says_so_and_opens_the_picker(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        values = {k: v for k, v in VALUES.items() if k != "nationality"}
        page.route(SCAN, lambda route: _answer(route, {"kind": "values", "values": values}))
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_function(
            "() => document.activeElement && document.activeElement.id === 'nationality_search'"
        )
        assert page.locator("#nationality_list").is_visible()
        assert "choose it from the list" in page.locator("#ocr-scan-status").inner_text()
        assert page.locator("#nationality_error").is_visible()
        assert "choose it from the list" in page.locator("#nationality_error").inner_text()
        assert page.locator("#nationality").input_value() == ""
        assert page.locator("#nationality").locator(
            "xpath=ancestor::div[contains(@class,'g-field')][1]//span[contains(@class,'g-scan-chip')]"
        ).count() == 0
        assert page.locator(".g-scan-chip").count() == 4
    finally:
        context.close()


def test_unread_nationality_is_said_even_when_an_earlier_scan_filled_it(base, world, browser):
    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        answers = [VALUES, {k: v for k, v in VALUES.items() if k != "nationality"}]
        page.route(SCAN, lambda route: _answer(route, {"kind": "values", "values": answers.pop(0)}))
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_selector(".g-scan-chip")
        page.wait_for_function("() => !document.querySelector('#ocr-scan-file').disabled")
        page.locator("#surname").focus()
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_function(
            "() => document.querySelector('#ocr-scan-status').textContent.includes('choose it from the list')"
        )
        assert page.locator("#nationality").input_value() == "DEU"
        assert page.locator("#nationality_error").is_visible()
        assert "choose it from the list" in page.locator("#nationality_error").inner_text()
        assert page.evaluate("document.activeElement && document.activeElement.id") != "nationality_search"
        assert page.locator(".g-scan-chip").count() == 4
        page.wait_for_function("() => !document.querySelector('#ocr-scan-file').disabled")
        assert page.locator("#nationality_error").is_visible(), "clearing chips must keep the prompt"
    finally:
        context.close()


def _photo(size, orientation=None):
    from PIL import Image

    image = Image.effect_noise(size, 80).convert("RGB")
    out = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(out, "JPEG", quality=92, exif=exif)
    else:
        image.save(out, "JPEG", quality=92)
    return out.getvalue()


def test_big_photo_is_shrunk_upright_before_upload(base, world, browser):
    from PIL import Image

    original = _photo((3200, 2400), orientation=6)  # a phone held upright
    seen = []

    def grab(route):
        seen.append(route.request.post_data_buffer)
        _answer(route, {"kind": "error", "message": "stub"}, 422)

    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        page.route(SCAN, grab)
        page.set_input_files("#ocr-scan-file",
                             {"name": "big.jpg", "mimeType": "image/jpeg", "buffer": original})
        page.wait_for_function("() => document.querySelector('#ocr-scan-status').textContent.includes('stub')")
    finally:
        context.close()
    body = seen[0]
    assert len(body) < len(original) * 0.6
    sent = Image.open(io.BytesIO(body[body.index(b"\xff\xd8"):]))
    assert max(sent.size) <= 1568
    assert sent.size[1] > sent.size[0], "orientation 6 must come out upright (portrait)"


def test_unreadable_image_is_sent_as_it_was(base, world, browser):
    seen = []

    def grab(route):
        seen.append(route.request.post_data_buffer)
        _answer(route, {"kind": "error", "message": "stub"}, 422)

    context, page = _page(browser, base, world, 390)
    try:
        _goto_form(page, base, world)
        page.route(SCAN, grab)
        page.set_input_files("#ocr-scan-file", TINY)
        page.wait_for_function("() => document.querySelector('#ocr-scan-status').textContent.includes('stub')")
    finally:
        context.close()
    assert b"\xff\xd8\xff\xd9" in seen[0]


@pytest.mark.parametrize("lang", ["en", "cs", "de", "es", "fr", "uk"])
def test_birth_date_format_error_gives_an_example(lang):
    message = validation_i18n.guest_localize("Enter the full date as DD.MM.YYYY.", lang)
    assert "14.03.1961" in message


@pytest.mark.parametrize("lang", ["en", "cs", "de", "es", "fr", "uk"])
def test_scan_texts_exist_in_every_guest_language(lang):
    table = i18n.STRINGS[lang]
    for key in ("ocr_scan_working", "ocr_filled_chip", "ocr_nationality_missing"):
        assert table[key].strip()
    assert "10" in table["ocr_scan_working"]
