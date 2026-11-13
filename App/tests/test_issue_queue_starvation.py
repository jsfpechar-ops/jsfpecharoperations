"""Task 1173: rows that cannot be issued never starve newer rows; ended stays expire.

issue() puts a row back to pending for not_eligible, no_account and bad_window without a try on the lock.
Before 1173 such a row stayed due and was taken again on every tick, so BATCH of them blocked every newer row.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db, deadlines, door_codes, ttlock
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401

OLD = "2000-01-01T00:00:00+00:00"


def _stuck(reason: str) -> int:
    """A pending row that issue() cannot issue for ``reason``; due long ago, never tried."""
    owner, apartment, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    if reason == "not_eligible":
        db.execute("UPDATE reservation SET registration_completed_at = NULL WHERE id = ?", (stay,))
    elif reason == "no_account":
        db.execute("UPDATE lock_account SET status = 'error' WHERE owner_user_id = ?", (owner,))
    else:
        db.execute("UPDATE apartment SET checkin_hour = 99 WHERE id = ?", (apartment,))
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", (OLD, row_id))
    return row_id


def _healthy() -> int:
    _, _, stay = _stay(registered_minutes_ago=1)
    return door_codes.ensure_row(stay)  # a new row: attempts 0, next_attempt_at = now


def _row(row_id: int):
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))


def _in(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(microsecond=0).isoformat()


@pytest.fixture
def lock(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "code-1"))
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: None)


def test_stuck_rows_do_not_starve_a_healthy_new_row(monkeypatch, lock):
    monkeypatch.setattr(door_codes, "BATCH", 3)
    stuck = [_stuck("not_eligible") for _ in range(4)]  # more than one batch
    healthy = _healthy()
    door_codes._issue_due(db.utcnow())  # the first 3 stuck rows are tried and put off
    assert _row(healthy)["state"] == door_codes.PENDING
    door_codes._issue_due(db.utcnow())  # 1 stuck row left: the healthy row fits in the batch
    assert _row(healthy)["state"] == door_codes.ISSUED  # never, before 1173: the stuck rows stay first
    assert all(_row(r)["state"] == door_codes.PENDING for r in stuck)


@pytest.mark.parametrize(
    "reason, minutes", [("not_eligible", 15), ("no_account", 15), ("bad_window", 60)]
)
def test_a_released_row_waits_its_backoff_before_it_is_taken_again(monkeypatch, lock, reason, minutes):
    row_id = _stuck(reason)
    seen = []
    real = door_codes.issue
    monkeypatch.setattr(
        door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or real(rid, allow_gateway=allow_gateway)
    )
    door_codes._issue_due(db.utcnow())
    row = _row(row_id)
    assert seen == [row_id] and row["state"] == door_codes.PENDING and row["last_error"] == reason
    assert row["attempts"] == 0  # the release still takes back the attempt
    wait = datetime.fromisoformat(row["next_attempt_at"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=minutes - 1) < wait <= timedelta(minutes=minutes)
    door_codes._issue_due(_in(minutes - 2))
    assert seen == [row_id]  # not taken before the backoff ends
    door_codes._issue_due(_in(minutes + 1))
    assert seen == [row_id, row_id]  # taken again afterwards


def test_a_new_row_is_taken_before_repeated_retries(monkeypatch):
    """New rows are inserted with next_attempt_at = now, which sorts after every older retry."""
    monkeypatch.setattr(door_codes, "BATCH", 3)
    for _ in range(5):
        _, _, stay = _stay(registered_minutes_ago=5)
        row_id = door_codes.ensure_row(stay)
        db.execute(
            "UPDATE door_code SET state = ?, attempts = 2, next_attempt_at = ? WHERE id = ?",
            (door_codes.RETRYING, OLD, row_id),
        )
    new_id = _healthy()
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert len(seen) == 3 and new_id in seen  # fails on SQLite and PostgreSQL without the attempts order


def test_pending_and_retrying_rows_of_an_ended_stay_expire_and_live_ones_do_not(lock):
    today = deadlines.local_now().date()
    ids = {}
    for name, state in (("pending", door_codes.PENDING), ("retrying", door_codes.RETRYING)):
        _, _, stay = _stay(registered_minutes_ago=30)
        row_id = door_codes.ensure_row(stay)  # the stay is live now, so the row can be made
        db.execute("UPDATE door_code SET state = ?, next_attempt_at = ? WHERE id = ?", (state, OLD, row_id))
        db.execute(
            "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
            ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
        )
        ids[name] = row_id
    live = _healthy()
    counts = door_codes.reconcile()
    assert _row(ids["pending"])["state"] == door_codes.EXPIRED
    assert _row(ids["retrying"])["state"] == door_codes.EXPIRED
    assert counts["expired"] == 2
    assert _row(live)["state"] == door_codes.ISSUED
