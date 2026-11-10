"""1086: the warning before "Read the letter" throws away unsaved edits.

Reading the letter reloads the editor, so a host with unsaved edits or a typed
password is asked first. Fake ``SAMPLE_*`` values and a fake client only.
"""
from __future__ import annotations

import os

import pytest

from tests.test_host_police_letter_browser import READ_BUTTON, en, live  # noqa: F401
from tests.test_police_letter_flow import LETTER, fake_client, host, no_client  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api  # noqa: F401
else:
    pytest.importorskip("playwright.sync_api")

WIDTH = 1280


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
    page.locator("details.police-letter-paste > summary").click()
    page.fill("#letter_text", LETTER)
    return page, seen


def test_unsaved_edits_ask_before_the_letter_is_read(live, no_client):  # noqa: F811
    warning = en("police_letter.discard_warning")
    page, seen = _open(live, [False, True])
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    page.fill("#uby_name", "Typed And Not Saved")
    page.wait_for_function("() => document.querySelector('#property-settings-form').dataset.dirty === '1'")

    # Cancel: the page stays and the typed value is kept.
    page.locator(READ_BUTTON).click()
    page.wait_for_timeout(400)
    assert seen == [("confirm", warning)]
    assert posts == []
    assert page.locator("#police-letter-check").count() == 0
    assert page.input_value("#uby_name") == "Typed And Not Saved"
    assert LETTER.strip() in page.input_value("#letter_text").replace("\r\n", "\n")

    # Accept: the check-answers page loads, and leaving for it does not warn a second time.
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        page.locator(READ_BUTTON).click()
    assert reply.value.status == 422
    page.wait_for_selector("#police-letter-check")
    page.wait_for_timeout(400)
    assert seen == [("confirm", warning), ("confirm", warning)]
    assert no_client == []


def test_a_typed_password_asks_and_a_clean_page_does_not(live, no_client):  # noqa: F811
    warning = en("police_letter.discard_warning")
    page, seen = _open(live, [False])
    page.fill("#uby_ws_password", "typed-by-hand-1086")
    page.locator(READ_BUTTON).click()
    page.wait_for_timeout(400)
    assert seen == [("confirm", warning)]
    assert page.locator("#police-letter-check").count() == 0
    assert page.input_value("#uby_ws_password") == "typed-by-hand-1086"

    clean, clean_seen = _open(live, [])
    with clean.expect_response(lambda r: r.url.endswith("/police-letter")):
        clean.locator(READ_BUTTON).click()
    clean.wait_for_selector("#police-letter-check")
    clean.wait_for_timeout(400)
    assert clean_seen == []
    assert no_client == []


def test_the_check_answers_page_starts_dirty_and_warns_on_leaving(live, no_client):  # noqa: F811
    page, seen = _open(live, [False])
    with page.expect_response(lambda r: r.url.endswith("/police-letter")):
        page.locator(READ_BUTTON).click()
    page.wait_for_selector("#police-letter-check")
    assert seen == []
    form = page.locator("#property-settings-form")
    assert form.get_attribute("data-dirty-start") == "1"
    # A real tick first: the browser only warns on a page the user has touched.
    page.check("#letter_ok_uby_idub")
    page.wait_for_function("() => document.querySelector('#property-settings-form').dataset.dirty === '1'")
    with page.expect_event("dialog"):
        page.close(run_before_unload=True)
    page.wait_for_timeout(300)
    assert [kind for kind, _ in seen] == ["beforeunload"]
    assert not page.is_closed()
    assert page.locator("#police-letter-check").is_visible()
    assert no_client == []


SAVE_ROW = ".savebar[data-for='property-settings-form']"
DIRTY = "() => document.querySelector('#property-settings-form').dataset.dirty === '1'"


def test_the_check_answers_page_shows_the_save_row_and_warns_with_no_input(live, no_client):  # noqa: F811
    page, seen = _open(live, [False])
    with page.expect_response(lambda r: r.url.endswith("/police-letter")):
        page.locator(READ_BUTTON).click()
    page.wait_for_selector("#police-letter-check")
    # Nothing ticked, typed or focused.
    page.wait_for_function(DIRTY)
    assert page.locator(SAVE_ROW).is_visible()
    # One click on plain text, so Chromium treats the page as touched.
    page.locator("#police-letter-check .police-letter-check-title").click()
    assert page.locator("#property-settings-form").get_attribute("data-dirty") == "1"
    assert seen == []
    with page.expect_event("dialog"):
        page.close(run_before_unload=True)
    page.wait_for_timeout(300)
    assert [kind for kind, _ in seen] == ["beforeunload"]
    assert not page.is_closed()

    # A clean page stays clean at load.
    clean = live.open(WIDTH)
    clean.goto(live.url)
    clean.wait_for_selector("#property-settings-form")
    assert clean.locator("#property-settings-form").get_attribute("data-dirty") is None
    assert not clean.locator(SAVE_ROW).is_visible()
    assert no_client == []
