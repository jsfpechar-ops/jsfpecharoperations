"""Setup wizard progress for new workspaces."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth, db, onboarding
from app.main import app


def setup_module():
    db.init_db()


def _entity(owner_id: int, name: str = "Test Host s.r.o.") -> int:
    return db.insert(
        "legal_entity",
        {
            "name": name,
            "seat": "Prague",
            "ico": "12345678",
            "contact_email": "host@example.com",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )


def _apartment(owner_id: int, entity_id: int) -> int:
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Studio",
            "permalink_token": "abc123def4",
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def test_onboarding_starts_with_legal_entity():
    owner_id = auth.create_account("onboard-host", "Secure-Password-123", role="host")
    progress = onboarding.progress(owner_id)
    assert progress["current"]["id"] == "entity"
    assert progress["completed"] == 0
    assert progress["percent"] == 0
    assert progress["current"]["learn_url"] == "/guide#setup"


def test_onboarding_advances_after_entity_and_property():
    owner_id = auth.create_account("onboard-next", "Secure-Password-123", role="host")
    entity_id = _entity(owner_id)
    progress = onboarding.progress(owner_id)
    assert progress["current"]["id"] == "property"
    apartment_id = _apartment(owner_id, entity_id)
    progress = onboarding.progress(owner_id)
    assert progress["current"]["id"] == "calendars"
    assert f"/apartments/{apartment_id}#calendars" in progress["current"]["url"]
    assert progress["percent"] == 40


def test_first_dashboard_is_a_guided_setup_journey():
    owner_id = auth.create_account(
        "onboard-first-view",
        "Secure-Password-123",
        role="host",
        must_change_password=False,
    )
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )

    page = client.get("/")

    assert page.status_code == 200
    assert 'class="onboarding-welcome"' in page.text
    assert 'class="onboarding-now"' in page.text
    assert "Set it once. Welcome every guest calmly." in page.text
    assert "Have ready: legal name, IČO" in page.text
    assert 'href="/entities"' in page.text
    assert 'href="/guide#setup"' in page.text


def test_onboarding_can_be_reopened_as_a_full_page():
    owner_id = auth.create_account(
        "onboard-reopen",
        "Secure-Password-123",
        role="host",
        must_change_password=False,
    )
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )

    page = client.get("/onboarding")

    assert page.status_code == 200
    assert "Nothing goes live by accident" in page.text
    assert "Want to learn before entering real details?" in page.text
