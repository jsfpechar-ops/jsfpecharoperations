"""0211: a new property's guest-link window defaults to 1 day; stored values are kept."""
from __future__ import annotations

from app import db
from tests.test_address_split import host_client  # noqa: F401  (fixture reuse)


def test_new_property_window_defaults_to_one_day(host_client):  # noqa: F811
    client, owner_id, entity_id = host_client
    payload = {
        "internal_name": "Window Default Flat",
        "legal_entity_id": str(entity_id),
        "addr_obec": "Praha",
        "addr_house_no": "7",
        "addr_zip": "11000",
        "addr_street": "Default Street",
        "active": "on",
        "automation_mode": "manual",
        "submit_after_hours": "24",
        "default_purpose": "10",
    }
    response = client.post("/apartments", data=payload, follow_redirects=False)
    assert response.status_code == 303
    row = db.query_one(
        "SELECT permalink_window_days FROM apartment WHERE internal_name = ?",
        ("Window Default Flat",),
    )
    assert row["permalink_window_days"] == 1
