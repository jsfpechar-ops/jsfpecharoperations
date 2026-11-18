"""1858: browser back to Stays restores scroll from Turbo cache."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app
from tests.conftest import login_as, mark_security_prompt_seen
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_host_quiet_dashboard_browser import (  # noqa: F401
    _launch,
    base,
    dashboard_host,
    sync_api,
)

USERNAME = "stays-cache-1858"


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        uid = row["id"]
        db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))", (uid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


@pytest.fixture
def stays_cache_host():
    db.init_db()
    _cleanup()
    mark_security_prompt_seen(auth.create_account(f"{USERNAME}@example.test", "Stays Cache", username=USERNAME))
    entity = db.insert(
        "legal_entity",
        {"name": "Cache s.r.o.", "seat": "Praha", "ico": "18580001", "contact_email": "c@example.test",
         "owner_user_id": _owner_id(), "created_at": db.utcnow()},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": _owner_id(),
            "internal_name": "Cache Flat",
            "addr_obec": "Praha",
            "addr_house_no": "2",
            "addr_zip": "11000",
            "permalink_token": "cacheflat1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    today = claim.prague_today()
    stay_ids = []
    for n in range(8):
        start = today + timedelta(days=n)
        end = start + timedelta(days=2)
        stay_ids.append(
            db.insert(
                "reservation",
                {
                    "apartment_id": apartment_id,
                    "uid": f"1858-{n}",
                    "source": "manual",
                    "date_from": start.isoformat(),
                    "date_to": end.isoformat(),
                    "status": "active",
                    "created_at": db.utcnow(),
                    "updated_at": db.utcnow(),
                },
            )
        )
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    try:
        yield client, stay_ids[0]
    finally:
        _cleanup()


def _cookie(client: TestClient) -> str:
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie


def test_back_to_stays_restores_scroll(base, stays_cache_host):
    client, first_stay = stays_cache_host
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, _cookie(client), "/reservations?range=all", 390)
        if 'content="cache"' not in page.content():
            pytest.skip("Turbo cache=stays needs Go GET /reservations")
        page.evaluate("() => window.scrollTo(0, 600)")
        page.wait_for_timeout(100)
        y_before = page.evaluate("() => window.scrollY")
        page.locator(f'a.card.stay[href*="/reservations/{first_stay}"]').first.click()
        page.wait_for_url("**/reservations/*")
        page.go_back()
        page.wait_for_url("**/reservations*")
        y_after = page.evaluate("() => window.scrollY")
        assert abs(y_after - y_before) <= 50, (y_before, y_after)
        assert page.locator(".flash-banner").count() == 0
        assert page.locator("[inert]").count() == 0
        context.close()
        browser.close()