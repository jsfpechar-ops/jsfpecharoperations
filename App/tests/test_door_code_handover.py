"""A code TTLock refuses twice is handed to the host at once (task 0024)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app import config, db, door_codes, mail, mail_notify, ttlock
# _env is the autouse fixture of that file; importing it here applies it here too.
from tests.test_door_codes_safeguards import _env, _stay, _view  # noqa: F401


def _refuse(monkeypatch, calls):
    def refused(*args, **kwargs):
        calls.append(1)
        raise ttlock.TTLockError("refused", code=-1026, kind="transient")

    monkeypatch.setattr(ttlock, "create_period_code", refused)


def _log_lines(monkeypatch):
    lines = []
    monkeypatch.setattr(door_codes.log, "error", lambda msg, *args, **kw: lines.append(msg % args))
    return lines


def _row(stay):
    return db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))


def _notices(stay):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND kind = 'door_code_notice'",
        (stay,),
    )


def _due_now(stay):
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))


def _parse(value):
    when = datetime.fromisoformat(value)
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def test_the_first_refusal_retries_in_a_minute_without_mail(monkeypatch):
    _refuse(monkeypatch, [])
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    row = _row(stay)
    assert row["state"] == door_codes.RETRYING
    wait = _parse(row["next_attempt_at"]) - datetime.now(timezone.utc)
    assert timedelta(0) < wait <= timedelta(minutes=1, seconds=5)
    assert _notices(stay) == []


def test_the_second_refusal_hands_over_to_host_and_support(monkeypatch):
    _refuse(monkeypatch, [])
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    _due_now(stay)
    door_codes.reconcile()
    assert _row(stay)["state"] == door_codes.FAILED
    notices = _notices(stay)
    assert len(notices) == 1
    assert notices[0]["to_email"] == "host@example.test"
    assert notices[0]["cc_email"] == "support@ubyhost.com"
    body = json.loads(notices[0]["payload"])["text"]
    assert "[transient:-1026]" in body
    assert "Passcodes" in body
    assert "will not try again" in body


def test_after_the_hand_over_ttlock_is_not_asked_again(monkeypatch):
    calls = []
    _refuse(monkeypatch, calls)
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    _due_now(stay)
    door_codes.reconcile()
    assert len(calls) == 2
    _due_now(stay)
    door_codes.reconcile()
    assert len(calls) == 2


def test_every_problem_is_one_greppable_log_line(monkeypatch):
    lines = _log_lines(monkeypatch)
    _refuse(monkeypatch, [])
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    assert any(l.startswith("DOOR_CODE_PROBLEM stage=attempt_failed") for l in lines), lines
    _due_now(stay)
    door_codes.reconcile()
    assert any(
        l.startswith("DOOR_CODE_PROBLEM stage=handed_over") and f"reservation={stay}" in l
        for l in lines
    ), lines


def test_the_guest_waiting_text_says_only_that_the_code_comes_by_e_mail():
    template = (
        Path(door_codes.__file__).parent / "templates" / "guest" / "stay.html"
    ).read_text(encoding="utf-8")
    assert "door_code_delayed" not in template
    assert "door_code_only_between" not in template
    assert mail_notify._guest_text("en", "door_code_preparing") == (
        "You will receive your door code by email."
    )


def test_an_issued_code_names_the_real_first_use_deadline(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    door_codes.reconcile()
    shown = _view(stay, apartment)
    start = _parse(_row(stay)["valid_from"])
    expected = (start + timedelta(hours=24)).astimezone(ZoneInfo(config.TIMEZONE)).strftime(
        "%d.%m.%Y %H:%M"
    )
    assert shown["first_use_by"] == expected
    content = mail_notify.build_door_code(
        lang="en",
        property_name="Flat",
        checkin=shown["checkin"],
        checkout=shown["checkout"],
        first_use_by=shown["first_use_by"],
    )
    assert f"If you have not used it by {expected}, it stops working." in content["text"]


def test_no_alert_and_no_mail_when_the_plan_has_no_door_codes(monkeypatch):
    _refuse(monkeypatch, [])
    _, apartment, stay = _stay(registered_minutes_ago=15)
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner_user_id: False)
    door_codes._alert_delayed()
    assert db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = ?", (f"door_code_delayed:{stay}",)
    ) is None
    assert _notices(stay) == []



def test_the_guest_door_code_mail_is_queued_with_the_deadline(monkeypatch):
    """The whole path: code made, guest has an address, the mail is queued (task 0028)."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "99"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    now = db.utcnow()
    db.execute(
        "INSERT INTO reservation_claim (reservation_id, state, email, lang, created_at, updated_at) "
        "VALUES (?, 'claimed', 'guest@example.test', 'en', ?, ?)",
        (stay, now, now),
    )
    try:
        door_codes.reconcile()
        row = db.query_one(
            "SELECT payload FROM email_outbox WHERE reservation_id = ? AND kind = 'door_code'",
            (stay,),
        )
        assert row is not None, "the guest door-code mail was not queued"
        text = mail.delivery_body(json.loads(row["payload"]))
        assert "4821937" in text
        assert "If you have not used it by" in text
    finally:
        db.execute("DELETE FROM reservation_claim WHERE reservation_id = ?", (stay,))
