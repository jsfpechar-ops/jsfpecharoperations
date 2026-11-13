"""Task 1173: rows that cannot be issued never starve newer rows; ended stays expire.

issue() puts a row back to pending for not_eligible, no_account and bad_window without a try on the lock.
Before 1173 such a row stayed due and was taken again on every tick, so BATCH of them blocked every newer row.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import alerts, db, deadlines, door_codes, ttlock
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


# --- 1173c ---------------------------------------------------------------------------------------------


def _released() -> int:
    """A row issue() put back for not_eligible: attempts 0 again, its backoff over (due long ago)."""
    row_id = _stuck("not_eligible")
    db.execute("UPDATE door_code SET last_error = 'not_eligible' WHERE id = ?", (row_id,))
    return row_id


def test_released_rows_sort_after_new_rows_and_real_retries(monkeypatch):
    """25 released rows are older than a new row and a real retry; they still go last (1173c)."""
    monkeypatch.setattr(door_codes, "BATCH", 3)
    for _ in range(25):
        _released()
    _, _, stay = _stay(registered_minutes_ago=5)
    retry_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 2, last_error = 'network', next_attempt_at = ? WHERE id = ?",
        (door_codes.RETRYING, OLD, retry_id),
    )
    new_id = _healthy()
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert len(seen) == 3 and new_id in seen and retry_id in seen
    assert seen[:2] == [new_id, retry_id]  # new rows, then real retries, then released rows


def test_a_pending_row_of_a_stay_that_ends_today_is_not_expired(lock):
    """The test is date_to < today (the one _eligible_sql uses), not <=: the check-out day is still live."""
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=2)).isoformat(), today.isoformat(), stay),
    )
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", (OLD, row_id))
    assert door_codes._expire_ended_stays(db.utcnow()) == 0
    assert _row(row_id)["state"] == door_codes.PENDING


@pytest.mark.parametrize(
    "change",
    ["status = 'cancelled'", "archived_at = '2026-01-01T00:00:00+00:00'"],
    ids=["cancelled", "archived"],
)
def test_a_cancelled_or_archived_ended_stay_is_revoked_not_expired(lock, change):
    """_expire_ended_stays leaves it to _handle_cancellations: the row ends revoked (1173c)."""
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute(
        f"UPDATE reservation SET {change}, date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
    )
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", (OLD, row_id))
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.REVOKED


def _expired_unissued(stay_end_offset_days: int):
    """A stay whose row expired before any code was made, then its dates changed to end today + offset."""
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute("UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ? WHERE id = ?", (door_codes.EXPIRED, OLD, row_id))
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today + timedelta(days=stay_end_offset_days)).isoformat(), stay),
    )
    return stay, row_id


def test_an_expired_row_without_a_code_comes_back_when_the_stay_is_extended(lock):
    stay, old_id = _expired_unissued(2)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["state"] == door_codes.ISSUED and row["provider_code_id"] == "code-1"
    assert db.query_one(
        "SELECT 1 AS n FROM audit WHERE action = 'door_code_reset' AND detail = ?", (f"door_code={old_id}",)
    )


def test_an_expired_row_stays_expired_when_its_window_has_ended(monkeypatch, lock):
    """date_to is today, so the stay is eligible, but the window ended: reviving it would loop every tick."""
    _, row_id = _expired_unissued(0)
    monkeypatch.setattr(ttlock, "stay_window", lambda *a, **k: (0, 1))
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED


def test_an_expired_row_that_had_a_code_stays_expired(lock):
    _, row_id = _expired_unissued(2)
    db.execute("UPDATE door_code SET provider_code_id = 'code-9' WHERE id = ?", (row_id,))  # issued, then expired
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED


# --- 1173d ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE reservation SET status = 'cancelled' WHERE id = ?",
        "UPDATE reservation SET registration_completed_at = NULL WHERE id = ?",
    ],
)
def test_an_expired_row_of_a_stay_that_is_not_eligible_is_not_revived(lock, change):
    """The window is ahead, but the stay is cancelled or not registered: the eligibility clause keeps the row."""
    stay, row_id = _expired_unissued(2)
    db.execute(change, (stay,))
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED


def _reset_audited(row_id: int):
    return db.query_one(
        "SELECT 1 AS n FROM audit WHERE action = 'door_code_reset' AND detail = ?", (f"door_code={row_id}",)
    )


def test_an_expired_row_is_kept_when_the_plan_does_not_allow_ttlock(monkeypatch, lock):
    """ensure_row would never make a new row for this owner: deleting would leave the stay with none (1173d)."""
    _, row_id = _expired_unissued(2)
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: False)
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert _reset_audited(row_id) is None


def test_a_broken_lock_account_deletes_the_expired_row_and_the_host_is_told(lock):
    """Plan allows TTLock, account not ok: the row goes so _alert_delayed raises the card (1173e)."""
    stay, row_id = _expired_unissued(2)
    db.execute(
        "UPDATE lock_account SET status = 'error' WHERE owner_user_id = "
        "(SELECT a.owner_user_id FROM apartment a JOIN reservation r ON r.apartment_id = a.id WHERE r.id = ?)",
        (stay,),
    )
    assert door_codes._revive_unissued_expired() == 1
    assert _row(row_id) is None
    assert _reset_audited(row_id)
    door_codes.reconcile()
    card = alerts.open_alert(f"door_code_delayed:{stay}")
    assert card is not None and "reason=not_set_up" in card["detail"]


def test_an_expired_row_is_revived_when_the_owner_can_hold_a_code(lock):
    _, row_id = _expired_unissued(2)
    assert door_codes._revive_unissued_expired() == 1
    assert _row(row_id) is None
    assert _reset_audited(row_id)


def test_the_due_query_follows_the_number_of_release_reasons(monkeypatch):
    """The IN list is built from RELEASE_REASONS: a fourth reason must not break the bindings (1173d)."""
    monkeypatch.setattr(door_codes, "RELEASE_REASONS", (*door_codes.RELEASE_REASONS, "other_release"))
    retry_id = _healthy()
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 1, last_error = 'network', next_attempt_at = ? WHERE id = ?",
        (door_codes.RETRYING, OLD, retry_id),
    )
    released_id = _stuck("not_eligible")
    db.execute("UPDATE door_code SET last_error = 'other_release' WHERE id = ?", (released_id,))
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert seen.index(retry_id) < seen.index(released_id)  # the fourth reason ranks last too
