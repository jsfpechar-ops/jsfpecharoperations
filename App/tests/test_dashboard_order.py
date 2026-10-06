"""An overdue stay outranks the "you are ready" card on the Overview.

Once setup finished, the tall green finish card sat above an overdue stay until
the host clicked "Skip setup guidance", so the page's most urgent action was
pushed below the fold. The focus card now comes first, and the finish card either
shrinks to one line or moves below the work queue.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "dashboard-order-host"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _ready_workspace(token: str) -> int:
    """An entity, a property that passes validation, and nothing else."""
    owner_id = _owner_id()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Order s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@order.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Order Flat",
            "permalink_token": token,
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Order Flat",
            "uby_contact": "host@order.test",
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


def _stay(apartment_id: int, uid: str, days_from_today: int) -> int:
    start = date.today() + timedelta(days=days_from_today)
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": uid,
            "date_from": start.isoformat(),
            "date_to": (start + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Order Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_an_overdue_stay_comes_before_the_finish_card(host):
    apartment_id = _ready_workspace("dashboardorder1")
    _stay(apartment_id, "overdue-order-1", -5)

    page = host.get("/?lang=en")

    assert page.status_code == 200
    focus = page.text.index('id="needs-action"')
    strip = page.text.index("Setup is done. Your guest link and PIN are ready.")
    assert focus < strip, "the finish card is still outranking an overdue stay"


def test_an_overdue_stay_shrinks_the_finish_card_to_one_line(host):
    apartment_id = _ready_workspace("dashboardorder2")
    _stay(apartment_id, "overdue-order-2", -5)

    page = host.get("/?lang=en")

    assert 'class="onboarding-finish"' not in page.text, "the tall finish card is back"
    assert "Setup is done. Your guest link and PIN are ready." in page.text
    assert "Show link" in page.text


def test_the_one_line_finish_card_still_reaches_the_guest_link(host):
    apartment_id = _ready_workspace("dashboardorder3")
    _stay(apartment_id, "overdue-order-3", -5)

    page = host.get("/?lang=en")

    assert f'href="/apartments/{apartment_id}#communication"' in page.text


def test_the_finish_card_keeps_its_room_when_nothing_is_overdue(host):
    apartment_id = _ready_workspace("dashboardorder4")
    _stay(apartment_id, "future-order-4", 10)

    page = host.get("/?lang=en")

    assert 'class="onboarding-finish"' in page.text
    assert "Setup is done. Your guest link and PIN are ready." not in page.text
    queue = page.text.index('id="needs-action"')
    finish = page.text.index('class="onboarding-finish"')
    assert finish > queue, "the finish card still sits above the work queue"


def test_the_one_line_finish_card_is_in_czech(host):
    apartment_id = _ready_workspace("dashboardorder6")
    _stay(apartment_id, "overdue-order-6", -5)

    page = host.get("/?lang=cs")

    assert "Nastavení je hotové. Odkaz a PIN pro hosty jsou připravené." in page.text
    assert "Zobrazit odkaz" in page.text
