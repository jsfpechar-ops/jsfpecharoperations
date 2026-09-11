"""Setup wizard progress for new workspaces."""
from __future__ import annotations

from app import auth, db, onboarding


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


def test_onboarding_advances_after_entity_and_property():
    owner_id = auth.create_account("onboard-next", "Secure-Password-123", role="host")
    entity_id = _entity(owner_id)
    progress = onboarding.progress(owner_id)
    assert progress["current"]["id"] == "property"
    apartment_id = _apartment(owner_id, entity_id)
    progress = onboarding.progress(owner_id)
    assert progress["current"]["id"] == "calendars"
    assert f"/apartments/{apartment_id}#calendars" in progress["current"]["url"]
