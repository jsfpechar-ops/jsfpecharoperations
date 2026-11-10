"""1079: S15 the child-on-a-parent's-passport box only for under-18s; S16 the visa field in a real browser.

The script only ever sets ``#child-wrap``'s ``style.display``. It never unticks
the box and never changes a value, so what is posted is what main posts.

Browser tests; run with UBYHOST_REQUIRE_BROWSER=1 so a missing Chromium fails instead of skipping.
Screenshots: UBYHOST_SHOTS_DIR=<dir> writes adult-<width>.png and child-<width>.png.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
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


def _page(browser, width=390):
    return browser.new_page(viewport={"width": width, "height": 812})


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


def test_1079_typing_an_adult_never_shows_the_box_and_a_child_shows_it_in_place(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079type")
    page = _page(browser)
    try:
        page.goto(url)
        start = _state(page)
        assert not start["box"], "an empty birth date shows the child box"
        assert not start["parent"] and start["docRequired"] and not start["checked"]

        ends = []
        for _ in range(2):  # the same sequence twice ends in the same state
            page.click("#birth_date")
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            seen = []
            for key in ADULT:
                page.keyboard.type(key)
                state = _state(page)
                seen.append(state["birth"])
                assert not state["box"], f"the box flashed at {state['birth']!r}"
                assert not state["parent"] and state["docRequired"]
            assert "01.01.19" in seen and seen[-1] == ADULT_TEXT, seen

            # A child: nothing moves until the date is complete, then the box
            # appears below the field and the caret stays where it was.
            page.keyboard.press("Control+A")
            digits = _digits(CHILD)
            for key in digits[:-1]:
                page.keyboard.type(key)
                assert not _state(page)["box"], "the box appeared on a half-typed date"
            top = page.evaluate(BIRTH_TOP_JS)
            page.keyboard.type(digits[-1])
            state = _state(page)
            assert state["birth"] == _text(CHILD)
            assert state["box"], "a two-year-old does not get the child box"
            assert state["focus"] == "birth_date", state
            assert abs(page.evaluate(BIRTH_TOP_JS) - top) < 1, "the birth date field moved"
            assert not state["checked"] and state["docRequired"] and not state["parent"]

            # Back to an adult: the box stays while the date is half typed, then hides.
            page.keyboard.press("Control+A")
            for key in ADULT[:-1]:
                page.keyboard.type(key)
                assert _state(page)["box"], "the box flickered away on a half-typed date"
            page.keyboard.type(ADULT[-1])
            state = _state(page)
            assert not state["box"] and state["focus"] == "birth_date", state
            ends.append(state)
        assert ends[0] == ends[1], ends

        # "01.01.19" left as it is reads as 2019: a child. Decided on blur.
        page.keyboard.press("Control+A")
        page.keyboard.type("010119")
        assert not _state(page)["box"]
        page.keyboard.press("Tab")
        state = _state(page)
        assert state["birth"] == "01.01.19" and state["box"], state

        page.click("#birth_date")
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.press("Tab")
        state = _state(page)
        assert state["birth"] == "" and not state["box"], state
    finally:
        page.close()


def test_1079_a_ticked_box_is_never_hidden_and_its_own_change_never_hides_it(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079tick")
    page = _page(browser)
    try:
        page.goto(url)
        _retype(page, _digits(CHILD))
        page.check("#child_in_passport")
        state = _state(page)
        assert state["box"] and state["parent"] and state["parentRequired"] and not state["docRequired"]

        _retype(page, ADULT)
        _leave(page)
        state = _state(page)
        assert state["birth"] == ADULT_TEXT
        assert state["box"] and state["checked"], "a ticked box was hidden or unticked"
        assert state["parent"] and state["parentRequired"] and not state["docRequired"]

        # Unticking is the guest's own act on the box: it stays under the finger.
        page.uncheck("#child_in_passport")
        state = _state(page)
        assert state["box"], "the box vanished when it was unticked"
        assert not state["checked"] and state["docRequired"] and not state["parentRequired"]
        assert state["doc"] and not state["parent"]
        page.check("#child_in_passport")
        assert _state(page)["checked"] and _state(page)["box"]
        page.uncheck("#child_in_passport")
        assert _state(page)["box"]

        # Only the next look at the birth date hides it.
        _retype(page, "02011980")
        state = _state(page)
        assert state["birth"] == "02.01.1980" and not state["box"] and not state["checked"], state
        assert state["docRequired"]
    finally:
        page.close()


def test_1079_the_reference_day_is_the_earlier_of_arrival_and_today(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079ref")
    page = _page(browser)
    try:
        page.goto(url)
        past = (TODAY - timedelta(days=30)).isoformat()
        future = (TODAY + timedelta(days=30)).isoformat()

        def box(born: date, stay_from: str) -> bool:
            page.evaluate(SET_STAY_FROM_JS, stay_from)
            page.evaluate(SET_BIRTH_JS, _text(born))
            return _state(page)["box"]

        almost = _years_before(TODAY - timedelta(days=360), 17)
        assert box(almost, past), "17 years and 360 days: still a child"
        assert not box(_years_before(TODAY, 30), future), "a 30-year-old with a future arrival"

        # 18 since ten days ago: a child on the arrival day 30 days ago, an
        # adult when the arrival is today or still to come.
        just = _years_before(TODAY - timedelta(days=10), 18)
        assert box(just, past), "under 18 on the arrival day"
        assert not box(just, TODAY.isoformat())
        assert not box(just, future), "today is the earlier day"
        assert not box(just, "not-a-date")

        # The 18th birthday itself is an adult; the day before is a child.
        assert not box(_years_before(TODAY, 18), TODAY.isoformat())
        assert box(_years_before(TODAY, 18) + timedelta(days=1), TODAY.isoformat())

        # Unknown day or month: by the year alone, and generously.
        assert box(date(TODAY.year - 18, 1, 1), TODAY.isoformat()) is False
        page.evaluate(SET_BIRTH_JS, f"00.00.{TODAY.year - 18}")
        assert _state(page)["box"], "an unknown day in the year of the 18th birthday"
        page.evaluate(SET_BIRTH_JS, f"00.00.{TODAY.year - 19}")
        assert not _state(page)["box"]
        page.evaluate(SET_BIRTH_JS, "31.02.2020")
        assert not _state(page)["box"], "a date that does not exist"
    finally:
        page.close()


def test_1079_a_scanned_or_pasted_birth_date_moves_the_box(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079scan")
    page = _page(browser)
    try:
        page.goto(url)
        # _ocr_scan.html sets the value, then dispatches input and change.
        page.evaluate(SET_BIRTH_JS, _text(CHILD))
        assert _state(page)["box"]
        page.evaluate(SET_BIRTH_JS, ADULT_TEXT)
        assert not _state(page)["box"]

        # initBirthDate's paste handler writes the value with no input event.
        page.click("#birth_date")
        page.evaluate(
            """text => {
              const el = document.getElementById('birth_date');
              const data = new DataTransfer();
              data.setData('text', text);
              el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
            }""",
            _text(CHILD),
        )
        page.wait_for_function(
            "() => getComputedStyle(document.getElementById('child-wrap')).display !== 'none'", timeout=3000
        )
        state = _state(page)
        assert state["birth"] == _text(CHILD) and not state["checked"], state
    finally:
        page.close()


def test_1079_s16_the_visa_field_follows_the_nationality(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079visa")
    page = _page(browser)
    try:
        page.goto(url)

        def pick(code):
            # Picking a second country: the list sometimes stays shut on the
            # first try in headless Chromium, so try again rather than wait 30 s.
            option = page.locator("#nationality_list [role=option]").first
            for attempt in range(4):
                page.locator("#nationality_search").blur()
                page.click("#nationality_search")
                page.keyboard.press("Control+A")
                page.keyboard.type(code)
                try:
                    option.click(timeout=2500)
                    break
                except Exception:
                    if attempt == 3:
                        raise
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
def test_1079_the_hidden_box_leaves_no_gap_and_the_shown_box_sits_in_order(live_server, browser, monkeypatch, width):
    url = _open_url(live_server, monkeypatch, f"1079geo{width}")
    page = _page(browser, width)
    guest = Guest(page, width)
    try:
        page.goto(url)
        page.fill("#first_name", "Synthetica")
        page.fill("#surname", "Testovic")
        _retype(page, ADULT)
        guest.pick_country("nationality", "USA")
        page.fill("#doc_number", "SYN1079X")
        page.locator("#doc_number").blur()

        hidden = page.evaluate(GAPS_JS)
        assert hidden["scrollWidth"] <= hidden["innerWidth"], hidden
        assert "child-wrap" not in hidden["order"], hidden["order"]
        at = hidden["order"].index("doc-wrap")
        assert hidden["order"][at + 1] == "visa", hidden["order"]
        doc_to_visa = hidden["gaps"][at]["gap"]
        others = [g["gap"] for i, g in enumerate(hidden["gaps"]) if i != at]
        assert others, "no other neighbouring fields to compare with"
        assert abs(doc_to_visa - others[-1]) <= 1, hidden["gaps"]
        guest.check_layout(f"adult at {width}px")
        guest.check_spacing(f"adult at {width}px")
        _shot(page, f"adult-{width}.png")

        _retype(page, _digits(CHILD))
        page.locator("#birth_date").blur()
        shown = page.evaluate(GAPS_JS)
        assert shown["scrollWidth"] <= shown["innerWidth"], shown
        at = shown["order"].index("doc-wrap")
        assert shown["order"][at + 1 : at + 3] == ["child-wrap", "visa"], shown["order"]
        assert shown["doc"]["bottom"] <= shown["box"]["top"], shown
        assert shown["box"]["bottom"] <= shown["visa"]["top"], shown
        assert shown["box"]["bottom"] > shown["box"]["top"]
        assert abs(shown["gaps"][at]["gap"] - shown["gaps"][at + 1]["gap"]) <= 1, shown["gaps"]
        guest.check_layout(f"child at {width}px")
        guest.check_spacing(f"child at {width}px")
        _shot(page, f"child-{width}.png")
        assert not guest.problems, guest.problems
    finally:
        page.close()


def test_1079_a_box_ticked_by_a_restored_page_is_shown(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079restore")
    page = _page(browser)
    try:
        page.goto(url)
        _retype(page, ADULT)
        _leave(page)
        assert not _state(page)["box"]
        # The back button restores a ticked box without any event.
        page.evaluate(
            """() => {
              document.getElementById('child_in_passport').checked = true;
              window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
            }"""
        )
        state = _state(page)
        assert state["box"] and state["parent"] and state["parentRequired"] and state["checked"], state
        assert not state["docRequired"] and not state["doc"]
    finally:
        page.close()


def test_1079_a_server_error_page_with_the_box_ticked_shows_it_for_an_adult(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079error")
    page = _page(browser)
    try:
        page.goto(url)
        page.fill("#first_name", "Synthetica")
        page.fill("#surname", "Testovic")
        _retype(page, _digits(CHILD))
        page.check("#child_in_passport")
        _retype(page, ADULT)
        _leave(page)
        # form.submit() skips the browser's own checks, so the server answers:
        # the parent's number is missing, and the page comes back with the box ticked.
        with page.expect_navigation():
            page.evaluate("() => document.querySelector('form[data-guest-wizard]').submit()")
        assert page.locator("#child_in_passport").count() == 1
        state = _state(page)
        assert state["birth"] == ADULT_TEXT, state
        assert state["checked"] and state["box"], "a ticked box came back hidden"
        assert state["parent"] and state["parentRequired"] and not state["docRequired"]
    finally:
        page.close()


def test_1079_without_javascript_the_box_is_visible_as_before(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079nojs")
    context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 812})
    page = context.new_page()
    try:
        page.goto(url)
        page.fill("#birth_date", ADULT_TEXT)
        assert page.locator("#child-wrap").is_visible()
        assert page.locator("#child_in_passport").is_visible()
        assert page.get_attribute("#child-wrap", "style") is None
    finally:
        context.close()


def test_1079_hiding_and_showing_the_box_posts_the_same_form(live_server, browser, monkeypatch):
    url = _open_url(live_server, monkeypatch, "1079post")
    page = _page(browser)
    guest = Guest(page, 390)
    try:
        page.goto(url)
        page.fill("#first_name", "Synthetica")
        page.fill("#surname", "Testovic")
        guest.pick_country("nationality", "USA")
        page.fill("#doc_number", "SYN1079X")
        page.fill("#visa_number", "V1234567")

        def posted():
            return [pair for pair in page.evaluate(FORM_JS) if pair[0] != "birth_date"]

        def birth():
            return [pair for pair in page.evaluate(FORM_JS) if pair[0] == "birth_date"]

        _retype(page, ADULT)
        _leave(page)
        adult = posted()
        assert not _state(page)["box"] and birth() == [["birth_date", ADULT_TEXT]]
        assert "child_in_passport" not in [k for k, _ in adult]
        assert ["doc_number", "SYN1079X"] in adult and ["visa_number", "V1234567"] in adult

        _retype(page, _digits(CHILD))
        _leave(page)
        assert _state(page)["box"] and birth() == [["birth_date", _text(CHILD)]]
        assert posted() == adult, "showing the box changed what is posted"

        _retype(page, ADULT)
        _leave(page)
        assert not _state(page)["box"]
        assert posted() == adult, "hiding the box changed what is posted"

        # The child case: a ticked box posts the same whether the date says child or adult.
        _retype(page, _digits(CHILD))
        page.check("#child_in_passport")
        page.fill("#parent_doc_number", "PARENT79")
        child = posted()
        assert ["child_in_passport", "1"] in child and ["parent_doc_number", "PARENT79"] in child
        _retype(page, ADULT)
        _leave(page)
        assert _state(page)["box"] and _state(page)["checked"]
        assert posted() == child
        _retype(page, _digits(CHILD))
        _leave(page)
        assert posted() == child
    finally:
        page.close()
