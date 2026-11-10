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
