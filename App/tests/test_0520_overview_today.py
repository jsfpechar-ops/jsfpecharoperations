"""0520: the Overview has a quiet month line, a Today table, and one header button."""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, reporting
from app.main import app
from tests.conftest import login_as

USERNAME = "overview-today-host"
OTHER = "overview-today-other"


def _owner_id(username):
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"]


def _cleanup():
    for username in (USERNAME, OTHER):
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
            user_id = row["id"]
            db.execute(
                "DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
                "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)",
                (user_id,),
            )
            db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
            db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _property(owner_id: int, token: str) -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Overview s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@overview.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Overview Flat",
            "permalink_token": token,
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Overview Flat",
            "uby_contact": "host@overview.test",
            "addr_okres": "Praha 2",
            "addr_obec": "Praha",
            "addr_obec_cast": "Vinohrady",
            "addr_street": "Korunní",
            "addr_house_no": "1234",
            "addr_orient_no": "12a",
            "addr_zip": "12000",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password_enc": db.encrypt_secret("demo-password"),
        },
    )


def _stay(apartment_id: int, uid: str, date_from: date, nights: int, source: str = "manual") -> int:
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": source,
            "uid": uid,
            "date_from": date_from.isoformat(),
            "date_to": (date_from + timedelta(days=nights)).isoformat(),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def _guest(reservation_id: int, surname: str, submit_state=reporting.PENDING, submitted_at=None) -> int:
    return db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": surname,
            "first_name": "Sample",
            "birth_date": "1990-02-03",
            "nationality": "CZE",
            "doc_number": "TEST-123",
            "purpose": "10",
            "submit_state": submit_state,
            "submitted_at": submitted_at,
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Overview Host", username=USERNAME)
    auth.create_account(f"{OTHER}@example.test", "Other Host", username=OTHER)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_month_line_shows_guests_nights_and_reports(host):
    today = date.today()
    apartment_id = _property(_owner_id(USERNAME), "overviewtoday1")
    stay = _stay(apartment_id, "month-1", today.replace(day=1), 3)
    _guest(stay, "Month One", reporting.SENT, db.utcnow())
    _guest(stay, "Month Two")

    page = host.get("/?lang=en").text

    assert "data-dashboard-month" in page
    line = page[page.index("data-dashboard-month"):][:900]
    assert re.findall(r"<b>(\d+)</b>", line) == ["2", "3", "1"], line


def test_today_table_lists_arrivals_and_departures_today_only(host):
    today = date.today()
    apartment_id = _property(_owner_id(USERNAME), "overviewtoday2")
    arrive = _stay(apartment_id, "today-arrive", today, 2)
    depart = _stay(apartment_id, "today-depart", today - timedelta(days=2), 2)
    tomorrow = _stay(apartment_id, "tomorrow-arrive", today + timedelta(days=1), 2)

    page = host.get("/?lang=en").text

    start = page.index('class="dashboard-today"')
    table = page[start:page.index("</section>", start)]
    assert f"/reservations/{arrive}" in table
    assert f"/reservations/{depart}" in table
    assert f"/reservations/{tomorrow}" not in table


def test_order_is_needs_you_month_calendar_today(host):
    today = date.today()
    apartment_id = _property(_owner_id(USERNAME), "overviewtoday3")
    _stay(apartment_id, "order-overdue", today - timedelta(days=5), 2)

    page = host.get("/?lang=en").text

    needs = page.index('class="needs-you"')
    month = page.index("data-dashboard-month")
    calendar = page.index('id="calendar"')
    today_table = page.index('class="dashboard-today"')
    assert needs < month < calendar < today_table


def test_no_add_cleaning_button_and_no_more_actions_menu(host):
    apartment_id = _property(_owner_id(USERNAME), "overviewtoday4")
    _stay(apartment_id, "buttons-1", date.today(), 1)

    page = host.get("/?lang=en").text

    assert ">Add cleaning<" not in page
    assert 'data-toggle-panel="dashboard-more"' not in page
    assert "dashboard-more" not in page
    assert "ui-ph-menu" not in page


def test_month_summary_ignores_demo_stays_and_other_owners(host):
    today = date.today()
    start = today.replace(day=1)
    owner_id = _owner_id(USERNAME)
    other_id = _owner_id(OTHER)
    mine = _property(owner_id, "overviewtoday5")
    theirs = _property(other_id, "overviewtoday6")

    demo = _stay(mine, "demo-1", start, 4, source="demo")
    _guest(demo, "Demo Guest", reporting.SENT, db.utcnow())
    other = _stay(theirs, "other-1", start, 5)
    _guest(other, "Other Guest", reporting.SENT, db.utcnow())

    assert reporting.month_summary(owner_id, today) == {"guests": 0, "nights": 0, "reported": 0}

    own = _stay(mine, "own-1", start, 2)
    _guest(own, "Own Guest")
    assert reporting.month_summary(owner_id, today) == {"guests": 1, "nights": 2, "reported": 0}
    assert reporting.month_summary(other_id, today) == {"guests": 1, "nights": 5, "reported": 1}
