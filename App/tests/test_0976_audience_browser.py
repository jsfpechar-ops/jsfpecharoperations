"""0976: Keys card audience default, checked in a real browser at phone width. Synthetic data only; changes no product code.

Reuses the live server, browser and layout checker of test_guest_browser_e2e.
Skipped when Chromium is missing, unless UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, claim, config, db, guest_guide, guide_token, mail
from app.main import app
from tests.conftest import login_as
from tests.test_guest_browser_e2e import LAYOUT_JS, browser, live_server  # noqa: F401

SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b18")
APT_NAME = "Audience 0976"
PERMALINK = "audience0976tok"
SYNTHETIC = "SYNTHETIC-0976 key box instruction"
ANY_STAY = "audience0976-stay"


def _cleanup():
    for row in db.query("SELECT id FROM apartment WHERE internal_name = ?", (APT_NAME,)):
        db.execute("DELETE FROM guide_item WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))


def _seed(username: str):
    """A fresh host property, every must-have card filled, plus a stay that starts today."""
    _cleanup()
    now = db.utcnow()
    owner = auth.create_account(f"{username}@example.test", "Audience 0976", role="host", username=username)
    apartment_id = db.insert("apartment", {
        "internal_name": APT_NAME, "uby_name": APT_NAME, "owner_user_id": owner,
        "permalink_token": PERMALINK, "permalink_window_days": 14,
        "automation_mode": "manual", "active": 1, "created_at": now,
    })
    guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
    cards = {r["kind"]: r for r in guest_guide.items(apartment_id)}
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apartment_id, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    keys_id = cards["keys"]["id"]
    today = claim.prague_today()
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "uid": ANY_STAY, "source": "airbnb", "status": "active",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=2)).isoformat(),
        "created_at": now, "updated_at": now,
    })
    return apartment_id, keys_id, guide_token.ensure(apartment_id), reservation_id


def _save_keys(page, apartment_id: int, keys_id: int, steps: str | None = None):
    if steps is not None:
        page.fill('textarea[name="steps"]', steps)
    page.locator(f'form[action$="/{keys_id}"] button[type="submit"]:not([name="then"])').click()
    page.wait_for_load_state()


def test_keys_card_audience_default_in_a_browser(live_server, browser, monkeypatch):  # noqa: F811
    # Same switches as the matrix test: no PIN page, and no claim mail gate before the stay page.
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    username = f"audience{secrets.token_hex(3)}"
    apartment_id, keys_id, qr_token, reservation_id = _seed(username)
    SHOTS.mkdir(parents=True, exist_ok=True)
    contexts = []
    try:
        client = TestClient(app)
        response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
        assert response.status_code == 303, response.text
        session = client.cookies.get(auth.SESSION_COOKIE)
        assert session

        host = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        contexts.append(host)
        host.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": live_server + "/"}])
        page = host.new_page()

        # a. host, 390 px: the Keys editor of the fresh card
        page.goto(f"{live_server}/apartments/{apartment_id}/guide/{keys_id}?lang=en")
        editor_value = page.eval_on_selector('select[name="visibility"]', "s => s.value")
        editor_label = page.eval_on_selector(
            'select[name="visibility"]', "s => s.options[s.selectedIndex].text.trim()")
        print("EDITOR_BROWSER_DEFAULT", editor_value, "|", editor_label)
        page.screenshot(path=str(SHOTS / "0976-editor-keys-default-390.png"), full_page=True)
        assert editor_value == "everyone"

        # b. save with the select untouched (the default path), then the QR door
        _save_keys(page, apartment_id, keys_id, steps=SYNTHETIC)
        guest = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        contexts.append(guest)
        qr = guest.new_page()
        qr.goto(f"{live_server}/g/{qr_token}?lang=en")
        qr_default_visible = SYNTHETIC in qr.content()
        print("QR_DEFAULT_VISIBLE", qr_default_visible)
        assert not qr.evaluate(LAYOUT_JS)
        qr.screenshot(path=str(SHOTS / "0976-qr-default-390.png"), full_page=True)
        assert qr_default_visible is True

        # c. change the select to booked, save, then the QR door and the stay door
        page.goto(f"{live_server}/apartments/{apartment_id}/guide/{keys_id}?lang=en")
        page.select_option('select[name="visibility"]', "booked")
        _save_keys(page, apartment_id, keys_id)
        qr.goto(f"{live_server}/g/{qr_token}?lang=en")
        qr_booked_visible = SYNTHETIC in qr.content()
        print("QR_BOOKED_VISIBLE", qr_booked_visible)
        assert not qr.evaluate(LAYOUT_JS)
        qr.screenshot(path=str(SHOTS / "0976-qr-booked-390.png"), full_page=True)
        assert qr_booked_visible is False

        stay = guest.new_page()
        stay.goto(f"{live_server}/l/{PERMALINK}/{reservation_id}/guide?lang=en")
        stay_inside_visible = SYNTHETIC in stay.content()
        print("STAY_INSIDE_BOOKED_VISIBLE", stay_inside_visible)
        assert not stay.evaluate(LAYOUT_JS)
        stay.screenshot(path=str(SHOTS / "0976-stay-booked-390.png"), full_page=True)
        assert stay_inside_visible is True, (stay.url, stay.inner_text("body")[:700])
    finally:
        for context in contexts:
            context.close()
        _cleanup()
