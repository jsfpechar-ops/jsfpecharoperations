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


def _ready_apartment(owner_id: int, entity_id: int) -> int:
    """Apartment that clears validation so onboarding can finish all five steps."""
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Ready Studio",
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Ready Studio",
            "uby_contact": "host@example.com",
            "addr_okres": "Praha 2",
            "addr_obec": "Praha",
            "addr_obec_cast": "Vinohrady",
            "addr_street": "Korunní",
            "addr_house_no": "1234",
            "addr_orient_no": "12a",
            "addr_zip": "12000",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password_enc": db.encrypt_secret("demo-password"),
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "permalink_token": "finishlink99",
            "permalink_pin": "246810",
            "passport_photo_policy": "off",
            "guest_message": "Welcome — please register before arrival.",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def test_finished_onboarding_shows_guest_link_and_pin_handoff():
    owner_id = auth.create_account(
        "onboard-finish",
        "Secure-Password-123",
        role="host",
        must_change_password=False,
    )
    entity_id = _entity(owner_id)
    apartment_id = _ready_apartment(owner_id, entity_id)
    db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://example.com/calendar.ics",
            "label": "Airbnb",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )

    progress = onboarding.progress(owner_id)
    assert progress["finished"] is True
    assert progress["finish"]["pin"] == "246810"
    assert progress["finish"]["permalink"].endswith("/l/finishlink99")
    assert progress["finish"]["communication_url"] == f"/apartments/{apartment_id}#communication"

    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert 'class="onboarding-finish"' in dashboard.text
    assert "Guest link and PIN are live" in dashboard.text
    assert "finishlink99" in dashboard.text
    assert "246810" in dashboard.text
    assert "edit host message" in dashboard.text
    assert "Open communication settings" in dashboard.text
    assert f'href="/apartments/{apartment_id}#communication"' in dashboard.text
    assert "Skip setup guidance" in dashboard.text

    checklist = client.get("/onboarding")
    assert checklist.status_code == 200
    assert 'class="onboarding-finish"' in checklist.text
    assert "All five checks are done" in checklist.text


def test_host_can_skip_and_restore_setup_guidance():
    owner_id = auth.create_account(
        "onboard-skip",
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

    first_view = client.get("/")
    assert "Skip setup guidance" in first_view.text

    skipped = client.post(
        "/onboarding/dismiss",
        data={"return_to": "/"},
        follow_redirects=False,
    )
    assert skipped.status_code == 303
    assert skipped.headers["location"] == "/"
    assert onboarding.progress(owner_id)["dismissed"] is True

    dashboard = client.get("/")
    assert 'class="onboarding-welcome"' not in dashboard.text
    assert "Setup guidance hidden" in dashboard.text
    assert 'href="/onboarding"' in dashboard.text

    checklist = client.get("/onboarding")
    assert checklist.status_code == 200
    assert 'class="onboarding-welcome"' in checklist.text
    assert "Show setup guidance again" in checklist.text

    resumed = client.post(
        "/onboarding/resume",
        data={"return_to": "/"},
        follow_redirects=False,
    )
    assert resumed.status_code == 303
    assert resumed.headers["location"] == "/"
    assert onboarding.progress(owner_id)["dismissed"] is False
    assert 'class="onboarding-welcome"' in client.get("/").text
