"""Brief 0228: exactly four events reach the host's phone, once each."""
from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

import pytest

from app import auth, config, db, push
from tests.test_push import Browser

APP = Path(__file__).resolve().parent.parent / "app"


@pytest.fixture(autouse=True)
def push_on(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "WEB_PUSH", True)
    yield


@pytest.fixture
def stay():
    username = f"pe{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Push Events", role="host", username=username)
    apartment_id = db.insert("apartment", {
        "internal_name": "Byt Vinohrady", "owner_user_id": owner,
        "permalink_token": f"pe{secrets.token_hex(5)}", "active": 1, "created_at": db.utcnow(),
    })
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "uid": f"pe-{secrets.token_hex(6)}",
        "date_from": "2026-10-24", "date_to": "2026-10-26",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    push.save_subscription(owner, Browser().subscription(), lang="en", device="iPhone")
    yield {"owner": owner, "apartment_id": apartment_id, "reservation_id": reservation_id}
    db.execute("DELETE FROM push_outbox WHERE user_account_id = ?", (owner,))
    db.execute("DELETE FROM push_subscription WHERE user_account_id = ?", (owner,))


def _queued(owner):
    return db.query(
        "SELECT kind, url, params FROM push_outbox WHERE user_account_id = ? ORDER BY id", (owner,)
    )


def test_a_door_code_problem_is_pushed_once_per_stay(stay):
    assert push.door_code_missing(stay["reservation_id"]) == 1
    assert push.door_code_missing(stay["reservation_id"]) == 0
    [row] = _queued(stay["owner"])
    assert row["kind"] == "door_code" and row["url"] == f"/reservations/{stay['reservation_id']}"
    assert "24.10.2026" in row["params"] and "Byt Vinohrady" in row["params"]


def test_a_cancelled_stay_with_guests_is_pushed_once(stay):
    assert push.cancelled_with_guests(stay["apartment_id"], stay["reservation_id"]) == 1
    assert push.cancelled_with_guests(stay["apartment_id"], stay["reservation_id"]) == 0
    assert _queued(stay["owner"])[0]["kind"] == "cancelled_with_guests"


def test_a_deadline_at_risk_is_pushed_once_with_the_deadline(stay):
    record = {
        "owner_user_id": stay["owner"], "reservation_id": stay["reservation_id"],
        "property": "Byt Vinohrady", "arrival": datetime(2026, 10, 24),
        "deadline": datetime(2026, 10, 27, 23, 59),
    }
    assert push.deadline_at_risk(record) == 1
    assert push.deadline_at_risk(record) == 0
    [row] = _queued(stay["owner"])
    assert "27.10.2026 23:59" in row["params"]


def test_a_filing_problem_is_pushed_once_per_property_and_day(stay):
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (stay["apartment_id"],))
    assert push.filing_problem(apartment, None) == 1
    assert push.filing_problem(apartment, None) == 0
    [row] = _queued(stay["owner"])
    assert row["kind"] == "filing_problem" and row["url"] == "/reservations"


def test_the_helpers_never_raise(stay):
    assert push.door_code_missing(-1) == 0
    assert push.deadline_at_risk({"reservation_id": 1}) == 0
    assert push.filing_problem(None, None) == 0


def test_each_event_is_wired_exactly_once_next_to_its_e_mail():
    sources = {
        "reporting.py": "push.filing_problem(",
        "filing_watchdog.py": "push.deadline_at_risk(",
        "door_codes.py": "push.door_code_missing(",
        "icalsync.py": "push.cancelled_with_guests(",
    }
    for name, call in sources.items():
        assert (APP / name).read_text(encoding="utf-8").count(call) == 1, name
    # Nothing else in the app queues a push.
    callers = [
        path.name for path in APP.rglob("*.py")
        if "push.notify(" in path.read_text(encoding="utf-8") and path.name != "push.py"
    ]
    assert callers == []
