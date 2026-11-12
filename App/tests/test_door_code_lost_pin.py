"""1149: a revoke that deleted the lock code but lost the row must not leave a dead PIN.

A fake lock holds the PINs. Each test makes a competing writer run inside the
delete call, after the lock has dropped the PIN, then checks the row against the lock.
"""
from __future__ import annotations

import itertools
from datetime import timedelta

import pytest

from app import config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state


class FakeLock:
    def __init__(self):
        self.pins = {"pid-1": "4821937"}
        self.made = 0
        self.fail_create = None
        self._seq = itertools.count(2)

    def delete(self, account_id, lock_id, code_id, priority=None):
        self.pins.pop(str(code_id), None)

    def create(self, *args, **kwargs):
        if self.fail_create:
            raise self.fail_create
        self.made += 1
        code_id = f"pid-{next(self._seq)}"
        self.pins[code_id] = "5550000"
        return "5550000", code_id


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = FakeLock()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "delete_code", lambda *a, **k: lock.delete(*a, **k))
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "add_custom_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "find_code_by_name", lambda *a, **k: None)
    # 1155 checks a revived row on the lock; these tests pin the 1149 zero-row path alone.
    monkeypatch.setattr(door_codes, "_lock_code_state", lambda *a, **k: door_codes.PIN_PRESENT)
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


def _revive(stay):
    db.execute("UPDATE reservation SET status = 'active' WHERE id = ?", (stay,))


def _expire_lease(row):
    old = door_codes._iso(door_codes._now() - timedelta(minutes=door_codes.LEASE_MINUTES + 1))
    db.execute("UPDATE door_code SET claimed_at = ? WHERE id = ?", (old, row))


def _revive_after_lease(monkeypatch, lock, stay, row, extra=None):
    """Delete runs on the lock, takes longer than the lease, the stay comes back."""
    def slow_delete(*a, **k):
        lock.delete(*a, **k)
        _revive(stay)
        _expire_lease(row)
        door_codes._handle_cancellations(db.utcnow())
        if extra:
            extra()

    monkeypatch.setattr(ttlock, "delete_code", slow_delete)


def _row(row):
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row,))


def test_lost_race_with_a_live_stay_gets_a_new_working_pin(world, monkeypatch):
    lock, stay, row, sent = world
    lost, again = _audits("door_code_revoke_lost_race"), _audits("door_code_pin_reissued")
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.ISSUED
    assert after["provider_code_id"] in lock.pins and after["provider_code_id"] != "pid-1"
    assert "pid-1" not in lock.pins and lock.made == 1
    assert db.decrypt_field(after["pin_enc"]) == "5550000"
    assert sent == [row]
    assert _audits("door_code_revoke_lost_race") == lost + 1
    assert _audits("door_code_pin_reissued") == again + 1


def test_a_date_move_that_won_is_left_alone(world, monkeypatch):
    lock, stay, row, sent = world

    def move():
        code_id = lock.create()[1]
        db.execute("UPDATE door_code SET provider_code_id = ? WHERE id = ?", (code_id, row))

    _revive_after_lease(monkeypatch, lock, stay, row, extra=move)
    again = _audits("door_code_pin_reissued")
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == "pid-2"
    assert list(lock.pins) == ["pid-2"] and lock.made == 1
    assert _audits("door_code_pin_reissued") == again


def test_a_stay_cancelled_again_is_not_reissued(world, monkeypatch):
    lock, stay, row, sent = world
    monkeypatch.setattr(
        ttlock,
        "delete_code",
        lambda *a, **k: (
            lock.delete(*a, **k),
            db.execute("UPDATE door_code SET state = ?, claimed_at = NULL WHERE id = ?", (door_codes.ISSUED, row)),
        ),
    )
    again = _audits("door_code_pin_reissued")
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.ISSUED
    assert lock.made == 0 and sent == []
    assert _audits("door_code_pin_reissued") == again


def test_a_second_revoke_that_won_needs_no_reissue(world, monkeypatch):
    lock, stay, row, sent = world
    calls = {"n": 0}

    def delete(*a, **k):
        lock.delete(*a, **k)
        calls["n"] += 1
        if calls["n"] == 1:
            _expire_lease(row)
            door_codes._revoke_one(row)

    monkeypatch.setattr(ttlock, "delete_code", delete)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKED
    assert lock.made == 0 and lock.pins == {}


def test_a_new_issue_cannot_touch_a_revoke_pending_row(world, monkeypatch):
    lock, stay, row, sent = world
    seen = {}

    def delete(*a, **k):
        lock.delete(*a, **k)
        seen["issue"] = door_codes.issue(row, allow_gateway=True)

    monkeypatch.setattr(ttlock, "delete_code", delete)
    door_codes._revoke_one(row)
    assert seen == {"issue": False}
    assert _state(row) == door_codes.REVOKED and lock.made == 0


def test_operator_pause_keeps_the_row_pending_until_the_plan_is_back(world, monkeypatch):
    lock, stay, row, sent = world
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: False)
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    held = _row(row)
    assert held["state"] == door_codes.PENDING and held["pin_enc"] is None
    assert lock.made == 0
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    door_codes._issue_due(db.utcnow())
    back = _row(row)
    assert back["state"] == door_codes.ISSUED and back["provider_code_id"] in lock.pins


def test_a_failed_reissue_alerts_the_host_once(world, monkeypatch):
    lock, stay, row, sent = world
    lock.fail_create = ttlock.TTLockError("busy", kind="transient")
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    assert _state(row) in (door_codes.RETRYING, door_codes.PENDING)
    assert lock.pins == {}
    db.execute("UPDATE reservation SET registration_completed_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", stay))
    door_codes._alert_delayed()
    door_codes._alert_delayed()
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE kind = 'door_code_delayed' AND reservation_id = ? AND resolved_at IS NULL",
        (stay,),
    )["n"]
    assert n == 1
    lock.fail_create = None
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
    door_codes._issue_due(db.utcnow())
    assert _state(row) == door_codes.ISSUED
