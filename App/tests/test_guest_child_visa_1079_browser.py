"""1079 S16: the visa field follows the nationality in a real browser.

S15 (the child-on-a-parent's-passport box) was removed on 2026-11-13 by owner
decision: every guest types their own document number. The last test pins
that a child's form shows the document box and no parent box.

Browser tests; run with UBYHOST_REQUIRE_BROWSER=1 so a missing Chromium fails instead of skipping.
Screenshots: UBYHOST_SHOTS_DIR=<dir> writes child-doc-<width>.png.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import pytest

from tests.test_guest_browser_e2e import Guest, browser, live_server  # noqa: F401
from tests.test_guest_form_input_browser import _open_url

__all__ = ["browser", "live_server"]

WIDTHS = [390, 768, 1280]
ADULT = "01011980"
ADULT_TEXT = "01.01.1980"


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February
        return day.replace(year=day.year - years, day=28)


def _text(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def _digits(day: date) -> str:
    return day.strftime("%d%m%Y")


TODAY = date.today()
CHILD = _years_before(TODAY, 2)

STATE_JS = """() => {
  const shown = id => { const el = document.getElementById(id); return !!el && getComputedStyle(el).display !== 'none'; };
  return {
    box: shown('child-wrap'),
    parent: shown('parent-doc-wrap'),
    doc: shown('doc-wrap'),
    checked: document.getElementById('child_in_passport').checked,
    docRequired: document.getElementById('doc_number').required,
    parentRequired: document.getElementById('parent_doc_number').required,
    focus: document.activeElement ? document.activeElement.id : '',
    birth: document.getElementById('birth_date').value,
  };
}"""

FORM_JS = """() => {
  const form = document.querySelector('form[data-guest-wizard]');
  return Array.from(new FormData(form).entries()).map(([k, v]) => [k, typeof v === 'string' ? v : 'file:' + v.name]);
}"""

BIRTH_TOP_JS = "() => document.getElementById('birth_date').getBoundingClientRect().top"

SET_BIRTH_JS = """value => {
  const el = document.getElementById('birth_date');
  el.value = value;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}"""

SET_STAY_FROM_JS = "value => { document.querySelector('input[name=\"stay_from\"]').value = value; }"

GAPS_JS = """() => {
  const doc = document.getElementById('doc-wrap');
  const box = document.getElementById('child-wrap');
  const visa = document.getElementById('visa_number').closest('.g-field');
  const rows = Array.from(doc.parentElement.children).filter(
    el => el.classList.contains('g-field') && getComputedStyle(el).display !== 'none');
  const rect = el => { const r = el.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; };
  const gaps = [];
  for (let i = 1; i < rows.length; i += 1) {
    gaps.push({ from: rows[i - 1].id || '', to: rows[i].id || (rows[i] === visa ? 'visa' : ''),
                gap: rows[i].getBoundingClientRect().top - rows[i - 1].getBoundingClientRect().bottom });
  }
  return {
    gaps: gaps,
    order: rows.map(el => el.id || (el === visa ? 'visa' : 'field')),
    doc: rect(doc), box: rect(box), visa: rect(visa),
    scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,
  };
}"""


def _state(page):
    return page.evaluate(STATE_JS)


def _page(browser, width=390, today=TODAY):
    """A page whose clock starts at noon on ``today``, so the script's "today"
    is the day these tests compute with, whatever the real time is."""
    page = browser.new_page(viewport={"width": width, "height": 812})
    page.clock.install(time=datetime(today.year, today.month, today.day, 12))
    return page


def _retype(page, digits):
    """Replace the birth date from the keyboard, as a guest would."""
    page.click("#birth_date")
    page.keyboard.press("Control+A")
    page.keyboard.type(digits)


def _leave(page):
    """Blur the birth date. Tab would open the nationality list over the fields below."""
    page.locator("#birth_date").blur()


def _shot(page, name):
    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / name), full_page=True)


def test_1079_s16_the_visa_field_follows_the_nationality(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079visa")
    page = _page(browser)
    try:
        page.goto(url)

        def pick(code):
            # The picker closes its list 120 ms after any blur and never cancels
            # that timer (known-issues), so let it run out before opening again.
            page.clock.run_for(200)
            page.click("#nationality_search")
            page.keyboard.press("Control+A")
            page.keyboard.type(code)
            page.locator("#nationality_list [role=option]").first.click()
            assert page.input_value("#nationality") == code

        pick("USA")
        assert page.locator("#visa_number").is_visible()
        page.fill("#visa_number", "V1234567")
        pick("DEU")
        assert not page.locator("#visa_number").is_visible(), "a German guest is asked for a visa"
        assert page.input_value("#visa_number") == "", "the typed visa number was kept behind the guest's back"
        pick("USA")
        assert page.locator("#visa_number").is_visible()
        assert page.input_value("#visa_number") == ""
        pick("CZE")
        assert not page.locator("#visa_number").is_visible()
    finally:
        page.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_a_childs_form_asks_for_their_own_document_and_has_no_parent_box(live_server, browser, monkeypatch, width):
    url = _open_url(live_server, monkeypatch, f"ownDoc{width}")
    page = _page(browser, width)
    guest = Guest(page, width)
    try:
        page.goto(url)
        page.fill("#first_name", "Synthetica")
        page.fill("#surname", "Testovic")
        _retype(page, _digits(CHILD))
        _leave(page)
        guest.pick_country("nationality", "POL")
        page.fill("#doc_number", "fc 4296103")
        assert page.locator("#doc_number").is_visible()
        assert page.locator("#child_in_passport").count() == 0
        assert page.locator("#parent_doc_number").count() == 0
        guest.check_layout(f"child at {width}px")
        guest.check_spacing(f"child at {width}px")
        _shot(page, f"child-doc-{width}.png")
        assert not guest.problems, guest.problems
    finally:
        page.close()
