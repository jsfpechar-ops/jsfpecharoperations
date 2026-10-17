"""An unknown guest headcount should read as unknown, not as "0 / ?".

The Overview and Stays lists printed "0 / ?" and left the host to guess what the
question mark meant. The Czech focus card's note counted
"%(filled)s / %(expected)s formulářů hostů",
so one registered guest read incorrectly. The Overview stays quiet until the
count is declared; tables show a quiet dash with the meaning for screen readers.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "overview-headcount-host"
UNKNOWN_EN = "Number of guests not known yet"
UNKNOWN_CS = "Počet hostů zatím neznáme"
LIST_DASH = '<span class="muted" aria-hidden="true">–</span><span class="sr-only">{text}</span>'


def _cleanup(apartment_id: int) -> None:
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM legal_entity WHERE id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL) "
        "AND owner_user_id = (SELECT id FROM user_account WHERE username = ?)",
        (USERNAME,),
    )


def _cleanup_owner(owner_id: int, remove_account: bool = False) -> None:
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
    if remove_account:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _seed_unknown_headcount(token: str):
    """Seed an active stay owned by the authenticated host in the test."""
    db.init_db()
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    assert owner, "the headcount fixture must have an owner-scoped host"
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": f"Headcount {token}", "seat": "Praha", "ico": "12345678",
        "contact_email": "headcount@example.test", "owner_user_id": owner["id"],
        "created_at": now,
    })
    apartment_id = db.insert("apartment", {
        "legal_entity_id": entity_id, "owner_user_id": owner["id"],
        "internal_name": f"Headcount {token}", "permalink_token": token,
        "permalink_pin": "123456", "automation_mode": "manual", "active": 1,
        "created_at": now,
    })
    today = claim.prague_today()
    db.insert("reservation", {
        "apartment_id": apartment_id, "source": "manual", "uid": f"stay-{token}",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=2)).isoformat(),
        "status": "active", "expected_guests_override": None,
        "created_at": now, "updated_at": now,
    })
    return apartment_id


@pytest.fixture
def host():
    """A host-scoped dashboard so these assertions exercise the owned stay."""
    db.init_db()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if existing:
        _cleanup_owner(existing["id"])
    else:
        auth.create_account(
            f"{USERNAME}@example.test", "Headcount Host", role="host", username=USERNAME
        )
    client = TestClient(app)
    response = login_as(client, USERNAME, follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
        if owner:
            _cleanup_owner(owner["id"], remove_account=True)


def test_the_overview_says_nothing_about_an_unknown_headcount(host):
    apartment = _seed_unknown_headcount("ux147-dash")
    try:
        english = host.get("/?lang=en").text
        czech = host.get("/?lang=cs").text

        assert "0 / ?" not in english
        assert UNKNOWN_EN not in english
        assert UNKNOWN_CS not in czech
    finally:
        _cleanup(apartment)


def test_the_reservations_list_shows_a_quiet_dash(host):
    apartment = _seed_unknown_headcount("ux147-list")
    try:
        page = host.get("/reservations?lang=en").text

        assert LIST_DASH.format(text=UNKNOWN_EN) in page
        assert "0 / ?" not in page
    finally:
        _cleanup(apartment)


def test_a_known_headcount_shows_the_count(host):
    apartment = _seed_unknown_headcount("ux147-known")
    reservation = db.query_one("SELECT id FROM reservation WHERE apartment_id = ?", (apartment,))
    db.update("reservation", reservation["id"], {"expected_guests_override": 3})
    try:
        page = host.get("/?lang=en").text

        assert "0 / 3" in page
    finally:
        _cleanup(apartment)


def test_the_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["common.guests_unknown"] == UNKNOWN_EN
    assert host_i18n.STRINGS["cs"]["common.guests_unknown"] == UNKNOWN_CS
