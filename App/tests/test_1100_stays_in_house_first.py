"""1100: the stays list shows stays in the flat today first, then upcoming, then past.

Order inside each group: in house by leaving date (soonest first), upcoming by
arrival (soonest first), past by departure (most recent first). The order is
set in SQL, so paging cuts the same sequence on every page.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, deadlines, host_i18n, reporting
from app.main import app
from app.routes import admin
from tests.conftest import login_as

USERNAME = "stays-in-house-host"
TOKEN = "staysinhousefirsttoken"

_ENTITY_ID: int | None = None

# surname -> (days from today to arrival, days from today to departure, already filed)
STAYS = {
    "STAYA": (-2, 3, False),   # in house, leaves in 3 days
    "STAYB": (-2, 1, False),   # in house, leaves tomorrow
    "STAYC": (10, 12, False),  # arrives in 10 days
    "STAYD": (2, 4, False),    # arrives in 2 days
    "STAYE": (-8, -5, True),   # left 5 days ago (filed, so not overdue)
    "STAYF": (-25, -20, True),  # left 20 days ago (filed, so not overdue)
}
ALL_IN_ORDER = ["STAYB", "STAYA", "STAYD", "STAYC", "STAYE", "STAYF"]


def _cleanup():
    global _ENTITY_ID
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if apartment:
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    if _ENTITY_ID is not None:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (_ENTITY_ID,))
        _ENTITY_ID = None


def _seed() -> TestClient:
    global _ENTITY_ID
    db.init_db()
    _cleanup()
    now = db.utcnow()
# Prague civil date — same clock urgency() and the stays list use. UTC
    # date.today() on CI runners lags Prague near midnight and can make the
    # in-house stays look overdue, crowding the overdue past stay off page 1.
    today = deadlines.local_now().date()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    user_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{USERNAME}@example.test", "Stays Order Host", username=USERNAME)
    )
    _ENTITY_ID = db.insert(
        "legal_entity",
        {"name": "Stays Order s.r.o.", "owner_user_id": user_id, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": _ENTITY_ID,
            "owner_user_id": user_id,
            "internal_name": "Order 1",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "uby_mark": "DEMO2",
            "active": 1,
            "created_at": now,
        },
    )
    for surname, (arrive, leave, filed) in STAYS.items():
        reservation_id = db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": f"order-{surname}",
                "date_from": (today + timedelta(days=arrive)).isoformat(),
                "date_to": (today + timedelta(days=leave)).isoformat(),
                "status": "active",
                "expected_guests_override": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": surname,
                "first_name": "TEST",
                "birth_date": "01011990",
                "nationality": "VNM",
                "doc_number": "P9988771",
                "res_street": "Le Loi 5",
                "res_city": "Hanoi",
                "res_country": "VNM",
                "purpose": "10",
                "is_lead": 1,
                "entered_by": "guest",
                "signature_png": "imported",
                "signed_at": now,
                "passport_photo_at": now,
                "identity_verified_at": now,
                "submit_state": reporting.SENT if filed else reporting.PENDING,
                "submitted_at": now if filed else None,
                "created_at": now,
                "updated_at": now,
            },
        )
    client = TestClient(app)
    login_as(client, USERNAME, follow_redirects=False)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client


@pytest.fixture
def stays_client(monkeypatch):
    # All six stays on one page (the real page size is 5), so the order is visible whole.
    monkeypatch.setattr(admin, "RESERVATION_PAGE_SIZE", 10)
    client = _seed()
    yield client
    _cleanup()


def _order(page: str, names: list[str]) -> list[str]:
    """The surnames that appear on the page, in the order they appear."""
    present = [name for name in names if name in page]
    return sorted(present, key=page.index)


def test_range_all_lists_in_house_then_upcoming_then_past(stays_client):
    page = stays_client.get("/reservations?range=all").text
    assert _order(page, ALL_IN_ORDER) == ALL_IN_ORDER


def test_default_view_shows_in_house_then_upcoming_and_no_past(stays_client):
    page = stays_client.get("/reservations").text
    assert _order(page, ALL_IN_ORDER) == ["STAYB", "STAYA", "STAYD", "STAYC"]


def test_range_past_lists_most_recent_departure_first(stays_client):
    page = stays_client.get("/reservations?range=past").text
    assert _order(page, ALL_IN_ORDER) == ["STAYE", "STAYF"]


def test_range_current_lists_soonest_leaving_first(stays_client):
    page = stays_client.get("/reservations?range=current").text
    assert _order(page, ALL_IN_ORDER) == ["STAYB", "STAYA"]


def test_paging_cuts_the_same_sequence(stays_client, monkeypatch):
    monkeypatch.setattr(admin, "RESERVATION_PAGE_SIZE", 2)
    first = stays_client.get("/reservations?range=all").text
    second = stays_client.get("/reservations?range=all&page=2").text
    assert _order(first, ALL_IN_ORDER) == ["STAYB", "STAYA"]
    assert _order(second, ALL_IN_ORDER) == ["STAYD", "STAYC"]


def test_overdue_unfiled_stay_comes_first_and_stays_on_page_one(stays_client, monkeypatch):
    # 1100 step 3: an overdue unfiled past stay stays on page 1 of the default
    # view. The phone list regroups in-house ("today") ahead of past overdue
    # ("earlier"), so STAYB appears before STAYOVERDUE even when only the past
    # stay is past its police deadline. Seed dates use Prague civil time so a
    # UTC CI runner near midnight does not also mark STAYA overdue and push
    # STAYOVERDUE onto page 2.
    monkeypatch.setattr(admin, "RESERVATION_PAGE_SIZE", 2)
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    now = db.utcnow()
    today = deadlines.local_now().date()
    arrival = today - timedelta(days=12)
    departure = today - timedelta(days=10)
    assert deadlines.reporting_deadline(arrival) < deadlines.local_now()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment["id"],
            "source": "manual",
            "uid": "order-STAYOVERDUE",
            "date_from": arrival.isoformat(),
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
            "reservation_id": reservation_id,
            "surname": "STAYOVERDUE",
            "first_name": "TEST",
            "birth_date": "01011990",
            "nationality": "VNM",
            "doc_number": "P9988773",
            "res_street": "Le Loi 5",
            "res_city": "Hanoi",
            "res_country": "VNM",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "signature_png": "imported",
            "signed_at": now,
            "passport_photo_at": now,
            "identity_verified_at": now,
            "stay_from": arrival.isoformat(),
            "stay_to": departure.isoformat(),
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    page = stays_client.get("/reservations").text
    assert _order(page, ["STAYOVERDUE", "STAYB", "STAYA", "STAYD", "STAYC"]) == [
        "STAYB",
        "STAYOVERDUE",
    ]
    assert "STAYA" not in page
