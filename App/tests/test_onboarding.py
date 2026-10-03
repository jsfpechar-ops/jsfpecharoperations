"""Setup wizard progress for new workspaces."""
from __future__ import annotations

import html
import re

from fastapi.testclient import TestClient

from app import auth, db, onboarding
from app.host_i18n import STRINGS as HOST_STRINGS
from app.main import app

STEPS_RE = re.compile(r'<div class="onboarding-steps"[^>]*>\n(.*?)\n    </div>', re.DOTALL)


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
    assert HOST_STRINGS["en"]["onboarding.welcome_title"] in page.text
    assert "Have ready: name, IČO" in page.text
    assert 'href="/entities"' in page.text
    assert 'href="/guide#setup"' in page.text


def test_the_welcome_copy_names_the_task_and_the_finish():
    assert HOST_STRINGS["en"]["onboarding.welcome_title"] == "Set up UbyHost in five steps"
    assert (
        HOST_STRINGS["cs"]["onboarding.welcome_title"]
        == "Nastavení UbyHostu v pěti krocích"
    )
    assert HOST_STRINGS["en"]["onboarding.finish_line"] == (
        "Finish these five steps and you can send guests their registration link."
    )
    assert HOST_STRINGS["cs"]["onboarding.finish_line"] == (
        "Dokončete těchto pět kroků a můžete hostům poslat odkaz k registraci."
    )
    assert HOST_STRINGS["cs"]["onboarding.property.why"] == (
        "Přesné údaje zabrání tomu, aby UbyPort hlášení odmítl."
    )
    assert (
        HOST_STRINGS["cs"]["onboarding.demo_title"]
        == "Chcete si to nejdřív vyzkoušet nanečisto?"
    )
    assert HOST_STRINGS["en"]["onboarding.finish_passport_tip"] == (
        "Passport or ID photo for this property:"
    )
    assert HOST_STRINGS["cs"]["onboarding.finish_passport_tip"] == (
        "Fotka pasu nebo dokladu u tohoto ubytování:"
    )


