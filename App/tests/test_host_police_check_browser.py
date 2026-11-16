"""A4: the police setup warnings in a real browser at 390, 768 and 1280 px (0 skipped)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import db
from tests.test_host_police_letter_browser import (  # noqa: F401
    FULL_LETTER, READ_BUTTON, apartment_id, live,
)
from tests.test_police_letter_flow import host, fake_client, no_client  # noqa: F401
from app.ubyport_sample_pdf import SAMPLE_IDUB, SAMPLE_WS_USER

SHOTS = os.environ.get("UBYHOST_A4_SHOTS", "")
WIDTHS = (390, 768, 1280)
BRACKET_FULL_LETTER = FULL_LETTER.replace(
    "BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,", "FIKTVNÍ 1234/56 - BYT A3.3 [A33]"
)


def _seed():
    db.update("apartment", apartment_id(), {
        "uby_ws_user": SAMPLE_WS_USER, "uby_mark": "DEMO1", "uby_idub": SAMPLE_IDUB,
        "uby_name": "Penzion Letter",
    })


def _shot(page, name, width):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}-{width}.png"), full_page=False)


@pytest.mark.parametrize("width", WIDTHS)
def test_saved_page_shows_the_warnings_without_sideways_scroll(live, width):
    _seed()
    page = live.open(width)
    page.goto(live.url)
    page.locator("#ubyport").scroll_into_view_if_needed()
    for code in ("mark_is_login_suffix", "name_address", "first_filing"):
        assert page.locator(f'[data-police-check-code="{code}"]').is_visible(), code
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    _shot(page, "police-check-saved", width)


@pytest.mark.parametrize("width", WIDTHS)
def test_paste_with_javascript_names_the_printed_short_name(live, width):
    _seed()
    page = live.open(width)
    page.goto(live.url)
    page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")
    page.fill("#letter_text", BRACKET_FULL_LETTER)
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        page.dispatch_event("#letter_text", "paste")
    assert reply.value.status == 200
    page.wait_for_function("document.querySelector('[data-letter-status]').textContent.includes('Filled from your letter')", timeout=5000)
    page.wait_for_function("document.querySelectorAll('[data-letter-warning]').length === 1", timeout=5000)
    assert "A33" in page.locator("[data-letter-warning]").inner_text()
    assert "No report accepted yet" not in page.locator("[data-letter-status]").inner_text()
    assert page.locator("body").inner_text().count("No report accepted yet") == 1
    gap = page.evaluate("() => document.querySelector('[data-letter-warning]').getBoundingClientRect().top - document.querySelector('[data-letter-status]').getBoundingClientRect().bottom")
    assert gap >= 12, f"status to warning gap {gap}px"
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    _shot(page, "police-check-paste", width)
