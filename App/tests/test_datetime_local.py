"""The host reads Prague times, not raw UTC.

Every timestamp the app stores comes from ``db.utcnow()``, so a batch that left
at 19:37 Prague summer time was printed as "17:37" — two hours off. The
``datetime_local`` filter converts on the way out; these tests pin the
conversion and prove the pages actually go through it.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import auth, db, templating
from app.main import app

TOKEN = "datetimelocaltoken"
PASSWORD = "Date-Time-Local-Password-123"
USERNAME = "datetime-local-admin"

# 17:37 UTC is 19:37 in Prague in summer, 18:37 in winter.
SUMMER_UTC = "2026-09-24T17:37:00+00:00"
SUMMER_PRAGUE = "2026-09-24 19:37"
WINTER_UTC = "2026-01-15T17:37:00+00:00"
WINTER_PRAGUE = "2026-01-15 18:37"
LATE_UTC = "2026-09-24T22:30:00+00:00"
LATE_PRAGUE = "2026-09-25 00:30"


def _local(value, seconds: bool = False) -> str:
    return templating.templates.env.from_string("{{ v | datetime_local(s) }}").render(
        v=value, s=seconds
    )


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    if not account:
        return auth.create_account(
            USERNAME,
            PASSWORD,
            "Date time local admin",
            role="admin",
            must_change_password=False,
        )
    return account["id"]


def _browser() -> TestClient:
    _ensure_admin()
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))


def _seed() -> dict:
    """One reported guest and one sent report, both stamped 17:37 UTC."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    today = date.today()
    apartment_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Local time flat",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "datetime-local-stay",
            "date_from": (today + timedelta(days=5)).isoformat(),
            "date_to": (today + timedelta(days=7)).isoformat(),
            "summary": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Local",
            "first_name": "Test",
            "nationality": "CZE",
            "purpose": "10",
            "entered_by": "guest",
            "submit_state": "sent",
            "submitted_at": SUMMER_UTC,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "mode": "manual_bulk",
            "state": "sent",
            "created_at": SUMMER_UTC,
            "finished_at": SUMMER_UTC,
        },
    )
    return {"apartment_id": apartment_id, "reservation_id": reservation_id}


def test_a_summer_timestamp_is_shown_two_hours_later():
    assert _local(SUMMER_UTC) == SUMMER_PRAGUE


def test_a_winter_timestamp_is_shown_one_hour_later():
    assert _local(WINTER_UTC) == WINTER_PRAGUE


def test_a_late_evening_timestamp_rolls_into_the_next_day():
    assert _local(LATE_UTC) == LATE_PRAGUE


def test_the_seconds_variant_keeps_the_seconds():
    assert _local(SUMMER_UTC, seconds=True) == "2026-09-24 19:37:00"


def test_a_timestamp_without_an_offset_is_read_as_utc():
    assert _local("2026-09-24T17:37:00") == SUMMER_PRAGUE


def test_a_missing_timestamp_renders_nothing():
    assert _local(None) == ""
    assert _local("") == ""


def test_an_unreadable_timestamp_is_shown_as_stored():
    assert _local("not a timestamp") == "not a timestamp"


def test_a_reported_guest_shows_the_prague_time():
    seeded = _seed()
    try:
        page = _browser().get(f"/reservations/{seeded['reservation_id']}")
        assert page.status_code == 200
        assert SUMMER_PRAGUE in page.text
        assert "17:37" not in page.text
    finally:
        _cleanup()


def test_the_reports_list_shows_the_prague_time():
    _seed()
    try:
        page = _browser().get("/submissions")
        assert page.status_code == 200
        assert SUMMER_PRAGUE in page.text
        assert "17:37" not in page.text
    finally:
        _cleanup()