def test_the_first_dashboard_list_is_one_line_per_step():
    owner_id = auth.create_account(
        "onboard-compact-list",
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
    steps = STEPS_RE.search(page.text)

    assert steps, "the five-step list is missing from the first dashboard"
    assert "<details>" not in steps.group(1)
    assert "<small>" not in steps.group(1)
    assert "<p>" not in steps.group(1)
    for step in onboarding.progress(owner_id)["steps"]:
        assert HOST_STRINGS["en"][f"onboarding.{step['id']}.title"] in steps.group(1)

    # "Do this now" keeps the detail and the "Have ready" line, exactly once each.
    current = onboarding.progress(owner_id)["current"]["id"]
    assert page.text.count(HOST_STRINGS["en"][f"onboarding.{current}.detail"]) == 1
    assert page.text.count(HOST_STRINGS["en"][f"onboarding.{current}.prepare"]) == 1
    assert '<a href="/onboarding">' in page.text


def test_the_full_checklist_keeps_the_detail_and_the_why():
    owner_id = auth.create_account(
        "onboard-full-list",
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
    steps = STEPS_RE.search(page.text)

    assert steps, "the five-step list is missing from the setup page"
    block = html.unescape(steps.group(1))
    for step in onboarding.progress(owner_id)["steps"]:
        assert HOST_STRINGS["en"][f"onboarding.{step['id']}.detail"] in block
        assert HOST_STRINGS["en"][f"onboarding.{step['id']}.prepare"] in block
    assert "<details>" in block


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
    assert "Set up UbyHost in five steps" in page.text
    # WP17 (review 3.E item 10): the reassurance box is gone from the app.
    assert "Nothing goes live by accident" not in page.text
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


def _unique_apartment(owner_id: int, entity_id: int, token: str, *, ready: bool = False) -> int:
    """A fresh property per test -- ``permalink_token`` is unique across the DB."""
    data = {
        "legal_entity_id": entity_id,
        "owner_user_id": owner_id,
        "internal_name": "Studio",
        "permalink_token": token,
        "permalink_pin": "1234",
        "automation_mode": "manual",
        "submit_after_hours": 24,
        "active": 1,
        "created_at": db.utcnow(),
    }
    if ready:
        data.update(
            {
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
            }
        )
    return db.insert("apartment", data)


def _manual_stay(apartment_id: int, uid: str) -> int:
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": uid,
            "date_from": "2026-11-02",
            "date_to": "2026-11-05",
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def test_a_hand_typed_stay_satisfies_the_calendar_step():
    """A host who takes direct bookings has no iCal feed to connect."""
    owner_id = auth.create_account("onboard-manual", "Secure-Password-123", role="host")
    entity_id = _entity(owner_id)
    apartment_id = _unique_apartment(owner_id, entity_id, "manualtoken1")

    assert onboarding.progress(owner_id)["current"]["id"] == "calendars"

    _manual_stay(apartment_id, "hand-typed-1")

    progress = onboarding.progress(owner_id)
    assert progress["steps"][2]["id"] == "calendars"
    assert progress["steps"][2]["done"] is True, "a hand-typed stay left step 3 unfinished"


def test_a_hand_typed_stay_also_lets_the_guest_link_step_finish():
    """Step 5 repeated the iCal requirement, so fixing step 3 alone was not enough."""
    owner_id = auth.create_account("onboard-manual-end", "Secure-Password-123", role="host")
    entity_id = _entity(owner_id)
    apartment_id = _unique_apartment(owner_id, entity_id, "manualtoken2", ready=True)
    _manual_stay(apartment_id, "hand-typed-2")

    progress = onboarding.progress(owner_id)

    assert progress["finished"] is True
    assert progress["completed"] == progress["total"] == 5
    assert progress["finish"]["permalink"].endswith("/l/manualtoken2")


def test_a_cancelled_hand_typed_stay_does_not_satisfy_the_calendar_step():
    owner_id = auth.create_account("onboard-cancelled", "Secure-Password-123", role="host")
    entity_id = _entity(owner_id)
    apartment_id = _unique_apartment(owner_id, entity_id, "manualtoken3")
    stay_id = _manual_stay(apartment_id, "hand-typed-3")
    db.update("reservation", stay_id, {"status": "cancelled"})

    assert onboarding.progress(owner_id)["current"]["id"] == "calendars"


def test_the_calendar_step_offers_adding_a_stay_by_hand():
    owner_id = auth.create_account(
        "onboard-manual-copy",
        "Secure-Password-123",
        role="host",
        must_change_password=False,
    )
    entity_id = _entity(owner_id)
    _unique_apartment(owner_id, entity_id, "manualtoken4")
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )

    page = client.get("/onboarding?lang=en")

    assert page.status_code == 200
    assert "Connect Airbnb or Booking.com — or add a direct booking by hand." in page.text
    assert "Add a stay by hand" in page.text
    assert 'href="/reservations#add-stay-panel"' in page.text

    czech = client.get("/onboarding?lang=cs")

    assert "Připojte Airbnb nebo Booking.com — nebo přidejte přímou rezervaci ručně." in czech.text
    assert "Přidat pobyt ručně" in czech.text


def test_the_police_reporting_step_points_at_the_property_page():
    """The credentials and the address are both on the property page, and the
    automation card only carries the credentials, so that is where the step has
    to land."""
    owner_id = auth.create_account("onboard-ubyport", "Secure-Password-123", role="host")
    entity_id = _entity(owner_id)
    apartment_id = _unique_apartment(owner_id, entity_id, "ubyportstep1")

    progress = onboarding.progress(owner_id)
    step = progress["steps"][3]

    assert step["id"] == "automation"
    assert step["url"] == f"/apartments/{apartment_id}#ubyport"


def test_the_police_reporting_step_is_named_for_what_it_asks_for():
    owner_id = auth.create_account(
        "onboard-ubyport-copy",
        "Secure-Password-123",
        role="host",
        must_change_password=False,
    )
    entity_id = _entity(owner_id)
    _unique_apartment(owner_id, entity_id, "ubyportstep2")
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )

    english = client.get("/onboarding?lang=en")

    assert "Police reporting details" in english.text

    czech = client.get("/onboarding?lang=cs")

    assert "Údaje pro hlášení policii" in czech.text


def test_the_police_reporting_step_without_a_property_offers_creating_one():
    owner_id = auth.create_account("onboard-ubyport-none", "Secure-Password-123", role="host")
    _entity(owner_id)

    assert onboarding.progress(owner_id)["current"]["id"] == "property"
    assert onboarding.progress(owner_id)["steps"][3]["url"] == "/apartments/new"
