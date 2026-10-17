"""Legacy /automation URLs redirect to the property hub (brief 0066)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "automation-missing-host"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Automation Host", username=USERNAME)
    owner_id = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Automation s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@automation.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Automation Flat",
            "permalink_token": "automationmissing1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def test_the_old_automation_hub_is_gone(host):
    """0101: /automation was removed; the property's Settings → Automation is the home."""
    client, apartment_id = host
    assert client.get("/automation?lang=en", follow_redirects=False).status_code == 404
    page = client.get(f"/apartments/{apartment_id}?view=settings&section=automation&lang=en")
    assert page.status_code == 200 and 'id="automation"' in page.text
