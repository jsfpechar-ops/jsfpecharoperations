"""0955 step 7: the property page's Save changes and Cancel, scenario by scenario.

Each test asserts the visible result and the persisted row after a reload.
Synthetic data only. Chromium only here; CI also runs webkit (untested locally).
Documented gaps: the validation-error path, the business editor, keyboard order
from the last field, Escape on the bar, and webkit.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import db
from tests.test_host_unsaved_changes_browser import NAME, _page, _stored, base, browser, host  # noqa: F401

SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0957"
BAR = ".savebar[data-for='property-settings-form']"
SAVE = f"{BAR} button[type=submit]"
CANCEL = f"{BAR} [data-unsaved-reset]"


def _edit_name(page, value):
    page.fill("#internal_name", value)


def test_save_persists_the_value_and_hides_the_bar(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    assert not page.locator(BAR).is_visible()
    _edit_name(page, "Save O1 name")
    assert page.locator(BAR).is_visible()
    with page.expect_navigation():
        page.locator(SAVE).click()
    assert _stored(host, "internal_name") == "Save O1 name"
    page.goto(f"{url}?view=settings&section=property&lang=en")
    assert page.input_value("#internal_name") == "Save O1 name"
    assert not page.locator(BAR).is_visible()
    page.context.close()
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (NAME, host["apartment"]))


def test_cancel_restores_every_field_and_persists_nothing(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    loaded = page.input_value("#internal_name")
    _edit_name(page, "Cancel O1 typed")
    assert page.locator(BAR).is_visible()
    page.locator(CANCEL).click()
    assert page.input_value("#internal_name") == loaded
    assert not page.locator(BAR).is_visible()
    assert page.url.split("#")[0].startswith(url)
    assert _stored(host, "internal_name") == NAME
    assert page.native_dialogs == []
    page.context.close()


def test_typing_the_original_value_back_hides_the_bar_and_asks_nothing(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    loaded = page.input_value("#internal_name")
    _edit_name(page, "Back O1 draft")
    assert page.locator(BAR).is_visible()
    _edit_name(page, loaded)
    assert not page.locator(BAR).is_visible()
    page.locator('a.airbnb-back[href="/apartments"]').click()
    assert page.locator("#unsaved-dialog").evaluate("d => d.open") is False
    assert "/apartments" in page.url
    assert _stored(host, "internal_name") == NAME
    page.context.close()


def test_an_outside_lock_time_saves_through_the_bar(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=lock&lang=en")
    loaded = page.input_value("#lock_checkin_hour")
    new = "23" if loaded != "23" else "22"
    page.select_option("#lock_checkin_hour", new)
    assert page.locator(BAR).is_visible()
    with page.expect_navigation():
        page.locator(SAVE).click()
    page.goto(f"{url}?view=settings&section=lock&lang=en")
    assert page.input_value("#lock_checkin_hour") == new
    assert page.locator(BAR).count() == 1 and not page.locator(BAR).is_visible()
    page.context.close()


@pytest.mark.parametrize("width,height", [(390, 844), (768, 1024), (1280, 900)])
def test_the_dirty_bar_is_visible_clear_of_the_tab_bar_and_help_bubble(browser, base, host, width, height):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    _edit_name(page, "Layout O1 draft")
    page.wait_for_timeout(200)
    bar = page.locator(BAR).bounding_box()
    save = page.locator(SAVE).bounding_box()
    assert bar and save
    assert save["x"] >= 0 and save["x"] + save["width"] <= width + 1
    assert page.evaluate("() => document.documentElement.scrollWidth") <= width
    tab = page.locator(".ui-tabbar")
    if tab.count() and tab.first.is_visible():
        assert bar["y"] + bar["height"] <= tab.first.bounding_box()["y"] + 1
    fab = page.locator(".havel-fab")
    if fab.count() and fab.first.is_visible():
        f = fab.first.bounding_box()
        overlap = not (save["x"] + save["width"] <= f["x"] or f["x"] + f["width"] <= save["x"]
                       or save["y"] + save["height"] <= f["y"] or f["y"] + f["height"] <= save["y"])
        assert not overlap, "the help bubble covers Save"
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / f"property-save-bar-{width}.png"), full_page=False)
    page.context.close()
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (NAME, host["apartment"]))


def test_an_invalid_field_keeps_the_edits_and_the_bar_and_cancel_clears_it(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    loaded_house = page.input_value("#addr_house_no")
    page.fill("#internal_name", "Invalid O1 edit")
    page.fill("#addr_house_no", "")
    page.locator(SAVE).click()
    page.wait_for_timeout(300)
    assert page.url.split("#")[0].startswith(url), "an invalid form must not post"
    invalid = page.evaluate("() => { const e = document.getElementById('addr_house_no'); return !e.checkValidity(); }")
    assert invalid, "house number is required in the browser"
    assert page.input_value("#internal_name") == "Invalid O1 edit"
    assert page.locator(BAR).is_visible()
    assert _stored(host, "internal_name") == NAME
    page.locator(CANCEL).click()
    assert page.input_value("#addr_house_no") == loaded_house
    assert page.input_value("#internal_name") == NAME
    assert not page.locator(BAR).is_visible()
    assert page.evaluate("() => document.getElementById('addr_house_no').checkValidity()")
    assert page.native_dialogs == []
    page.context.close()


def test_tab_from_the_last_field_reaches_cancel_then_save(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "Keys O1 edit")
    page.focus("#internal_name")
    stops = []
    for _ in range(200):
        page.keyboard.press("Tab")
        info = page.evaluate("""() => { const a = document.activeElement; const bar = document.querySelector(".savebar[data-for='property-settings-form']");
            return {cancel: a.matches('[data-unsaved-reset]'), save: a.matches('button[type=submit][form="property-settings-form"]'),
                    before: !!(bar.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_PRECEDING), label: a.tagName + '#' + (a.id || a.name || '')}; }""")
        if info["cancel"]:
            break
        stops.append(info["label"])
    assert info["cancel"], "Tab never reached Cancel after the form fields"
    assert stops, "Tab did not visit a form field first"
    page.keyboard.press("Tab")
    nxt = page.evaluate("() => document.activeElement.matches('button[type=submit][form=\"property-settings-form\"]')")
    assert nxt, "Tab after Cancel did not reach Save changes"
    page.context.close()


def test_escape_neither_discards_nor_leaves_the_page(browser, base, host):  # noqa: F811
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "Escape O1 edit")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert page.input_value("#internal_name") == "Escape O1 edit"
    assert page.locator(BAR).is_visible()
    assert page.url.split("#")[0].startswith(url)
    assert _stored(host, "internal_name") == NAME
    page.context.close()
