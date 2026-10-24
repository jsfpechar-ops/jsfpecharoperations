"""0294: the QR guide page in a real browser at phone width (layout rules and a screenshot).

Reuses the live server, browser and layout checker of test_guest_browser_e2e.
Skipped when Chromium is missing, unless UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import db, guest_guide, guide_token
from tests.test_guest_browser_e2e import LAYOUT_JS, browser, live_server  # noqa: F401

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or Path(__file__).resolve().parents[1] / ".screenshots")
NAME = "Guide browser flat 0294"


def _seed() -> str:
    _cleanup()
    now = db.utcnow()
    apartment_id = db.insert("apartment", {
        "internal_name": NAME, "uby_name": NAME, "permalink_token": "guidebrowsertok0294",
        "automation_mode": "manual", "active": 1, "created_at": now,
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
    cards = {r["kind"]: r for r in guest_guide.items(apartment_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apartment_id, cards[kind]["id"], {"location": "By the door", "steps": "Step one\nStep two", "watch_out": "Mind the step"})
    return guide_token.ensure(apartment_id)


def _cleanup():
    for row in db.query("SELECT id FROM apartment WHERE internal_name = ?", (NAME,)):
        db.execute("DELETE FROM guide_item WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_qr_guide_page_lays_out_on_a_phone(live_server, browser, lang):  # noqa: F811
    token = _seed()
    try:
        context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = context.new_page()
        page.goto(f"{live_server}/g/{token}?lang={lang}")
        assert page.locator("[data-guide-card]").count() == len(guest_guide.MUST_HAVE)
        problems = page.evaluate(LAYOUT_JS)
        assert not problems, problems
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"0294-guide-qr-{lang}-390.png"), full_page=True)
        context.close()
    finally:
        _cleanup()
