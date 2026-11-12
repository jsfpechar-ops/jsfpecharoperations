"""1155b: a stay cancelled again deletes a code that is already gone: that is success.

A fake lock holds the PINs. Deleting a PIN that is not there raises an errcode the repo
does not map (-3999 here), like TTLock's answer for a missing code.
"""
from __future__ import annotations

import pytest

from app import config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state
from tests.test_door_code_lost_pin import FakeLock, _row

UNMAPPED = -3999


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = FakeLock()
    lock.lookups = 0
    lock.lookup_error = None
    notices: list = []

    def delete(account_id, lock_id, code_id, priority=None):
        if str(code_id) not in lock.pins:
            raise ttlock.TTLockError("no such passcode", code=UNMAPPED, kind="transient")
        lock.pins.pop(str(code_id))

    def listed(account_id, lock_id, name, code_id):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        return str(code_id) in lock.pins

    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "delete_code", delete)
    monkeypatch.setattr(ttlock, "code_is_listed", listed)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", lambda row_id, kind: notices.append(kind))
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    db.execute("UPDATE door_code SET valid_from = ? WHERE id = ?", ("2098-12-30T00:00:00+00:00", row))
    yield lock, stay, row, notices
    _purge()


def test_deleting_a_code_that_is_already_gone_counts_as_revoked(world):
    lock, stay, row, notices = world
    lock.pins.clear()
    revoked = _audits("door_code_revoked")
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKED and after["pin_enc"] is None
    assert _audits("door_code_revoked") == revoked + 1
    assert notices == ["cancelled_deleted"] and lock.lookups == 1


def test_a_timed_out_delete_then_a_retry_that_finds_the_code_gone_is_revoked(world, monkeypatch):
    lock, stay, row, notices = world
    real = ttlock.delete_code

    def timeout_after_delete(*a, **k):
        real(*a, **k)
        raise ttlock.TTLockError("timeout", kind="network")

    monkeypatch.setattr(ttlock, "delete_code", timeout_after_delete)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.pins == {}
    monkeypatch.setattr(ttlock, "delete_code", real)
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKED
    assert "cancelled_not_deleted" not in notices


def test_an_unmapped_refusal_while_the_code_is_still_on_the_lock_is_retried(world, monkeypatch):
    lock, stay, row, notices = world

    def refuse(*a, **k):
        raise ttlock.TTLockError("odd", code=UNMAPPED, kind="transient")

    monkeypatch.setattr(ttlock, "delete_code", refuse)
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKE_PENDING and after["next_attempt_at"] is not None
    assert lock.pins == {"pid-1": "4821937"} and lock.lookups == 1 and notices == []


def test_an_unmapped_refusal_and_a_failed_lookup_are_retried(world):
    lock, stay, row, notices = world
    lock.pins.clear()
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and notices == []


@pytest.mark.parametrize("code,kind", [(None, "network"), (-2012, "offline")])
def test_a_network_error_or_a_mapped_errcode_costs_no_lookup(world, monkeypatch, code, kind):
    lock, stay, row, notices = world

    def fail(*a, **k):
        raise ttlock.TTLockError("down", code=code, kind=kind)

    monkeypatch.setattr(ttlock, "delete_code", fail)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.lookups == 0
