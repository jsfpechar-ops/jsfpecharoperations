"""Regressions from the host-reported UI pass.

Each of these was a real complaint: a demo date left on the sign-in page, a copy
button whose label burst out of its border, a sidebar shortcut that appeared on
some pages but not others, and a guest form that named the property the way the
police register does instead of the way the guest booked it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app import auth, db
from app.main import app

USERNAME = "ui-consistency"
PASSWORD = "Ui-Consistency-Password-123"
APARTMENT_NAME = "Downtown Comfort in a Spacious Apartment"
REGISTERED_NAME = "BYT C. 1"


def _subtitle(page) -> str:
    """The line under the guest form heading: which property is this."""
    return page.text.split('class="g-facility">', 1)[1].split("</p>", 1)[0]


@pytest.fixture(scope="module")
def client():
    db.init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def host(client):
    """A signed-in administrator with one named apartment, cleaned up after."""
    account = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not account:
        auth.create_account(
            USERNAME, PASSWORD, "UI consistency", role="admin", must_change_password=False
        )
        account = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    response = client.post(
        "/login", data={"username": USERNAME, "password": PASSWORD}, follow_redirects=False
    )
    assert response.status_code == 303
    created = client.post(
        "/apartments",
        data={
            "internal_name": APARTMENT_NAME,
            "city_en": "Prague",
            "uby_name": REGISTERED_NAME,
            "active": "1",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    yield client
    for table in ("apartment", "legal_entity", "alert", "audit"):
        db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (account["id"],))
    db.execute("DELETE FROM user_account WHERE id = ?", (account["id"],))


def test_the_sign_in_page_has_no_leftover_demo_date(client):
    page = client.get("/login")

    assert page.status_code == 200
    assert "Sep 12" not in page.text
    assert "auth-float-booking" not in page.text
    # The other float badge belongs there; only the date was the problem.
    assert "auth-float-ready" in page.text


def test_no_shell_template_hardcodes_a_demo_date():
    """Two shells drifted once already; the login page kept a date for a year."""
    offenders = [
        path.name for path in Path("app/templates").rglob("*.html") if "Sep 12" in path.read_text()
    ]

    assert not offenders, f"hardcoded demo dates left in: {offenders}"


def test_properties_and_search_are_on_every_host_page(host):
    """It is part of the sidebar, so no page may depend on a route passing it."""
    for path in ("/", "/reservations", "/housebook", "/guest-links", "/automation"):
        page = host.get(path)

        assert page.status_code == 200, path
        assert 'href="/apartments"' in page.text
        assert 'data-command-open' in page.text
        assert 'class="property-switcher"' not in page.text


def test_the_copy_button_keeps_its_icon_when_it_confirms(host):
    page = host.get("/guest-links")

    assert "data-copy-label-slot" in page.text
    # The confirmation goes in the slot; the icon stays where it is.
    button = page.text.split("data-copy-label-slot", 1)[0].rsplit("<button", 1)[1]
    assert "<svg" in button


def test_the_guest_form_names_the_apartment_the_host_chose(host):
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE internal_name = ?", (APARTMENT_NAME,)
    )
    page = host.get(f"/l/{apartment['permalink_token']}")

    assert page.status_code == 200
    assert _subtitle(page) == f"{APARTMENT_NAME}, Prague"


def test_the_guest_form_falls_back_to_the_registered_name(host):
    """A property named before this field existed still identifies itself."""
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE internal_name = ?", (APARTMENT_NAME,)
    )
    db.execute("UPDATE apartment SET internal_name = '' WHERE id = ?", (apartment["id"],))
    try:
        page = host.get(f"/l/{apartment['permalink_token']}")

        assert page.status_code == 200
        assert _subtitle(page) == f"{REGISTERED_NAME}, Prague"
    finally:
        db.execute(
            "UPDATE apartment SET internal_name = ? WHERE id = ?",
            (APARTMENT_NAME, apartment["id"]),
        )
