"""The registration confirmation carries the door code (task 0025)."""
from __future__ import annotations

import json

import pytest

from app import claim, config, db, door_codes, mail, ttlock
# _env is the autouse fixture of that file; importing it here applies it here too.
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401

PIN = "4821937"


@pytest.fixture(autouse=True)
def _claims(_env, monkeypatch):
    monkeypatch.setattr(
        claim.reporting,
        "reservation_progress",
        lambda _r: {"expected": 1, "filled": 1, "incomplete": False, "status": "complete"},
    )
    yield
    db.execute(
        "DELETE FROM reservation_claim WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE uid LIKE 'dc-safe-%')"
    )


def _claim(stay):
    now = db.utcnow()
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, created_at, updated_at) "
        "VALUES (?, 'claimed', 'guest@example.test', 'en', ?, ?)",
        (stay, now, now),
    )


def _guest_registers(stay):
    """What the guest form does once everyone is in (the order from step 1)."""
    _claim(stay)
    door_codes.on_registration_complete(stay)
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
    claim.maybe_notify_completion(reservation, apartment)


def _guest_mails(stay):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind IN ('completion', 'door_code') "
        "ORDER BY id",
        (stay,),
    )


def _text(row):
    return mail.delivery_body(json.loads(row["payload"]))


def _works(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: (PIN, "99"))


def _refuses(monkeypatch, kind="transient"):
    def refused(*args, **kwargs):
        raise ttlock.TTLockError("refused", code=-1026, kind=kind)

    monkeypatch.setattr(ttlock, "create_period_code", refused)


def _due_now(stay):
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))


def test_a_code_made_at_once_rides_in_the_confirmation(monkeypatch):
    _works(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert PIN in _text(mails[0])
    assert "If you have not used it by" in _text(mails[0])
    row = db.query_one("SELECT notified_at FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["notified_at"]


def test_a_held_confirmation_goes_with_the_code_after_the_retry(monkeypatch):
    _refuses(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    assert _guest_mails(stay) == []
    _works(monkeypatch)
    _due_now(stay)
    door_codes.reconcile()
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert PIN in _text(mails[0])


def test_two_refusals_send_the_confirmation_without_a_code_and_tell_the_host(monkeypatch):
    _refuses(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    _due_now(stay)
    door_codes.reconcile()
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert "If you have not used it by" not in _text(mails[0])
    assert db.query(
        "SELECT id FROM email_outbox WHERE reservation_id = ? AND kind = 'door_code_notice'",
        (stay,),
    )


def test_a_property_without_a_lock_sends_the_confirmation_at_once():
    _, apartment, stay = _stay(registered_minutes_ago=0)
    db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id = ?", (apartment,))
    _guest_registers(stay)
    assert [m["kind"] for m in _guest_mails(stay)] == ["completion"]


def test_codes_switched_off_send_the_confirmation_at_once(monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    assert [m["kind"] for m in _guest_mails(stay)] == ["completion"]


def test_a_confirmation_never_waits_more_than_five_minutes(monkeypatch):
    lines = []
    monkeypatch.setattr(door_codes.log, "error", lambda msg, *args, **kw: lines.append(msg % args))
    _refuses(monkeypatch, kind="budget")  # budget: TTLock is asked again only in 60 min
    _, apartment, stay = _stay(registered_minutes_ago=6)
    _guest_registers(stay)
    assert _guest_mails(stay) == []
    door_codes.reconcile()
    mails = _guest_mails(stay)
    assert [m["kind"] for m in mails] == ["completion"]
    assert any(l.startswith("DOOR_CODE_PROBLEM stage=confirmation_without_code") for l in lines), lines


def test_an_old_stay_never_gets_a_late_confirmation(monkeypatch):
    _refuses(monkeypatch, kind="budget")
    _, apartment, stay = _stay(registered_minutes_ago=2 * 24 * 60)
    _claim(stay)
    door_codes.ensure_row(stay)
    door_codes.reconcile()
    assert _guest_mails(stay) == []


def test_a_code_made_after_the_confirmation_gets_its_own_mail(monkeypatch):
    _works(monkeypatch)
    _, apartment, stay = _stay(registered_minutes_ago=0)
    _guest_registers(stay)
    db.execute("UPDATE door_code SET notified_at = NULL WHERE reservation_id = ?", (stay,))
    row = db.query_one("SELECT id FROM door_code WHERE reservation_id = ?", (stay,))
    door_codes.send_code_mail(int(row["id"]))
    assert [m["kind"] for m in _guest_mails(stay)] == ["completion", "door_code"]
