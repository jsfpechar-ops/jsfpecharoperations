"""Calendar range, ownership, truthfulness, and canonical manual creation."""
from __future__ import annotations

import secrets
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, db, onboarding
from app.main import app
from app.routes import dashboard_calendar
from tests.conftest import login_as


@pytest.fixture(scope="module")
def calendar_workspace():
    db.init_db()
    suffix = secrets.token_hex(5)
    owner = auth.create_account(f"calendar-{suffix}@example.test", "Calendar Review",
                                role="host", username=f"calendar-{suffix}")
    other = auth.create_account(f"calendar-other-{suffix}@example.test", "Other Review",
                                role="host", username=f"calendar-other-{suffix}")
    now = db.utcnow()
    entity = db.insert("legal_entity", {"name": "Calendar Review", "owner_user_id": owner, "created_at": now})

    def property_row(name, owner_id=owner, active=1, archived=None):
        return db.insert("apartment", {
            "internal_name": name, "owner_user_id": owner_id, "legal_entity_id": entity,
            "active": active, "archived_at": archived, "created_at": now,
            "automation_mode": "manual", "permalink_token": secrets.token_hex(12),
        })

    properties = [property_row(f"Calendar home {index}") for index in (1, 2, 3)]
    inactive = property_row("Inactive home", active=0)
    archived = property_row("Archived home", archived=now)
    foreign = property_row("Other workspace home", owner_id=other)
    client = TestClient(app)
    response = login_as(client, f"calendar-{suffix}", url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    onboarding.set_dismissed(owner, True)
    yield {"client": client, "owner": owner, "properties": properties,
           "inactive": inactive, "archived": archived, "foreign": foreign}
    ids = [*properties, inactive, archived, foreign]
    for apartment_id in ids:
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity,))
    for owner_id in (owner, other):
        db.execute("DELETE FROM settings WHERE key = ?", (f"onboarding_dismissed_{owner_id}",))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def make_stay(apartment, start="2026-10-03", end="2026-10-07", **values):
    return db.insert("reservation", {
        "apartment_id": apartment, "uid": secrets.token_hex(16), "source": "manual",
        "date_from": start, "date_to": end, "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(), **values,
    })


def calendar_get(client, **params):
    return client.get("/dashboard/calendar", params={"from": "2026-10-01", "to": "2026-11-01", **params})


def create(client, apartment, start, end, **values):
    return client.post("/reservations", headers={"Accept": "application/json"}, data={
        "calendar": "1", "apartment_id": str(apartment), "date_from": start, "date_to": end, **values,
    })


@pytest.mark.parametrize("start,end", [
    ("2026-02-30", "2026-03-03"), ("20261001", "2026-10-02"),
    ("2026-10-02", "2026-10-02"), ("2026-10-03", "2026-10-02"),
    ("1899-12-31", "1900-01-02"), ("2101-12-31", "2102-01-01"),
    ("2026-01-01", "2028-01-01"), ("", "2026-10-02"),
])
def test_invalid_ranges_are_bounded_and_strict(start, end):
    with pytest.raises(ValueError):
        dashboard_calendar.parse_range(start, end)


def test_leap_year_and_prague_dst_are_date_only():
    assert dashboard_calendar.parse_range("2028-02-28", "2028-03-01") == (date(2028, 2, 28), date(2028, 3, 1))
    assert (dashboard_calendar.parse_range("2026-10-24", "2026-10-27")[1] - date(2026, 10, 24)).days == 3


def test_anonymous_calendar_requires_login():
    db.init_db()
    response = TestClient(app).get("/dashboard/calendar?from=2026-10-01&to=2026-11-01", follow_redirects=False)
    assert response.status_code == 303
    assert "/login" in response.headers["location"]


