"""Setup wizard shell: welcome through bookings."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app import auth, config, db, onboarding
from app.main import app


def setup_module():
    db.init_db()


def _session_client(username: str) -> TestClient:
    owner_id = auth.create_account(f"{username}@example.test", "", role="host", username=username)
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(auth.SESSION_COOKIE, auth.issue_session(owner_id, account["session_version"]))
    client.owner_id = owner_id
    return client


def _add_entity(owner_id: int, name: str = "Wizard Operator s.r.o.") -> int:
    return db.insert(
        "legal_entity",
        {
            "name": name,
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "wizard-operator@example.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )


def _walk_to_address(client: TestClient, name: str = "Flat Vinohrady") -> int:
    client.post("/setup/welcome", follow_redirects=False)
    entity_id = _add_entity(client.owner_id)
    response = client.post(
        "/setup/name",
        data={"internal_name": name, "legal_entity_id": str(entity_id)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    apartment = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ? ORDER BY id DESC LIMIT 1",
        (name,),
    )
    assert apartment
    return apartment["id"]


def test_setup_resume_after_name_lands_on_address():
    client = _session_client("wizard-resume")
    _walk_to_address(client)
    response = client.get("/setup", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/setup/address")


def test_name_step_refuses_a_name_without_an_operator():
    """0088: the wizard no longer creates a name-only property."""
    client = _session_client("wizard-name-only")
    client.post("/setup/welcome", follow_redirects=False)
    response = client.post(
        "/setup/name",
        data={"internal_name": "Studio Karlín", "active": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Add an operator to continue." in response.text
    assert 'value="Studio Karlín"' in response.text
    assert db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ?", ("Studio Karlín",)
    ) is None


def test_name_step_creates_property_with_name_and_operator():
    client = _session_client("wizard-name-operator")
    entity_id = _add_entity(client.owner_id)
    page = client.get("/setup/name")
    assert page.text.count('name="legal_entity_id"') == 1
    assert f'<option value="{entity_id}" selected>' in page.text
    response = client.post(
        "/setup/name",
        data={"internal_name": "Studio Karlín 2", "legal_entity_id": str(entity_id), "active": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one(
        "SELECT * FROM apartment WHERE internal_name = ?", ("Studio Karlín 2",)
    )
    assert row
    assert row["active"] == 1
    assert row["legal_entity_id"] == entity_id
    assert row["data_controller_entity_id"] is None
    assert row["automation_mode"] == "manual"


def test_name_step_refuses_a_foreign_operator():
    other = _session_client("wizard-name-foreign-owner")
    foreign_entity = _add_entity(other.owner_id, "Foreign s.r.o.")
    client = _session_client("wizard-name-foreign")
    _add_entity(client.owner_id, "Mine A")
    _add_entity(client.owner_id, "Mine B")
    response = client.post(
        "/setup/name",
        data={"internal_name": "Foreign flat", "legal_entity_id": str(foreign_entity)},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Choose the operator for this property." in response.text
    assert "Foreign s.r.o." not in response.text
    assert db.query_one("SELECT id FROM apartment WHERE internal_name = ?", ("Foreign flat",)) is None


_ADDR_FIELDS = {
    "addr_okres",
    "addr_obec",
    "addr_obec_cast",
    "addr_street",
    "addr_house_no",
    "addr_orient_no",
    "addr_zip",
}


def _row_without_address(row) -> dict:
    skip = _ADDR_FIELDS | {"updated_at"}
    data = dict(row)
    return {key: value for key, value in data.items() if key not in skip}


def test_setup_address_save_leaves_other_property_fields_intact():
    client = _session_client("wizard-address-preserve")
    apartment_id = _walk_to_address(client, "Configured flat")
    db.update(
        "apartment",
        apartment_id,
        {
            "uby_idub": "123456789012",
            "uby_ws_user": "UBY-WSabcdef",
            "uby_ws_password_enc": db.encrypt_secret("secret-pass"),
            "guest_message": "Welcome message",
            "automation_mode": "scheduled",
            "submit_after_hours": 12,
            "default_purpose": "10",
            "stay_fee_rate_czk": 50,
            "lock_provider": "ttlock",
            "lock_id": "lock-123",
            "addr_street": "Old street",
            "addr_house_no": "1",
            "addr_zip": "12000",
            "addr_obec": "Praha",
        },
    )
    before = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))

    response = client.post(
        "/setup/address",
        data={
            "internal_name": before["internal_name"],
            "active": "1",
            "addr_street": "New street",
            "addr_house_no": "99",
            "addr_zip": "11000",
            "addr_obec": "Praha",
            "addr_okres": "Praha",
            "return_to": "/setup/bookings",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert after["addr_street"] == "New street"
    assert after["addr_house_no"] == "99"
    assert after["addr_zip"] == "11000"
    assert _row_without_address(before) == _row_without_address(after)


def test_setup_address_rejects_invalid_address_without_changing_row():
    client = _session_client("wizard-address-reject")
    apartment_id = _walk_to_address(client, "Reject flat")
    db.update(
        "apartment",
        apartment_id,
        {
            "addr_street": "Keep me",
            "addr_house_no": "5",
            "addr_zip": "12000",
            "addr_obec": "Praha",
        },
    )
    before = dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))

    response = client.post(
        "/setup/address",
        data={
            "internal_name": before["internal_name"],
            "active": "1",
            "addr_street": "Broken",
            "addr_house_no": "",
            "addr_zip": "",
            "addr_obec": "Praha",
            "return_to": "/setup/bookings",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert 'class="wizard-error"' in response.text
    after = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert dict(after) == before


def test_address_step_uses_property_validation():
    client = _session_client("wizard-address-validation")
    apartment_id = _walk_to_address(client)
    response = client.post(
        "/setup/address",
        data={
            "internal_name": "Flat Vinohrady",
            "active": "1",
            "addr_street": "Main",
            "addr_house_no": "1",
            "addr_zip": "12345",
            "addr_obec": "Prague",
            "return_to": "/setup/bookings",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one("SELECT addr_zip FROM apartment WHERE id = ?", (apartment_id,))
    assert row["addr_zip"] == "12345"


def test_another_owner_cannot_reach_foreign_property_wizard():
    owner_a = _session_client("wizard-owner-a")
    _walk_to_address(owner_a, "Owner A flat")
    owner_b = _session_client("wizard-owner-b")
    response = owner_b.get("/setup/address", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/setup/name")
    row = db.query_one("SELECT internal_name FROM apartment WHERE internal_name = ?", ("Owner A flat",))
    assert row
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM apartment WHERE internal_name = ?",
        ("Owner A flat",),
    )["n"] == 1


def test_sync_failure_shows_friendly_error_and_removes_feed(monkeypatch):
    client = _session_client("wizard-sync-fail")
    apartment_id = _walk_to_address(client)
    db.execute(
        "UPDATE apartment SET addr_street = ?, addr_house_no = ?, addr_zip = ?, addr_obec = ? WHERE id = ?",
        ("Street", "12", "12000", "Prague", apartment_id),
    )
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "http://testserver")

    def _fail_sync(_apartment_id):
        return {"created": 0, "updated": 0, "errors": 1}

    with patch("app.routes.setup_wizard.validate_calendar_url", lambda url: url):
        with patch("app.routes.setup_wizard.icalsync.sync_all", _fail_sync):
            client.post("/setup/bookings", data={"source": "airbnb"}, follow_redirects=False)
            response = client.post(
                "/setup/bookings",
                data={
                    "source": "airbnb",
                    "url": "https://example.test/calendar.ics",
                },
                follow_redirects=False,
            )
    assert response.status_code == 400
    assert "could not read" in response.text.lower()
    feeds = db.query("SELECT id FROM ical_feed WHERE apartment_id = ?", (apartment_id,))
    assert feeds == []


def test_setup_address_page_has_structured_fields_only():
    client = _session_client("wizard-structured-address")
    _walk_to_address(client)
    page = client.get("/setup/address")
    assert page.status_code == 200
    assert 'name="address_line"' not in page.text
    assert 'id="addr_obec"' in page.text
    assert "wizard-preview" not in page.text


def test_wizard_screens_work_without_javascript():
    client = _session_client("wizard-no-js")
    for path in ("/setup/welcome",):
        page = client.get(path)
        assert page.status_code == 200
        assert 'method="post"' in page.text
    _walk_to_address(client)
    for path in ("/setup/name?edit=1", "/setup/address", "/setup/bookings"):
        page = client.get(path)
        assert page.status_code == 200
        assert "<form" in page.text


def test_wizard_step_progress():
    owner_id = auth.create_account("wizard-step@example.test", "", role="host", username="wizard-step")
    assert onboarding.wizard_step(owner_id) == "name"
    apartment_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "X",
            "permalink_token": "tok1234567",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    assert onboarding.wizard_step(owner_id) == "address"
    db.execute(
        "UPDATE apartment SET addr_street = 'S', addr_house_no = '1', addr_zip = '11000', addr_obec = 'Praha' "
        "WHERE id = ?",
        (apartment_id,),
    )
    assert onboarding.wizard_step(owner_id) == "bookings"
