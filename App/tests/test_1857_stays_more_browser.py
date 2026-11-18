"""1857: phone Show more appends the next page of stays in place."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app
from tests.conftest import login_as, mark_security_prompt_seen
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.go_stack import go_paths_enabled, seed_go_host_gate
from tests.test_host_quiet_dashboard_browser import (  # noqa: F401
    _launch,
    base,
    dashboard_host,
    sync_api,
)

USERNAME = "stays-more-1857"


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        uid = row["id"]
        db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))", (uid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (uid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (uid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _seed_six_stays(apartment_id: int) -> None:
    today = claim.prague_today()
    for n in range(6):
        start = today + timedelta(days=n)
        end = start + timedelta(days=2)
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "uid": f"1857-{n}",
                "source": "manual",
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
                "status": "active",
                "created_at": db.utcnow(),
                "updated_at": db.utcnow(),
            },
        )


@pytest.fixture
def stays_more_host():
    db.init_db()
    _cleanup()
    owner_id = mark_security_prompt_seen(
        auth.create_account(f"{USERNAME}@example.test", "Stays More", username=USERNAME)
    )
    if go_paths_enabled():
        seed_go_host_gate(owner_id)
    entity = db.insert(
        "legal_entity",
        {"name": "More s.r.o.", "seat": "Praha", "ico": "18570001", "contact_email": "m@example.test",
         "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner_id,
            "internal_name": "More Flat",
            "addr_obec": "Praha",
            "addr_house_no": "1",
            "addr_zip": "11000",
            "permalink_token": "moreflat1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    _seed_six_stays(apartment_id)
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def _cookie(client: TestClient) -> str:
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie


def test_phone_show_more_no_js_uses_plain_link(base, stays_more_host):
    client, _apartment_id = stays_more_host
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context = browser.new_context(
            viewport={"width": 390, "height": 812},
            java_script_enabled=False,
            base_url=base,
        )
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _cookie(client), "url": base}])
        page = context.new_page()
        page.goto("/reservations?range=all")
        more = page.locator(".list.stays-more a, [data-stays-more] a")
        assert more.count() == 1
        more.click()
        assert "page=2" in page.url
        assert page.locator(".stays-desk tbody tr").count() >= 1
        page.go_back()
        assert "/reservations" in page.url
        context.close()
        browser.close()