def test_calendar_is_owner_scoped_and_checkout_exclusive(calendar_workspace):
    ws = calendar_workspace
    owned = make_stay(ws["properties"][0], guest_email="never-serialize@example.test", host_note="private note")
    long_stay = make_stay(ws["properties"][1], "2026-09-01", "2026-12-01")
    excluded = [
        make_stay(ws["foreign"]), make_stay(ws["inactive"]), make_stay(ws["archived"]),
        make_stay(ws["properties"][0], status="cancelled"),
        make_stay(ws["properties"][0], status="ignored"),
        make_stay(ws["properties"][0], archived_at=db.utcnow()),
        make_stay(ws["properties"][0], "2026-09-28", "2026-10-01"),
        make_stay(ws["properties"][0], "2026-11-01", "2026-11-04"),
    ]
    response = calendar_get(ws["client"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    ids = {event["id"] for event in data["events"]}
    assert {owned, long_stay} <= ids
    assert not ids.intersection(excluded)
    assert {item["id"] for item in data["properties"]} == set(ws["properties"])
    assert "never-serialize" not in response.text
    assert "private note" not in response.text
    assert "permalink" not in response.text
    filtered = calendar_get(ws["client"], property=ws["properties"][1]).json()["events"]
    assert filtered and {event["propertyId"] for event in filtered} == {ws["properties"][1]}


@pytest.mark.parametrize("which", ["foreign", "inactive", "archived"])
def test_foreign_and_unavailable_property_filters_do_not_leak(calendar_workspace, which):
    assert calendar_get(calendar_workspace["client"], property=calendar_workspace[which]).status_code == 404


@pytest.mark.parametrize("params", [{"property": "no"}, {"property": "-1"}, {"from": "bad"}, {"to": "2029-01-01"}])
def test_bad_calendar_queries_return_validation_errors(calendar_workspace, params):
    assert calendar_get(calendar_workspace["client"], **params).status_code == 422


def test_filed_stays_are_never_painted_overdue(calendar_workspace, monkeypatch):
    ws = calendar_workspace
    stay = make_stay(ws["properties"][2], "2027-01-01", "2027-01-04")
    monkeypatch.setattr(dashboard_calendar.reporting, "reservation_progress",
                        lambda *args: {"guests": [], "expected": 2, "filled": 2, "status": "reported"})
    monkeypatch.setattr(dashboard_calendar.reporting, "deadline_cell", lambda *args: {"level": "overdue"})
    events = dashboard_calendar.events(ws["owner"], date(2027, 1, 1), date(2027, 1, 5))
    event = next(event for event in events if event["id"] == stay)
    assert event["tone"] == "done"


def test_demo_ready_is_preview_not_ready(calendar_workspace, monkeypatch):
    ws = calendar_workspace
    stay = make_stay(ws["properties"][2], "2027-02-01", "2027-02-04")
    monkeypatch.setattr(dashboard_calendar.reporting, "reservation_progress",
                        lambda *args: {"guests": [], "expected": None, "filled": 0, "status": "ready"})
    monkeypatch.setattr(dashboard_calendar.reporting, "deadline_cell", lambda *args: {"level": "future"})
    monkeypatch.setattr(dashboard_calendar.demo, "is_demo_stay", lambda *args: True)
    event = next(event for event in dashboard_calendar.events(ws["owner"], date(2027, 2, 1), date(2027, 2, 5)) if event["id"] == stay)
    assert event["preview"] and event["tone"] == "neutral"


@pytest.mark.parametrize("guest_count", ["0", "61", "abc", "2.5"])
def test_calendar_creation_rejects_bad_headcounts(calendar_workspace, guest_count):
    ws = calendar_workspace
    response = create(ws["client"], ws["properties"][0], "2027-04-01", "2027-04-03", expected_guests=guest_count)
    assert response.status_code == 422
    assert "expected_guests" in response.json()["errors"]


@pytest.mark.parametrize("which", ["foreign", "inactive", "archived"])
def test_calendar_cannot_create_in_unavailable_properties(calendar_workspace, which):
    response = create(calendar_workspace["client"], calendar_workspace[which], "2027-04-01", "2027-04-03")
    assert response.status_code == 422
    assert "apartment_id" in response.json()["errors"]


def test_calendar_creation_rejects_bad_dates_and_missing_csrf(calendar_workspace):
    ws = calendar_workspace
    bad = create(ws["client"], ws["properties"][0], "2026-02-30", "2026-03-03")
    assert bad.status_code == 422 and "date_to" in bad.json()["errors"]
    before = db.query_one("SELECT COUNT(*) AS n FROM reservation")["n"]
    response = create(ws["client"], ws["properties"][0], "2027-04-01", "2027-04-03", _csrf="")
    assert response.status_code != 201
    assert db.query_one("SELECT COUNT(*) AS n FROM reservation")["n"] == before


def test_calendar_saves_via_canonical_manual_creation(calendar_workspace):
    ws = calendar_workspace
    response = create(ws["client"], ws["properties"][0], "2027-05-11", "2027-05-14",
                      expected_guests="2", summary="Direct booking", guest_email="direct@example.test")
    assert response.status_code == 201
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (response.json()["id"],))
    assert row["source"] == "manual" and row["status"] == "active"
    assert row["apartment_id"] == ws["properties"][0]
    assert row["date_from"] == "2027-05-11" and row["date_to"] == "2027-05-14"
    assert row["expected_guests_override"] == 2 and row["summary"] == "Direct booking"
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["url"].startswith(f"/reservations/{row['id']}")


def test_adjacent_stays_are_allowed_and_overlaps_require_confirmation(calendar_workspace):
    ws = calendar_workspace
    property_id = ws["properties"][1]
    make_stay(property_id, "2027-06-20", "2027-06-22")
    adjacent = create(ws["client"], property_id, "2027-06-22", "2027-06-24")
    assert adjacent.status_code == 201
    before = db.query_one("SELECT COUNT(*) AS n FROM reservation")["n"]
    conflict = create(ws["client"], property_id, "2027-06-21", "2027-06-23")
    assert conflict.status_code == 409 and conflict.json()["overlap"]
    assert db.query_one("SELECT COUNT(*) AS n FROM reservation")["n"] == before
    accepted = create(ws["client"], property_id, "2027-06-21", "2027-06-23", allow_overlap="1")
    assert accepted.status_code == 201


def test_calendar_payload_is_not_capped_at_five_stays(calendar_workspace):
    ws = calendar_workspace
    ids = {make_stay(ws["properties"][2], f"2027-07-{day:02d}", f"2027-07-{day + 1:02d}") for day in range(1, 15)}
    data = calendar_get(ws["client"], **{"from": "2027-07-01", "to": "2027-08-01"}).json()
    assert ids <= {event["id"] for event in data["events"]}


def test_manual_stay_can_cross_years_without_broadening_calendar_reads(calendar_workspace):
    ws = calendar_workspace
    response = create(ws["client"], ws["properties"][0], "2029-01-01", "2030-06-01")
    assert response.status_code == 201
    stay_id = response.json()["id"]
    window = calendar_get(ws["client"], **{"from": "2030-05-01", "to": "2030-06-01"})
    assert stay_id in {event["id"] for event in window.json()["events"]}
    unbounded = calendar_get(ws["client"], **{"from": "2029-01-01", "to": "2030-06-01"})
    assert unbounded.status_code == 422


def test_calendar_dashboard_renders_with_only_its_own_fixture(calendar_workspace):
    response = calendar_workspace["client"].get("/?lang=en")
    assert response.status_code == 200
    assert 'data-calendar data-today=' in response.text
    assert 'data-cal-properties' in response.text
