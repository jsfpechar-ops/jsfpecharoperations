"""0765: the phone Today lists stays from 3 days back to tomorrow, falls back to the next stay, and the calendar tab hides Today."""
from __future__ import annotations

import secrets
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, onboarding
from app.main import app
from tests.conftest import login_as
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_host_quiet_dashboard_browser import (  # the quiet overview's fixtures and helpers
    _launch,
    base,
    dashboard_host,
    sync_api,
)

__all__ = ["base", "dashboard_host"]

VISIBLE = """els => els.filter(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; }).length"""


def _make_host(offsets):
    """A host with one manual stay per offset (days from today), each lasting two nights."""
    db.init_db()
    username = f"phone-window-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Phone Window", role="host", username=username)
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": "Phone Window s.r.o.", "seat": "Praha", "ico": "11223344",
        "contact_email": "window@example.test", "owner_user_id": owner_id, "created_at": now,
    })
    apartment_id = db.insert("apartment", {
        "legal_entity_id": entity_id, "owner_user_id": owner_id,
        "internal_name": "Window Flat", "permalink_token": f"window{secrets.token_hex(4)}",
        "permalink_pin": "123456", "automation_mode": "manual",
        "submit_after_hours": 24, "active": 1, "created_at": now,
    })
    today = claim.prague_today()
    for offset in offsets:
        db.insert("reservation", {
            "apartment_id": apartment_id, "source": "manual", "uid": f"window-{secrets.token_hex(4)}",
            "date_from": (today + timedelta(days=offset)).isoformat(),
            "date_to": (today + timedelta(days=offset + 2)).isoformat(),
            "status": "active", "expected_guests_override": 1, "created_at": now, "updated_at": now,
        })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    onboarding.set_dismissed(owner_id, True)
    return {"client": client, "owner_id": owner_id, "entity_id": entity_id, "apartment_id": apartment_id}


def _drop(host):
    for table in ("alert", "audit"):
        db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (host["owner_id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (host["apartment_id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (host["apartment_id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (host["entity_id"],))
    db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{host['owner_id']}",))
    db.execute("DELETE FROM user_account WHERE id = ?", (host["owner_id"],))


@pytest.fixture(scope="module")
def window_host():
    host = _make_host([-2, 1])  # checked in 2 days ago, and tomorrow
    yield host
    _drop(host)


@pytest.fixture(scope="module")
def far_host():
    host = _make_host([10])  # only stay is 10 days ahead
    yield host
    _drop(host)


def _page(base, host, path, width):
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie, (list(host["client"].cookies.keys()), host["owner_id"])
    playwright = sync_api.sync_playwright().start()
    browser = _launch(playwright)
    context, page = _open_app(browser, base, cookie, path, width)
    return playwright, browser, context, page


def _close(playwright, browser, context):
    context.close()
    browser.close()
    playwright.stop()


def test_phone_window_lists_checkins_from_three_days_back(base, window_host):
    playwright, browser, context, page = _page(base, window_host, "/", 390)
    cards = page.locator(".hs .card").evaluate_all(VISIBLE)
    _close(playwright, browser, context)
    assert cards == 2, f"two stays in the window (2 days ago, tomorrow), found {cards} visible .hs .card"


def test_phone_far_stay_shows_next_stay_card(base, far_host):
    playwright, browser, context, page = _page(base, far_host, "/", 390)
    cards = page.locator(".hs .card").evaluate_all(VISIBLE)
    needs = page.locator(".needs-you-item.need").evaluate_all(VISIBLE)
    _close(playwright, browser, context)
    assert needs >= 1, "the 10-days-ahead host should have a need card (precondition)"
    assert cards == 1, f"only stay 10 days ahead: want one visible .hs .card (next stay), found {cards}"


def test_phone_calendar_tab_hides_today(base, window_host):
    playwright, browser, context, page = _page(base, window_host, "/?cal_view=calendar", 390)
    result = {
        "tab": page.locator(".tabs .tab.on").first.inner_text().strip(),
        "h1": page.locator("h1").evaluate_all(VISIBLE),
        "hs": page.locator(".hs").evaluate_all(VISIBLE),
        "needs_action": page.locator("#needs-action").evaluate_all(VISIBLE),
        "need_cards": page.locator(".needs-you-item.need").evaluate_all(VISIBLE),
        "more": page.locator(".needs-you-more").evaluate_all(VISIBLE),
        "ph_top": page.locator(".ph-top").evaluate_all(VISIBLE),
    }
    _close(playwright, browser, context)
    assert "alendar" in result["tab"], result["tab"]
    assert result["h1"] == 1, f"exactly one visible h1, found {result['h1']}"
    assert result["hs"] == 0, f"hs visible on phone in calendar view: {result['hs']}"
    assert result["needs_action"] == 0, f"needs-action: {result['needs_action']}"
    assert result["need_cards"] == 0 and result["more"] == 0 and result["ph_top"] == 0, result


def test_desktop_calendar_hides_needs_action(base, window_host):
    playwright, browser, context, page = _page(base, window_host, "/?cal_view=calendar", 1280)
    shown = page.locator("#needs-action").evaluate_all(VISIBLE)
    _close(playwright, browser, context)
    # 0877: the calendar view is a full page, like the Airbnb host calendar: no alert stack above it.
    assert shown == 0, "desktop calendar view shows #needs-action above the full-page calendar"
