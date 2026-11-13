"""Task 1173b: the "door code not confirmed" card closes when its stay has a new code, is revoked or expires.

The card is raised by _tell_host_unverified (task 1168) with the key door_code_pin_unverified:<reservation>.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app import alerts, db, deadlines, door_codes, ttlock
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401
from tests.test_ttlock_lock_setup import _moved_stay

OLD = "2000-01-01T00:00:00+00:00"
CARD = "door_code_pin_unverified"


@pytest.fixture
def lock(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "code-1"))
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: None)


def _row(row_id: int):
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))


def _card(stay: int) -> None:
    apartment = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))["apartment_id"]
    alerts.raise_alert(
        "warning", CARD, "Door code could not be confirmed on the lock",
        dedupe_key=f"{CARD}:{stay}", apartment_id=apartment, reservation_id=stay,
    )


def _open(stay: int):
    return alerts.open_alert(f"{CARD}:{stay}")


def _issued_stay(monkeypatch):
    """A stay with an issued code on its own window (no move pending)."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("1111111", "c1"))
    _, _, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["state"] == door_codes.ISSUED
    return stay, int(row["id"])


def test_the_unconfirmed_card_closes_when_a_move_makes_a_new_code(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    _card(stay)
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("2222222", "code-2"))
    door_codes.reconcile()
    assert _open(stay) is None


def test_the_unconfirmed_card_closes_when_a_lost_code_is_issued_again(monkeypatch, lock):
    stay, row_id = _issued_stay(monkeypatch)
    _card(stay)
    db.execute(
        "UPDATE door_code SET state = ?, pin_enc = NULL, provider_code_id = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = 'pin_lost' WHERE id = ?",
        (door_codes.PENDING, row_id),
    )
    assert door_codes.issue(row_id, allow_gateway=True)
    assert _open(stay) is None


def test_the_unconfirmed_card_closes_when_the_stay_is_cancelled(monkeypatch):
    stay, _ = _issued_stay(monkeypatch)
    _card(stay)
    door_codes.reconcile()
    assert _open(stay) is not None  # the code is still issued: the card stays
    db.execute("UPDATE reservation SET status = 'cancelled' WHERE id = ?", (stay,))
    door_codes.reconcile()
    assert _open(stay) is None


def test_the_unconfirmed_card_closes_when_the_code_expires(monkeypatch):
    stay, row_id = _issued_stay(monkeypatch)
    _card(stay)
    today = deadlines.local_now().date()
    db.execute(  # the stay is over: no move is wanted, the code's window has ended
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
    )
    db.execute("UPDATE door_code SET valid_to = ? WHERE id = ?", (OLD, row_id))
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert _open(stay) is None
