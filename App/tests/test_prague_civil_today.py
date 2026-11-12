"""Regression: host UI clocks use Prague civil time, not the server UTC date.

Merged 2026-11-12 (PR #921): UTC ``date.today()`` near midnight made in-house
stays look overdue on the stays list and skewed dashboard windows. These tests
pin the three entry points that were fixed together.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, deadlines, reporting, templating
from app.main import app
from tests.conftest import login_as

PRAGUE_MIDNIGHT = datetime(2026, 11, 12, 0, 30)
PRAGUE_DATE = PRAGUE_MIDNIGHT.date()
UTC_LAG_DATE = date(2026, 11, 11)

USERNAME = "prague-today-host"
TOKEN = "praguetodaytoken"


def test_template_globals_use_prague_civil_clock(monkeypatch):
    monkeypatch.setattr(deadlines, "local_now", lambda now=None: PRAGUE_MIDNIGHT)
    assert templating.templates.env.globals["today"]() == PRAGUE_DATE
    assert templating.templates.env.globals["now"]() == PRAGUE_MIDNIGHT


def test_dashboard_rows_window_uses_prague_civil_today(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "dash-prague-today.sqlite3")
    db.init_db()
    monkeypatch.setattr(deadlines, "local_now", lambda now=None: PRAGUE_MIDNIGHT)

    captured: list[tuple] = []

    def spy(query, params=()):
        captured.append(params)
        return []

    monkeypatch.setattr(db, "query", spy)
    reporting.dashboard_rows(overview=False)

    start = (PRAGUE_DATE - timedelta(days=45)).isoformat()
    end = (PRAGUE_DATE + timedelta(days=21)).isoformat()
    assert captured, "dashboard_rows must query reservations"
    assert captured[0][2:] == (start, end)


def _seed_past_stay(surname: str, departure: date) -> TestClient:
    db.init_db()
    now = db.utcnow()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if existing:
        owner_id = existing["id"]
    else:
        owner_id = auth.create_account(
            f"{USERNAME}@example.test", "Prague Today Host", username=USERNAME
        )
    entity_id = db.insert(
        "legal_entity",
        {"name": "Prague Today s.r.o.", "owner_user_id": owner_id, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Prague flat",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "prague-past",
            "date_from": (departure - timedelta(days=2)).isoformat(),
            "date_to": departure.isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": db.query_one(
                "SELECT id FROM reservation WHERE apartment_id = ? ORDER BY id DESC LIMIT 1",
                (apartment_id,),
            )["id"],
            "surname": surname,
            "first_name": "TEST",
            "birth_date": "01011990",
            "nationality": "VNM",
            "doc_number": "P1111222",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "created_at": now,
            "updated_at": now,
        },
    )
    client = TestClient(app)
    login_as(client, USERNAME)
    return client


def test_stays_list_past_uses_prague_yesterday(monkeypatch):
    """Past range must cut off at Prague yesterday, not the server UTC date."""
    monkeypatch.setattr(deadlines, "local_now", lambda now=None: PRAGUE_MIDNIGHT)
    expected_cutoff = (PRAGUE_DATE - timedelta(days=1)).isoformat()
    captured: list[tuple] = []

    orig_one = db.query_one

    def spy_one(sql, params=()):
        if "date_to <=" in sql:
            captured.append(tuple(params))
        return orig_one(sql, params)

    monkeypatch.setattr(db, "query_one", spy_one)

    yesterday_prague = PRAGUE_DATE - timedelta(days=1)
    client = _seed_past_stay("PRAGUEPAST", yesterday_prague)
    page = client.get("/reservations?range=past").text
    assert "PRAGUEPAST" in page
    wrong_cutoff = (UTC_LAG_DATE - timedelta(days=1)).isoformat()
    assert captured, "past filter must bind a departure cutoff"
    assert any(expected_cutoff in params for params in captured)
    assert not any(wrong_cutoff in params for params in captured)


def _cleanup():
    try:
        owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    except Exception:
        return
    if not owner:
        return
    owner_id = owner["id"]
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE a.owner_user_id = ?)",
        (owner_id,),
    )
    db.execute(
        "DELETE FROM reservation WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id = ?)",
        (owner_id,),
    )
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))


@pytest.fixture(autouse=True)
def _clear_prague_today_data():
    _cleanup()
    yield
    _cleanup()
