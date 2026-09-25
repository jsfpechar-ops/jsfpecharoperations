"""Double-clicking "Create stay" must not answer with a server error.

The manual uid used to be ``manual-{db.utcnow()}-{date_from}``, which has
one-second resolution, so two identical POSTs inside the same second collided on
``UNIQUE(apartment_id, uid)`` and the second one died with a 500 - after the
first had already created the stay. The uid is a random token now, and the
button in the panel goes quiet while its own submission is on the way.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "manual-stay-uid-host"
APP_JS = Path("app/static/app.js")


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (user_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _apartment_id() -> int:
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    return db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Manual Stay Flat",
            "permalink_token": "manualstayuid1",
            "permalink_pin": "1234",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Manual Stay Host", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _payload(apartment_id: int) -> dict:
    start = date.today() + timedelta(days=7)
    return {
        "apartment_id": str(apartment_id),
        "date_from": start.isoformat(),
        "date_to": (start + timedelta(days=3)).isoformat(),
        "summary": "Direct booking",
    }


def test_two_identical_clicks_do_not_produce_a_server_error(host):
    """The impatient re-click is the case the audit reproduced."""
    apartment_id = _apartment_id()
    payload = _payload(apartment_id)

    first = host.post("/reservations", data=payload, follow_redirects=False)
    second = host.post("/reservations", data=payload, follow_redirects=False)

    assert first.status_code == 303, first.text
    assert second.status_code == 303, second.text
    assert second.headers["location"].startswith("/reservations/")


def test_two_identical_clicks_create_two_separate_stays(host):
    """Both clicks are real bookings, so both have to exist."""
    apartment_id = _apartment_id()
    payload = _payload(apartment_id)

    host.post("/reservations", data=payload, follow_redirects=False)
    host.post("/reservations", data=payload, follow_redirects=False)

    rows = db.query(
        "SELECT uid FROM reservation WHERE apartment_id = ? ORDER BY id", (apartment_id,)
    )
    assert len(rows) == 2
    assert rows[0]["uid"] != rows[1]["uid"]


def test_the_uid_is_a_random_token_not_a_timestamp(host):
    apartment_id = _apartment_id()

    host.post("/reservations", data=_payload(apartment_id), follow_redirects=False)

    uid = db.query_one("SELECT uid FROM reservation WHERE apartment_id = ?", (apartment_id,))["uid"]
    assert re.fullmatch(r"manual-[0-9a-f]{16}", uid), uid


def test_the_panel_button_is_disabled_while_its_form_is_submitting():
    """The visible half of the fix: one click, one effect."""
    script = APP_JS.read_text()

    assert ".action-panel form" in script
    assert "initSubmitGuard();" in script
    assert "data-submit-guard" in script


def test_the_guard_leaves_a_submit_another_handler_owns():
    """A confirm dialog may hand the submission back, so it must not disable early."""
    script = APP_JS.read_text()

    guard = script.split("function initSubmitGuard()", 1)[1].split("\n  }", 1)[0]
    assert "event.defaultPrevented" in guard


def test_a_restored_page_gets_its_button_back():
    """Coming back with the back button must not leave a dead button behind."""
    script = APP_JS.read_text()

    assert 'addEventListener("pageshow"' in script
