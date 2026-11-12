"""1155: a revived row whose delete may have run is checked on the lock before it is shown.

A fake lock holds the PINs. The delete is made to time out or crash after the lock
dropped the PIN, the stay comes back, and the row must not stay "issued" with a dead PIN.
"""
from __future__ import annotations

import pytest

from app import config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state
from tests.test_door_code_lost_pin import FakeLock, _expire_lease, _revive, _row


class Crash(BaseException):
    """A process death: nothing in door_codes catches it."""


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = FakeLock()
    lock.lookups = 0
    lock.lookup_error = None

    def listed(account_id, lock_id, name, code_id):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        return str(code_id) in lock.pins

    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "delete_code", lambda *a, **k: lock.delete(*a, **k))
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "add_custom_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "code_is_listed", listed)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_delayed_notice", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.push, "door_code_missing", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail, "drain", lambda **k: None)
    sent: list = []
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: sent.append(row_id))
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    db.execute("UPDATE door_code SET valid_from = ? WHERE id = ?", ("2098-12-30T00:00:00+00:00", row))
    yield lock, stay, row, sent
    _purge()


def _delete_then(monkeypatch, lock, error):
    def delete(*a, **k):
        lock.delete(*a, **k)
        raise error

    monkeypatch.setattr(ttlock, "delete_code", delete)


def _tick():
    door_codes._handle_cancellations(db.utcnow())


def _assert_new_working_pin(lock, row, sent):
    after = _row(row)
    assert after["state"] == door_codes.ISSUED
    assert after["provider_code_id"] in lock.pins and after["provider_code_id"] != "pid-1"
    assert "pid-1" not in lock.pins and lock.made == 1
    assert db.decrypt_field(after["pin_enc"]) == "5550000"
    assert sent == [row]


def test_a_delete_that_timed_out_after_the_lock_ran_it_gets_a_new_pin(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.pins == {}
    _revive(stay)
    again = _audits("door_code_pin_reissued")
    _tick()
    _assert_new_working_pin(lock, row, sent)
    assert _audits("door_code_pin_reissued") == again + 1
    assert lock.lookups == 1


def test_a_crash_after_the_delete_gets_a_new_pin_once_the_lease_ends(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, Crash())
    with pytest.raises(Crash):
        door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.pins == {}
    _revive(stay)
    _tick()
    assert _state(row) == door_codes.REVOKE_PENDING and lock.lookups == 0  # lease still fresh
    _expire_lease(row)
    _tick()
    _assert_new_working_pin(lock, row, sent)
    assert lock.lookups == 1


def test_a_delete_the_lock_refused_keeps_its_pin_and_costs_no_lookup(world, monkeypatch):
    lock, stay, row, sent = world

    def refuse(*a, **k):
        raise ttlock.TTLockError("no permission", code=-2018, kind="permission")

    monkeypatch.setattr(ttlock, "delete_code", refuse)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_FAILED
    _revive(stay)
    again = _audits("door_code_pin_reissued")
    _tick()
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == "pid-1"
    assert lock.pins == {"pid-1": "4821937"} and lock.made == 0 and sent == []
    assert _audits("door_code_pin_reissued") == again
    assert lock.lookups == 0


def test_a_row_without_a_delete_attempt_and_an_issued_row_cost_no_lookup(world):
    lock, stay, row, sent = world
    _revive(stay)
    _tick()
    assert _state(row) == door_codes.ISSUED
    _tick()
    _tick()
    assert lock.lookups == 0 and lock.made == 0 and sent == []


def test_a_revoke_that_finds_the_stay_live_checks_a_row_that_had_a_delete_attempt(world):
    lock, stay, row, sent = world
    lock.pins.clear()
    db.execute("UPDATE door_code SET attempts = 1 WHERE id = ?", (row,))
    _revive(stay)
    door_codes._revoke_one(row)
    _assert_new_working_pin(lock, row, sent)
    assert lock.lookups == 1


def test_a_failed_lookup_keeps_the_row_then_gives_up_after_three_tries(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    _tick()
    held = _row(row)
    assert held["state"] == door_codes.REVOKE_PENDING and held["last_error"] == "lookup_failed:1"
    assert held["attempts"] == 1 and lock.lookups == 1
    _tick()
    assert lock.lookups == 1  # the lease holds the next try back
    _expire_lease(row)
    _tick()
    assert _row(row)["last_error"] == "lookup_failed:2" and _row(row)["attempts"] == 1 and lock.lookups == 2
    unverified = _audits("door_code_pin_unverified")
    _expire_lease(row)
    _tick()
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == "pid-1"
    assert lock.lookups == 3 and lock.made == 0
    assert _audits("door_code_pin_unverified") == unverified + 1


def test_a_lookup_that_fails_once_and_then_works_still_re_issues(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    _tick()
    assert _state(row) == door_codes.REVOKE_PENDING
    lock.lookup_error = None
    _expire_lease(row)
    _tick()
    _assert_new_working_pin(lock, row, sent)
