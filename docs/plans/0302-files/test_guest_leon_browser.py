"""0302: the Leon (AI) chat on the QR guide page in a real browser at 390 px.

A greeting is answered by the server without a model call (leon smalltalk), so
the round trip needs no network. A host answer and an open question are then
written straight into the tables, as 0301 would, and the page shows them after
a reload. Reuses the live server, browser and layout checker of
test_guest_browser_e2e. Skipped when Chromium is missing, unless
UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import config, db, guest_guide, guide_token
from tests.test_guest_browser_e2e import LAYOUT_JS, browser, live_server  # noqa: F401

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or Path(__file__).resolve().parents[1] / ".screenshots")
NAME = "Leon chat browser flat 0302"


def _seed() -> tuple:
    _cleanup()
    now = db.utcnow()
    entity = db.insert("legal_entity", {"name": "Jana Fiktivni", "created_at": now})
    apartment_id = db.insert("apartment", {
        "internal_name": NAME, "uby_name": NAME, "permalink_token": "leonchatbrowser0302", "legal_entity_id": entity,
        "automation_mode": "manual", "active": 1, "created_at": now,
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
    cards = {r["kind"]: r for r in guest_guide.items(apartment_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apartment_id, cards[kind]["id"], {"steps": "Step one\nStep two"})
    return apartment_id, guide_token.ensure(apartment_id)


def _cleanup():
    for row in db.query("SELECT id, legal_entity_id FROM apartment WHERE internal_name = ?", (NAME,)):
        db.execute("DELETE FROM guest_chat WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM guide_item WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (row["legal_entity_id"],))


def _host_answers(apartment_id: int) -> None:
    chat = db.query_one("SELECT id FROM guest_chat WHERE apartment_id = ? AND door = 'qr'", (apartment_id,))
    now = db.utcnow()
    db.insert("guest_chat_message", {"chat_id": chat["id"], "role": "host", "kind": "answer",
                                     "text": "The sauna opens at 18:00.", "created_at": now})
    db.insert("guest_chat_message", {"chat_id": chat["id"], "role": "leon", "kind": "emergency",
                                     "text": "Call 112 now.\nGas tap: under the sink.", "created_at": now})
    asked = db.insert("guest_chat_message", {"chat_id": chat["id"], "role": "guest", "text": "Is there a pool?",
                                             "created_at": now})
    db.insert("guest_question", {"chat_id": chat["id"], "apartment_id": apartment_id, "message_id": asked,
                                 "summary": "Pool", "status": "open", "created_at": now})


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_chat_works_and_lays_out_on_a_phone(live_server, browser, monkeypatch, lang):  # noqa: F811
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    apartment_id, token = _seed()
    try:
        context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = context.new_page()
        page.goto(f"{live_server}/g/{token}?lang={lang}")
        assert page.locator("[data-leon-form]").is_visible()
        assert page.locator("[data-leon-jump]").is_visible()
        page.fill("[data-leon-input]", "Hello")
        assert page.locator("[data-leon-count]").inner_text() == "5 / 500"
        page.click("[data-leon-send]")
        page.wait_for_selector("[data-leon-msg=leon]")
        assert page.locator("[data-leon-msg=guest]").inner_text().endswith("Hello")
        assert page.locator("[data-leon-input]").input_value() == ""
        assert page.locator("[data-leon-error]").is_hidden()

        _host_answers(apartment_id)
        page.reload()
        page.wait_for_selector("[data-leon-msg=host]")
        host = page.locator("[data-leon-msg=host]").inner_text()
        assert "Jana" in host and "The sauna opens at 18:00." in host
        assert page.locator("[data-leon-waiting]").is_visible()
        urgent = page.locator("[data-leon-kind=emergency]")
        assert urgent.get_attribute("role") == "alert" and "112" in urgent.inner_text()
        assert "g-leon-msg--emergency" in urgent.get_attribute("class")

        problems = page.evaluate(LAYOUT_JS)
        assert not problems, problems
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"0302-guide-chat-{lang}-390.png"), full_page=True)
        context.close()
    finally:
        _cleanup()


def test_without_javascript_the_guide_shows_one_line_and_no_form(live_server, browser, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    _, token = _seed()
    try:
        context = browser.new_context(viewport={"width": 390, "height": 844}, java_script_enabled=False)
        page = context.new_page()
        page.goto(f"{live_server}/g/{token}?lang=en")
        assert page.locator("[data-guide-card]").count() == len(guest_guide.MUST_HAVE)
        assert page.locator("[data-leon-nojs]").is_visible()
        assert page.locator("[data-leon-form]").is_hidden()
        assert page.locator("[data-leon-jump]").is_hidden()
        assert page.locator("[data-qr-contact]").is_visible()
        context.close()
    finally:
        _cleanup()
