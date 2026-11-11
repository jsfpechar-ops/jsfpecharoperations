"""1086/1100: the warning before the "Read the letter" button throws away unsaved edits.

1100: with JavaScript a paste fills the boxes in place, so the button is hidden; it
shows again when the in-place read fails, and then a click reloads the editor, so a
host with unsaved edits or a typed password is asked first. Fake ``SAMPLE_*``
values and a fake client only.
"""
from __future__ import annotations

import os

import pytest

from app.ubyport_sample_pdf import SAMPLE_IDUB
from tests.test_host_police_letter_browser import READ_BUTTON, en, live  # noqa: F401
from tests.test_police_letter_flow import LETTER, fake_client, host, no_client  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api  # noqa: F401
else:
    pytest.importorskip("playwright.sync_api")

WIDTH = 1280
SAVE_ROW = ".savebar[data-for='property-settings-form']"
DIRTY = "() => document.querySelector('#property-settings-form').dataset.dirty === '1'"
STATUS = "#police-letter-status"


def _open(live, answers):  # noqa: F811
    """A page whose dialogs are recorded as (type, message) and answered from ``answers``."""
    page = live.open(WIDTH)
    seen = []

    def on_dialog(dialog):
        seen.append((dialog.type, dialog.message))
        if answers.pop(0) if answers else True:
            dialog.accept()
        else:
            dialog.dismiss()

    page.on("dialog", on_dialog)
    page.goto(live.url)
    page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")  # 1099: may start open
    return page, seen


def _failed_paste(page):
    """The in-place read fails (server gone): the status says so and the button shows again."""
    page.route("**/police-letter", lambda route: route.abort())
    assert not page.locator(READ_BUTTON).is_visible()
    page.fill("#letter_text", LETTER)
    page.dispatch_event("#letter_text", "paste")
    page.wait_for_function("(sel) => !!document.querySelector(sel).textContent.trim()", arg=STATUS)
    assert page.locator(STATUS).inner_text().strip() == en("police_letter.read_failed")
    page.locator(READ_BUTTON).wait_for(state="visible")
    page.unroute("**/police-letter")


def _read_page(page):
    """The page the button's post answers with (the no-JS read), opened with JS on."""
    page.evaluate("(text) => { document.getElementById('letter_text').value = text; }", LETTER)
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        page.evaluate("() => HTMLFormElement.prototype.submit.call(document.getElementById('police-letter-form'))")
    assert reply.value.status == 422
    page.wait_for_function(f"() => document.getElementById('uby_idub').value === '{SAMPLE_IDUB}'")


def test_unsaved_edits_ask_before_the_letter_is_read(live, no_client):  # noqa: F811
    warning = en("police_letter.discard_warning")
    page, seen = _open(live, [False, True])
    page.fill("#uby_contact", "Typed And Not Saved")
    page.wait_for_function(DIRTY)
    _failed_paste(page)
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)

    # Cancel: the page stays and the typed value is kept.
    page.locator(READ_BUTTON).click()
    page.wait_for_timeout(400)
    assert seen == [("confirm", warning)]
    assert posts == []
    assert page.input_value("#uby_contact") == "Typed And Not Saved"
    assert LETTER.strip() in page.input_value("#letter_text").replace("\r\n", "\n")

    # Accept: the read page loads with the boxes filled, and leaving for it does not warn a second time.
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        page.locator(READ_BUTTON).click()
    assert reply.value.status == 422
    page.wait_for_function(f"() => document.getElementById('uby_idub').value === '{SAMPLE_IDUB}'")
    page.wait_for_timeout(400)
    assert seen == [("confirm", warning), ("confirm", warning)]
    assert page.locator("#police-letter-check").count() == 0
    assert no_client == []


def test_a_typed_password_asks_and_a_clean_page_does_not(live, no_client):  # noqa: F811
    warning = en("police_letter.discard_warning")
    page, seen = _open(live, [False])
    page.fill("#uby_ws_password", "typed-by-hand-1086")
    _failed_paste(page)
    page.locator(READ_BUTTON).click()
    page.wait_for_timeout(400)
    assert seen == [("confirm", warning)]
    assert page.input_value("#uby_ws_password") == "typed-by-hand-1086"

    clean, clean_seen = _open(live, [])
    _failed_paste(clean)
    with clean.expect_response(lambda r: r.url.endswith("/police-letter")):
        clean.locator(READ_BUTTON).click()
    clean.wait_for_function(f"() => document.getElementById('uby_idub').value === '{SAMPLE_IDUB}'")
    clean.wait_for_timeout(400)
    assert clean_seen == []
    assert no_client == []


def test_the_read_page_starts_dirty_and_warns_on_leaving(live, no_client):  # noqa: F811
    page, seen = _open(live, [False])
    _read_page(page)
    assert seen == []
    form = page.locator("#property-settings-form")
    assert form.get_attribute("data-dirty-start") == "1"
    assert not page.locator(READ_BUTTON).is_visible()
    # Nothing typed: the Save row shows at load.
    page.wait_for_function(DIRTY)
    assert page.locator(SAVE_ROW).is_visible()
    assert en("police_letter.filled", names="").split(":")[0] in page.locator(STATUS).inner_text()
    # One click on plain text, so Chromium treats the page as touched.
    page.locator(STATUS).click()
    with page.expect_event("dialog"):
        page.close(run_before_unload=True)
    page.wait_for_timeout(300)
    assert [kind for kind, _ in seen] == ["beforeunload"]
    assert not page.is_closed()
    assert page.input_value("#uby_idub") == SAMPLE_IDUB

    # A clean page stays clean at load.
    clean = live.open(WIDTH)
    clean.goto(live.url)
    clean.wait_for_selector("#property-settings-form")
    assert clean.locator("#property-settings-form").get_attribute("data-dirty") is None
    assert not clean.locator(SAVE_ROW).is_visible()
    assert no_client == []
