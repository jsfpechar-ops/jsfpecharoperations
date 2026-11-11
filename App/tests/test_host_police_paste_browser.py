"""1100: the police letter paste fills the boxes in place, and the send-timing options.

Steps 4 and 6 of brief 1100. The happy paths (paste with Turbo, the no-JS read and
its Save with no tick) live in ``test_host_police_letter_browser.py``; this file holds
the edge cases, the timing field and the review screenshots. Fake ``SAMPLE_*``
values and a fake client only. Set UBYHOST_SHOTS_1100 to a folder to write the
15 review screenshots.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import db
from app.ubyport_sample_pdf import SAMPLE_IDUB, SAMPLE_WS_PASSWORD, SAMPLE_WS_USER
from tests.browser_support import settle_motion
from tests.test_host_police_letter_browser import (  # noqa: F401
    FULL_LETTER,
    READ_BUTTON,
    SAVE_BUTTON,
    apartment_id,
    en,
    fits,
    live,
)
from tests.test_police_letter_flow import fake_client, host, no_client  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api  # noqa: F401
else:
    pytest.importorskip("playwright.sync_api")

WIDTHS = [390, 768, 1280]
SHOTS = os.environ.get("UBYHOST_SHOTS_1100")
STATUS = "#police-letter-status"
BOXES = ("uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark", "uby_name")


def shot(page, name, width, focus=None):
    if not SHOTS:
        return
    if focus:
        page.locator(focus).scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    settle_motion(page)
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(Path(SHOTS) / f"{name}-{width}.png"), full_page=True)


def values(page):
    return {name: page.input_value(f"#{name}") for name in BOXES}


def open_paste(page):
    page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")


def paste_text(page, text):
    open_paste(page)
    page.fill("#letter_text", text)
    page.focus("#letter_text")
    page.dispatch_event("#letter_text", "paste")


def wait_status(page):
    page.wait_for_function("(sel) => !!document.querySelector(sel).textContent.trim()", arg=STATUS, timeout=3000)
    return page.locator(STATUS).inner_text().strip()


@pytest.mark.parametrize("width", WIDTHS)
def test_unrelated_text_leaves_the_boxes_alone(live, no_client, width):  # noqa: F811
    page = live.open(width)
    page.goto(live.url)
    before = values(page)
    assert not page.locator(READ_BUTTON).is_visible()
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        paste_text(page, "Shopping list: milk, bread, two apples and some tea.")
    assert reply.value.status == 200
    status = wait_status(page)
    # Brief 1100 step 4: the failed text, or the "type the rest" line naming every box.
    assert status == en("police_letter.failed") or status.startswith(en("police_letter.type_rest", names="").split(":")[0]), status
    assert values(page) == before
    assert no_client == []


@pytest.mark.parametrize("width", [390, 1280])
@pytest.mark.parametrize("answer", ["abort", "html"])
def test_a_failed_read_says_so_and_shows_the_button(live, no_client, width, answer):  # noqa: F811
    page = live.open(width)
    page.goto(live.url)
    before = values(page)
    if answer == "abort":
        page.route("**/police-letter", lambda route: route.abort())
    else:  # a login or expired-form redirect lands as a 200 HTML page
        page.route("**/police-letter", lambda route: route.fulfill(
            status=200, content_type="text/html", body="<!doctype html><title>Log in</title>"))
    paste_text(page, FULL_LETTER)
    assert wait_status(page) == en("police_letter.read_failed")
    page.locator(READ_BUTTON).wait_for(state="visible")
    assert values(page) == before
    assert fits(page)
    assert no_client == []


@pytest.mark.parametrize("width", [390, 1280])
def test_a_typed_box_is_kept_and_focus_stays_in_the_paste_box(live, no_client, width):  # noqa: F811
    page = live.open(width)
    page.goto(live.url)
    page.fill("#uby_ws_user", "UBY-WS_TYPED")
    with page.expect_response(lambda r: r.url.endswith("/police-letter")):
        paste_text(page, FULL_LETTER)
    page.wait_for_function(f"() => document.getElementById('uby_idub').value === '{SAMPLE_IDUB}'", timeout=2000)
    assert page.input_value("#uby_ws_user") == "UBY-WS_TYPED"
    assert page.input_value("#uby_ws_password") == SAMPLE_WS_PASSWORD
    assert page.evaluate("() => document.activeElement.id") == "letter_text"
    page.evaluate("() => { for (const k of ['localStorage', 'sessionStorage']) if (window[k].length) throw k; }")
    assert SAMPLE_WS_PASSWORD not in page.url
    assert no_client == []


def _hours_visible(page):
    return page.evaluate("() => { const f = document.getElementById('submit_after_hours').closest('.field');"
                         " return !f.hidden && f.getClientRects().length > 0; }")


def _hint(page):
    return page.locator("#automation_mode-hint").inner_text().strip()


@pytest.mark.parametrize("width", WIDTHS)
def test_the_hours_show_only_for_the_delay_and_each_option_has_a_hint(live, no_client, width):  # noqa: F811
    db.execute("UPDATE apartment SET automation_mode = 'manual', submit_after_hours = 7 WHERE id = ?",
               (apartment_id(),))
    page = live.open(width)
    page.goto(live.plain + "?view=settings&section=automation&lang=en#automation")
    assert page.get_attribute("#automation_mode", "aria-describedby") == "automation_mode-hint"
    assert not _hours_visible(page)
    assert _hint(page) == en("automation.mode_hint.manual")
    shot(page, "timing-manual", width, "#automation")
    page.select_option("#automation_mode", "scheduled")
    assert _hours_visible(page)
    assert _hint(page) == en("automation.mode_hint.scheduled")
    assert page.locator('label[for="submit_after_hours"]').inner_text().strip() == en("automation.hours_delay")
    assert fits(page)
    shot(page, "timing-delay", width, "#automation")
    page.select_option("#automation_mode", "immediate")
    assert not _hours_visible(page)
    assert _hint(page) == en("automation.mode_hint.immediate")

    # Save with "manual": the hidden, disabled hours are not posted (as on main, where the field was
    # already disabled). The server then stores its default of 24 (admin.py _apartment_values, unchanged
    # by 1100); the hours only matter for the delay option.
    page.select_option("#automation_mode", "manual")
    page.fill("#uby_contact", "+420 777 000 999")  # back on the loaded option, so one other edit makes the form dirty
    posted = []
    page.on("request", lambda r: posted.append(r.post_data or "") if r.method == "POST" else None)
    with page.expect_navigation():
        page.locator(SAVE_BUTTON).click()
    row = db.query_one("SELECT automation_mode, submit_after_hours FROM apartment WHERE id = ?", (apartment_id(),))
    assert row["automation_mode"] == "manual" and row["submit_after_hours"] == 24
    db.execute("UPDATE apartment SET uby_contact = NULL WHERE id = ?", (apartment_id(),))
    assert posted and "submit_after_hours" not in posted[0]
    assert no_client == []


@pytest.mark.parametrize("width", [390, 1280])
def test_without_javascript_the_hours_always_show(live, no_client, width):  # noqa: F811
    db.execute("UPDATE apartment SET automation_mode = 'immediate' WHERE id = ?", (apartment_id(),))
    page = live.open(width, js=False)
    page.goto(live.plain + "?view=settings&section=automation&lang=en#automation")
    assert _hours_visible(page)
    assert page.locator('label[for="submit_after_hours"]').inner_text().strip() == en("automation.hours_delay")
    assert _hint(page) == en("automation.mode_hint.immediate")
    db.execute("UPDATE apartment SET automation_mode = 'manual' WHERE id = ?", (apartment_id(),))
    assert no_client == []


@pytest.mark.parametrize("width", WIDTHS)
def test_review_screenshots(live, no_client, width):  # noqa: F811
    """police-empty, police-after-paste and leave-dialog (the timing shots come from the test above)."""
    page = live.open(width)
    page.goto(live.url)
    open_paste(page)
    shot(page, "police-empty", width, "#ubyport")
    with page.expect_response(lambda r: r.url.endswith("/police-letter")):
        paste_text(page, FULL_LETTER)
    page.wait_for_function(f"() => document.getElementById('uby_ws_user').value === '{SAMPLE_WS_USER}'", timeout=2000)
    assert fits(page)
    shot(page, "police-after-paste", width, STATUS)
    page.locator("a.airbnb-back").click()
    page.wait_for_function("() => document.getElementById('unsaved-dialog').open", timeout=3000)
    shot(page, "leave-dialog", width)
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert no_client == []
