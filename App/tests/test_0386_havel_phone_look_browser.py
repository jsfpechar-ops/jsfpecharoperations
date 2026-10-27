"""0386: Havel looks like a support chat on the phone (rule 7: 390 px shots, 0 skipped)."""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from app import config  # noqa: E402
from tests import test_havel_browser as hb  # noqa: E402
from tests.test_submission_retry_cap import host  # noqa: E402,F401

origin = hb.origin
_context = hb._context

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0386"


def _open_sheet(page):
    page.locator("[data-havel-fab]").click()
    sheet = page.locator("#havel-sheet[open]")
    sheet.wait_for()
    # The first-open fetch replaces the topic nodes before filling this wrapper.
    # Wait for that swap, including the AI-off state, before measuring the chips.
    sheet.locator("[data-havel-form-wrap] > *").first.wait_for(state="attached")
    return sheet


def test_no_ring_on_open(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        _open_sheet(page)
        sync_api.expect(page.locator("#havel-title")).to_be_focused()
        outline = page.evaluate("getComputedStyle(document.getElementById('havel-title')).outlineStyle")
        assert outline == "none"
        page.screenshot(path=str(SHOTS / "home-390.png"))
        browser.close()


def test_topics_are_chips(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        sheet = _open_sheet(page)
        chips = sheet.locator(".havel-chip[data-havel-topic-link]")
        assert chips.count() == 6  # 0391: five topics + "Other topic"
        assert sheet.locator(".ui-menu-panel").count() == 0
        for i in range(chips.count()):
            sync_api.expect(chips.nth(i)).to_be_visible()
            box = chips.nth(i).bounding_box()
            assert box["x"] + box["width"] <= 390
            assert box["height"] >= 40
        chips.first.click()
        host_bubble = sheet.locator(".havel-msg-host").first
        host_bubble.wait_for()
        assert host_bubble.inner_text().strip() != ""
        page.screenshot(path=str(SHOTS / "topic-390.png"))
        question = sheet.locator(".havel-chips .havel-chip").first
        question.wait_for()
        question_text = question.inner_text().strip()
        question.click()
        sheet.locator(".havel-answer").wait_for()
        assert sheet.locator(".havel-msg-host").count() == 1
        assert question_text in sheet.locator(".havel-msg-host").inner_text()
        page.screenshot(path=str(SHOTS / "answer-390.png"))
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        browser.close()


def test_pill_composer(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        sheet = _open_sheet(page)
        sheet.locator("[data-havel-other]").click()
        textarea = sheet.locator("#havel-message")
        textarea.wait_for()
        assert sheet.locator(".havel-input #havel-message").count() == 1
        assert sheet.locator(".havel-input .havel-send").count() == 1
        assert textarea.evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"
        input_box = sheet.locator(".havel-input").bounding_box()
        send_box = sheet.locator(".havel-input .havel-send").bounding_box()
        assert send_box["x"] + send_box["width"] <= input_box["x"] + input_box["width"] + 1
        assert send_box["y"] >= input_box["y"] - 1
        assert send_box["y"] + send_box["height"] <= input_box["y"] + input_box["height"] + 1
        initial = textarea.bounding_box()["height"]
        textarea.fill("line\n" * 6)
        grown = textarea.bounding_box()["height"]
        assert grown > initial
        assert grown <= 132 + 1
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        browser.close()


def test_off_state_has_support_button(origin, monkeypatch):
    SHOTS.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        sheet = _open_sheet(page)
        # 0391: the status and support button show once the host taps "Other topic".
        sheet.locator("[data-havel-other]").click()
        sheet.locator(".havel-support-open").wait_for()
        assert sheet.locator("#havel-message").count() == 0
        assert sheet.locator(".havel-note").count() == 0
        support = sheet.locator(".havel-support-open")
        assert support.count() == 1
        page.screenshot(path=str(SHOTS / "off-390.png"))
        support.click()
        sheet.locator("[data-havel-support]").wait_for()
        assert sheet.locator("[data-havel-support]").is_visible()
        browser.close()


def test_cs_home_1280(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/?lang=cs")
        sheet = _open_sheet(page)
        assert sheet.locator(".havel-chip[data-havel-topic-link]").count() == 6
        page.screenshot(path=str(SHOTS / "home-cs-1280.png"))
        browser.close()
