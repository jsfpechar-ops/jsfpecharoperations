"""Property pages are the hub for guest links and police timing (brief 0066)."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "property-hub-host"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        apartment_ids = [
            row["id"]
            for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,))
        ]
        for apartment_id in apartment_ids:
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]


def _entity_id() -> int:
    return db.insert(
        "legal_entity",
        {
            "name": "Hub s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@hub.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )


def _seed_property(name: str = "Hub Flat", entity_id: int | None = None) -> int:
    if entity_id is None:
        entity_id = _entity_id()
    return db.insert(
        "apartment",
        {
            "internal_name": name,
            "owner_user_id": _owner_id(),
            "legal_entity_id": entity_id,
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "default_purpose": "10",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Hub Host", username=USERNAME)
    apartment_id = _seed_property()
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    yield client, apartment_id
    _cleanup()


@pytest.fixture
def two_properties(host):
    client, first_id = host
    entity_id = db.query_one(
        "SELECT legal_entity_id FROM apartment WHERE id = ?", (first_id,)
    )["legal_entity_id"]
    second_id = _seed_property("Second Flat", entity_id=entity_id)
    return client, first_id, second_id


def test_local_nav_absent_on_property_pages(host, two_properties):
    client, apartment_id, _second = two_properties
    for path in (
        "/apartments",
        f"/apartments/{apartment_id}",
        "/entities",
        "/smart-locks",
    ):
        text = client.get(path, follow_redirects=False).text
        assert 'class="host-local-nav"' not in text


def test_guest_links_redirects_to_communication_with_one_property(host):
    client, apartment_id = host
    response = client.get("/guest-links", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/apartments/{apartment_id}?view=settings&section=guests#communication"


def test_guest_links_redirects_to_apartments_with_two(two_properties):
    client, _first, _second = two_properties
    response = client.get("/guest-links", follow_redirects=False)
    assert response.status_code == 303
    # 0078: several properties land on the Properties summary, not a record.
    assert response.headers["location"] == "/apartments#property-summaries"


def test_the_old_automation_hub_is_gone(two_properties):
    """0101: /automation was removed (no e-mail links it, unlike /guest-links)."""
    client, _first, _second = two_properties
    assert client.get("/automation", follow_redirects=False).status_code == 404


def test_property_save_without_automation_fields_preserves_timing(host):
    client, apartment_id = host
    db.update(
        "apartment",
        apartment_id,
        {
            "automation_mode": "scheduled",
            "submit_after_hours": 12,
            "default_purpose": "10",
        },
    )
    apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    response = client.post(
        f"/apartments/{apartment_id}",
        data={
            "return_to": f"/apartments/{apartment_id}",
            "internal_name": apt["internal_name"],
            "legal_entity_id": apt["legal_entity_id"],
            "permalink_pin": apt["permalink_pin"],
            "permalink_window_days": str(apt["permalink_window_days"] or 2),
            "permalink_reachback_days": str(apt["permalink_reachback_days"] or 365),
        },
        follow_redirects=False,
    )
    assert response.status_code in (303, 302)
    row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert row["automation_mode"] == "scheduled"
    assert row["submit_after_hours"] == 12
    assert row["default_purpose"] == "10"


def test_property_save_updates_automation_fields(host):
    client, apartment_id = host
    apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    response = client.post(
        f"/apartments/{apartment_id}",
        data={
            "return_to": f"/apartments/{apartment_id}",
            "internal_name": apt["internal_name"],
            "legal_entity_id": apt["legal_entity_id"],
            "automation_mode": "scheduled",
            "submit_after_hours": "6",
            "default_purpose": "10",
            "permalink_pin": apt["permalink_pin"],
            "permalink_window_days": str(apt["permalink_window_days"] or 2),
            "permalink_reachback_days": str(apt["permalink_reachback_days"] or 365),
        },
        follow_redirects=False,
    )
    assert response.status_code in (303, 302)
    row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert row["automation_mode"] == "scheduled"
    assert row["submit_after_hours"] == 6
    assert row["default_purpose"] == "10"


def test_property_page_has_editable_automation_controls(host):
    client, apartment_id = host
    text = client.get(f"/apartments/{apartment_id}").text
    panel = text[text.index('id="automation"') : text.index("</section>", text.index('id="automation"'))]
    assert 'name="automation_mode"' in panel
    assert 'data-automation-mode' in panel
    assert 'name="submit_after_hours"' in panel
    assert 'name="default_purpose"' in panel
    help_snippet = "Automatic modes do not wait for ID verification"
    assert help_snippet in re.sub(r"\s+", " ", panel)


def test_test_connection_still_available_on_property_page(host):
    client, apartment_id = host
    text = client.get(f"/apartments/{apartment_id}").text
    assert f'formaction="/apartments/{apartment_id}/test-connection"' in text


def test_entities_reachable_from_property_and_settings(host):
    client, apartment_id = host
    property_page = client.get(f"/apartments/{apartment_id}").text
    # 0088: the operator link opens that operator's business details.
    assert 'href="/entities' in property_page
    settings = client.get("/settings").text
    # 0076: with one business, Account settings opens its editor directly.
    assert re.search(r'href="/entities(\?edit=\d+&amp;next=/settings)?"', settings)


def test_templates_do_not_link_to_removed_pages(host):
    client, apartment_id = host
    for path in ("/apartments", f"/apartments/{apartment_id}", "/settings", "/entities"):
        text = client.get(path).text
        # The removed /automation page (0098's /apartments/<id>/automation-timing is not it).
        assert not re.search(r'"/automation["?#]', text)
        assert "/guest-links" not in text
