"""0303: a translated guide card on the QR page at 390 px, with the original opened. No network."""
from __future__ import annotations

import os
import time
from pathlib import Path

from app import ai, config, db, guest_guide, guide_token
from tests.test_guest_browser_e2e import LAYOUT_JS, browser, live_server  # noqa: F401
from tests.test_guide_translate import EchoGerman

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or Path(__file__).resolve().parents[1] / ".screenshots")
NAME = "Translate browser flat 0353"


def _seed() -> str:
    _cleanup()
    apartment_id = db.insert("apartment", {
        "internal_name": NAME, "uby_name": NAME, "permalink_token": "translatebrowser0353",
        "automation_mode": "manual", "active": 1, "created_at": db.utcnow(),
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
    cards = {r["kind"]: r for r in guest_guide.items(apartment_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apartment_id, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    guest_guide.save(apartment_id, cards["heating"]["id"], {
        "steps": "Zmáčkněte kulaté tlačítko.\nNastavte 22 stupňů.", "location": "Skříň v předsíni"})
    return guide_token.ensure(apartment_id)


def _cleanup():
    for row in db.query("SELECT id FROM apartment WHERE internal_name = ?", (NAME,)):
        db.execute("DELETE FROM guide_item WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))


def test_a_translated_card_lays_out_on_a_phone(live_server, browser, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"guide_translate"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    ai.set_client_for_tests(EchoGerman())
    token = _seed()
    try:
        context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = context.new_page()
        page.goto(f"{live_server}/g/{token}?lang=de")
        deadline = time.time() + 10
        while not page.locator("[data-guide-original]").count() and time.time() < deadline:
            time.sleep(0.3)
            page.reload()
        assert page.locator("[data-guide-original]").count() >= 1
        page.locator("[data-guide-original] summary").first.click()
        assert page.locator(".g-guide-original-body").first.is_visible()
        problems = page.evaluate(LAYOUT_JS)
        assert not problems, problems
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "0353-guide-translated-de-390.png"), full_page=True)
        context.close()
    finally:
        ai.set_client_for_tests(None)
        _cleanup()
