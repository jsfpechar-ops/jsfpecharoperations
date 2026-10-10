"""A guest nobody registered is now a row on the stay, not an absence [C-37].

With 1 of 2 filled only one card rendered, so the missing guest was invisible:
there was nothing on the page to act on. The placeholder rows count the same
people as the stay-fee headcount warning, so the two wordings agree.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n, reporting
from app.main import app
from tests.test_send_controls import _seed
from tests.conftest import login_as

USERNAME = "missing-guest-rows-host"
TOKEN = "missingrows1"


def _owner_id() -> int:
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if existing:
        return existing["id"]
    return auth.create_account(f"{USERNAME}@example.test", "Missing Rows", username=USERNAME)


def _cleanup():
    rows = db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    for row in rows:
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?))",
            (user_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (user_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def stay():
    """One registered guest, three declared, logged in as the owner."""
    db.init_db()
    _cleanup()
    owner_id = _owner_id()
    _apartment, reservation, _guest_id = _seed("manual", TOKEN, owner_user_id=owner_id)
    db.update("reservation", reservation["id"], {"expected_guests_override": 3})
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client, reservation
    finally:
        _cleanup()


def _placeholder_rows(html: str) -> list[str]:
    return re.findall(r'<li class="guest-card placeholder">.*?</li>', html, re.S)


def test_the_missing_guests_get_a_row_each(stay):
    client, reservation = stay

    page = client.get(f"/reservations/{reservation['id']}")

    assert page.status_code == 200
    rows = _placeholder_rows(page.text)
    assert len(rows) == 2, "three declared guests, one registered, two rows expected"


def test_the_rows_are_numbered_after_the_guests_that_exist(stay):
    client, reservation = stay

    page = client.get(f"/reservations/{reservation['id']}")

    assert host_i18n.translate("en", "stay.detail.guests.placeholder", n=2) in page.text
    assert host_i18n.translate("en", "stay.detail.guests.placeholder", n=3) in page.text
    assert "Guest 1: not registered yet" not in page.text


def test_a_czech_host_reads_the_rows_in_czech(stay):
    client, reservation = stay

    page = client.get(f"/reservations/{reservation['id']}?lang=cs")

    assert "Host č. 2: zatím neregistrován" in page.text
    assert "Host č. 3: zatím neregistrován" in page.text


def test_each_row_carries_both_ways_to_fill_it(stay):
    client, reservation = stay

    page = client.get(f"/reservations/{reservation['id']}")

    rows = _placeholder_rows(page.text)
    assert rows, "no placeholder rows to inspect"
    for row in rows:
        assert host_i18n.STRINGS["en"]["host.copy_guest_form_link"] in row
        assert 'data-copy="stay-link"' in row
        assert host_i18n.STRINGS["en"]["stay.detail.guests.add_by_hand"] in row
        assert f'href="/reservations/{reservation["id"]}/guests/new"' in row


def test_the_rows_count_the_people_the_stay_fee_warning_counts(stay):
    """Both places name `expected - guests`; they must not disagree."""
    client, reservation = stay
    progress = reporting.reservation_progress(
        db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation["id"],))
    )

    rows = _placeholder_rows(client.get(f"/reservations/{reservation['id']}").text)

    assert progress["not_registered"] == len(rows)
    assert progress["not_registered"] == progress["expected"] - len(progress["guests"])


def test_a_fully_declared_stay_gets_no_placeholder_rows(stay):
    client, reservation = stay
    db.update("reservation", reservation["id"], {"expected_guests_override": 1})

    page = client.get(f"/reservations/{reservation['id']}")

    assert page.status_code == 200
    assert _placeholder_rows(page.text) == []


def test_an_unknown_headcount_guesses_nothing(stay):
    """With no expected count there is no fact to state, so no row is invented."""
    client, reservation = stay
    db.update("reservation", reservation["id"], {"expected_guests_override": None})

    page = client.get(f"/reservations/{reservation['id']}")

    assert _placeholder_rows(page.text) == []


def test_the_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["stay.detail.guests.placeholder"] == (
        "Guest %(n)s: not registered yet"
    )
    assert host_i18n.STRINGS["cs"]["stay.detail.guests.placeholder"] == (
        "Host č. %(n)s: zatím neregistrován"
    )
    assert host_i18n.STRINGS["en"]["stay.detail.guests.add_by_hand"] == "Add by hand"
    assert host_i18n.STRINGS["cs"]["stay.detail.guests.add_by_hand"] == "Přidat ručně"


def test_the_row_does_not_read_as_a_guest_record(stay):
    """It is a slot to fill, so it drops the card elevation."""
    client, reservation = stay

    page = client.get(f"/reservations/{reservation['id']}")

    assert '<li class="guest-card placeholder">' in page.text
