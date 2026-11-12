"""1165: lock-side setup errcodes (kind lock_setup) are retried slowly, account-level ones (config) are not.

-3034 network not configured, -4037 no gateway, -4043 not supported, -1003 lock does not exist and
-4067 NB device not registered can be fixed at the lock later; before 1163 they were retried as
transient, and 1165 restores that. -4063 and 30008 stay config: the host or operator must act.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import alerts, db, deadlines, door_codes, ttlock
from app.door_codes import check_lock_clocks as real_check_lock_clocks
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401

LOCK_SETUP_CODES = [-3034, -4037, -4043, -1003, -4067]


def _refuse(code):
    def fail(*a, **k):
        raise ttlock.TTLockError("x", code=code, kind=ttlock.ERROR_KINDS.get(code, "transient"))
    return fail


def _failed_mail(stay):
    return db.query_one(
        "SELECT 1 AS ok FROM email_outbox WHERE reservation_id = ? AND idempotency_key LIKE '%:failed'",
        (stay,),
    )


def _issue_row(stay):
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = NULL WHERE id = ?",
        (door_codes.PENDING, row_id),
    )
    return row_id


@pytest.mark.parametrize("code", LOCK_SETUP_CODES)
def test_a_lock_setup_answer_on_issue_is_retried_before_it_is_handed_over(monkeypatch, code):
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(code))
    monkeypatch.setattr(ttlock, "add_custom_code", _refuse(code))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    row_id = _issue_row(stay)
    door_codes.reconcile()
    first = db.query_one("SELECT state, last_error FROM door_code WHERE id = ?", (row_id,))
    assert first["state"] == door_codes.RETRYING and first["last_error"] == f"lock_setup:{code}"
    assert _failed_mail(stay) is None
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row_id,))
    door_codes.reconcile()
    second = db.query_one("SELECT state FROM door_code WHERE id = ?", (row_id,))
    assert second["state"] == door_codes.FAILED and _failed_mail(stay) is not None


def test_a_config_answer_on_issue_is_still_handed_over_at_once(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(-4063))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    row_id = _issue_row(stay)
    door_codes.reconcile()
    row = db.query_one("SELECT state, last_error FROM door_code WHERE id = ?", (row_id,))
    assert row["state"] == door_codes.FAILED and row["last_error"] == "config:-4063"
    assert _failed_mail(stay) is not None


def _moved_stay(monkeypatch):
    """An issued code, then the stay moves 2 days later: the next reconcile wants a move replace."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("1111111", "c1"))
    monkeypatch.setattr(ttlock, "delete_code", lambda *a, **k: None)
    _, apartment, stay = _stay(registered_minutes_ago=1)
    today = deadlines.local_now().date()
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today + timedelta(days=5)).isoformat(), (today + timedelta(days=7)).isoformat(), stay),
    )
    door_codes.reconcile()
    res = db.query_one("SELECT date_to FROM reservation WHERE id = ?", (stay,))
    old_to = res["date_to"]
    new_to = (datetime.fromisoformat(old_to).date() + timedelta(days=2)).isoformat()
    db.execute("UPDATE reservation SET date_to = ? WHERE id = ?", (new_to, stay))
    return stay, old_to


def _code_row(stay):
    return db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))


@pytest.mark.parametrize("code", LOCK_SETUP_CODES)
def test_a_lock_setup_answer_on_a_move_retries_in_an_hour_and_a_later_success_clears_it(monkeypatch, code):
    stay, _ = _moved_stay(monkeypatch)
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(code))
    door_codes.reconcile()
    failed = _code_row(stay)
    assert failed["last_error"] == f"lock_setup:{code}" and failed["provider_code_id"] == "c1"
    wait = datetime.fromisoformat(failed["next_attempt_at"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=55) < wait <= timedelta(minutes=60)
    assert _failed_mail(stay) is None
    calls = []
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: calls.append(1) or ("2222222", "c2"))
    door_codes.reconcile()
    assert calls == []  # the hour is not over
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()
    fixed = _code_row(stay)
    assert fixed["provider_code_id"] == "c2" and fixed["last_error"] is None


def test_a_config_answer_on_a_move_is_mailed_once_and_not_retried(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(-4063))
    door_codes.reconcile()
    assert _code_row(stay)["last_error"] == "config:-4063" and _failed_mail(stay) is not None
    calls = []
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: calls.append(1) or ("2", "c2"))
    door_codes.reconcile()
    assert calls == []


@pytest.mark.parametrize("error", ["lock_setup:-3034", "config:-4063"])
def test_a_stay_moved_back_to_the_codes_own_window_clears_an_old_move_failure(monkeypatch, error):
    stay, old_to = _moved_stay(monkeypatch)
    db.execute("UPDATE door_code SET last_error = ?, next_attempt_at = NULL WHERE reservation_id = ?", (error, stay))
    db.execute("UPDATE reservation SET date_to = ? WHERE id = ?", (old_to, stay))
    door_codes.reconcile()
    row = _code_row(stay)
    assert row["last_error"] is None and row["provider_code_id"] == "c1"


def _clock_world(monkeypatch):
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    _, apartment, stay = _stay(registered_minutes_ago=1)
    key = "ttlock_clock_checked:35662508"
    db.set_setting(key, "2000-01-01T00:00:00+00:00")
    return apartment, key


def test_a_lock_that_does_not_support_the_clock_call_raises_the_alert_and_waits_a_week(monkeypatch):
    apartment, key = _clock_world(monkeypatch)
    monkeypatch.setattr(ttlock, "query_lock_time", _refuse(-4043))
    raised = []
    monkeypatch.setattr(alerts, "raise_alert", lambda *a, **k: raised.append(k["dedupe_key"]))
    real_check_lock_clocks()
    assert raised == ["door_code_clock:35662508"]
    stamp = datetime.fromisoformat(db.get_setting(key))
    assert datetime.now(stamp.tzinfo) - stamp < timedelta(days=1)


def test_a_busy_lock_on_the_clock_call_is_retried_in_a_day_without_an_alert(monkeypatch):
    apartment, key = _clock_world(monkeypatch)
    monkeypatch.setattr(ttlock, "query_lock_time", _refuse(-3037))
    raised = []
    monkeypatch.setattr(alerts, "raise_alert", lambda *a, **k: raised.append(k["dedupe_key"]))
    real_check_lock_clocks()
    assert raised == []
    stamp = datetime.fromisoformat(db.get_setting(key))
    assert datetime.now(stamp.tzinfo) - stamp > timedelta(days=5)



def test_host_mails_say_what_to_do_for_the_new_kinds():
    from app import mail_notify

    def reason(lang, text):
        return mail_notify._door_code_reason(lang, text)

    assert "gateway" in reason("en", "lock_setup:-3034") and "TTLock app" in reason("en", "lock_setup:-3034")
    assert reason("en", "lock_setup:-3034").startswith("the lock is not fully set up in TTLock")
    assert reason("en", "lock_setup:-3034").endswith("[lock_setup:-3034]")
    assert reason("en", "config:-4063").startswith("this is a setting on the UbyHost side")
    assert reason("en", "bug:-3006").startswith("TTLock's cloud refused")
    assert reason("en", "code_missing").startswith("TTLock's cloud refused")
    assert reason("en", "period_taken:lock_setup:-4037").startswith("the lock is not fully set up in TTLock")
    for lang in ("cs", "vi"):
        assert reason(lang, "lock_setup:-3034") != reason("en", "lock_setup:-3034")
        assert reason(lang, "config:-4063") != reason(lang, "reauth")
