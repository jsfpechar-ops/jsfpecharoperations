"""1163: TTLock's official error codes map to the kind that decides what we do.

A delete that answers -1007 (the passcode is not on the lock) is confirmed by a list call
before it counts as revoked. Offline and busy answers are retried without any lookup.
A refused passcode is replaced once by a new random PIN, never retried forever.
"""
from __future__ import annotations

import pytest

from app import cleaning_codes, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _state
from tests.test_door_code_recancel import world  # noqa: F401
from tests.test_door_code_lost_pin import _row
from tests.test_cleaning import workspace  # noqa: F401
from tests.test_cleaning_code_lookup_pages import _own, _queued, lock  # noqa: F401
from tests.test_cleaning_code_lookup_pages import _row as _clean_row
from tests.test_ttlock import _Resp

REAL_CODE_IS_LISTED = ttlock.code_is_listed

NEW_CODES = [
    (-1007, "code_missing"),
    (-3002, "offline"), (-3003, "offline"), (-3035, "offline"),
    (-3036, "offline"), (-3037, "offline"), (-2025, "offline"),
    (-1003, "config"), (-4037, "config"), (-4043, "config"), (-3034, "config"),
    (-4067, "config"), (-4063, "config"), (30008, "config"),
    (80002, "bug"), (-2009, "bug"), (-2032, "bug"), (-3006, "bug"), (-3045, "bug"),
]


@pytest.mark.parametrize("code,kind", NEW_CODES)
def test_every_new_errcode_maps_to_its_kind(code, kind):
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock._parse_response(_Resp({"errcode": code, "errmsg": "x"}))
    assert exc.value.kind == kind and exc.value.code == code


def _refuse(code):
    def fail(*a, **k):
        raise ttlock.TTLockError("x", code=code, kind=ttlock.ERROR_KINDS.get(code, "transient"))
    return fail


def test_minus_1007_on_delete_confirmed_gone_by_the_lock_is_revoked(world, monkeypatch):
    lock, stay, row, notices = world
    lock.pins.clear()
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-1007))
    revoked = _audits("door_code_revoked")
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKED and after["pin_enc"] is None
    assert _audits("door_code_revoked") == revoked + 1 and lock.lookups == 1
    detail = db.query_one(
        "SELECT detail FROM audit WHERE action = 'door_code_revoked' ORDER BY id DESC LIMIT 1"
    )["detail"]
    assert detail.endswith("via=gone:-1007") and notices == ["cancelled_deleted"]


def test_minus_1007_on_delete_while_the_lock_lists_the_code_is_not_revoked(world, monkeypatch):
    lock, stay, row, notices = world
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-1007))
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKE_PENDING and after["next_attempt_at"] is not None
    assert after["last_error"] == "code_missing" and after["pin_enc"] is not None
    assert lock.pins == {"pid-1": "4821937"} and lock.lookups == 1 and notices == []


def test_minus_1007_on_delete_and_a_failed_lookup_is_retried(world, monkeypatch):
    lock, stay, row, notices = world
    lock.pins.clear()
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-1007))
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and notices == []


def test_minus_1007_on_the_list_too_means_the_lock_has_no_codes(world, monkeypatch):
    lock, stay, row, notices = world
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-1007))
    monkeypatch.setattr(ttlock, "code_is_listed", REAL_CODE_IS_LISTED)
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: _refuse(-1007)())
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKED and notices == ["cancelled_deleted"]


def test_a_list_that_answers_minus_1007_after_a_full_page_is_not_an_empty_list(monkeypatch):
    pages = []

    def call(account_id, path, data, priority):
        pages.append(data["pageNo"])
        if data["pageNo"] == 1:
            return {"list": [{"keyboardPwdId": str(n), "keyboardPwdName": "UH-1"} for n in range(20)]}
        return _refuse(-1007)()

    monkeypatch.setattr(ttlock, "_call", call)
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock.code_is_listed(1, "9", "UH-1", "99")
    assert exc.value.code == -1007 and pages == [1, 2]


def test_codes_named_reads_minus_1007_on_page_one_as_no_codes(monkeypatch):
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: _refuse(-1007)())
    assert ttlock.codes_named(1, "9", "UH Cleaning abc") == []


@pytest.mark.parametrize("code", [-3002, -3003, -3035, -3036, -3037, -2025])
def test_an_offline_or_busy_answer_is_retried_with_no_lookup_and_never_revokes(world, monkeypatch, code):
    lock, stay, row, notices = world
    lock.pins.clear()  # a lookup would say "gone": it must not even be asked
    monkeypatch.setattr(ttlock, "delete_code", _refuse(code))
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKE_PENDING and after["next_attempt_at"] is not None
    assert after["last_error"] == "offline" and lock.lookups == 0 and notices == []


def _fake_add(monkeypatch, answers):
    """answers: an int is an errcode, a str is the new code id."""
    sent = []

    def call(account_id, path, data, priority):
        sent.append(data["keyboardPwd"])
        answer = answers[len(sent) - 1]
        if isinstance(answer, int):
            return _refuse(answer)()
        return {"keyboardPwdId": answer}

    monkeypatch.setattr(ttlock, "_call", call)
    return sent


def test_a_pin_the_lock_finds_too_simple_is_replaced_once(monkeypatch):
    pins = iter(["1234567", "7391846", "5555555"])
    monkeypatch.setattr(ttlock, "_random_custom_pin", lambda: next(pins))
    sent = _fake_add(monkeypatch, [-2032, "42"])
    pin, code_id = ttlock.add_custom_code(1, "9", 0, 3_600_000, "UH-1", ttlock.NORMAL)
    assert (pin, code_id, sent) == ("7391846", "42", ["1234567", "7391846"])


def test_a_second_refused_pin_is_raised_as_a_bug_and_not_retried_again(monkeypatch):
    pins = iter(["1234567", "7391846", "5555555"])
    monkeypatch.setattr(ttlock, "_random_custom_pin", lambda: next(pins))
    sent = _fake_add(monkeypatch, [-2032, -2032, "42"])
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock.add_custom_code(1, "9", 0, 3_600_000, "UH-1", ttlock.NORMAL)
    assert exc.value.kind == "bug" and exc.value.code == -2032 and len(sent) == 2


def test_a_format_errcode_other_than_too_simple_is_not_retried_with_a_new_pin(monkeypatch):
    monkeypatch.setattr(ttlock, "_random_custom_pin", lambda: "1234567")
    sent = _fake_add(monkeypatch, [-3006, "42"])
    with pytest.raises(ttlock.TTLockError) as exc:
        ttlock.add_custom_code(1, "9", 0, 3_600_000, "UH-1", ttlock.NORMAL)
    assert exc.value.kind == "bug" and len(sent) == 1


def _cleaning_delete_says_minus_1007(lock, monkeypatch, remove_first):
    """The lock's delete answers -1007; ``remove_first`` also drops the code (it was already gone)."""
    def call(account_id, path, data, priority):
        if path == "/v3/keyboardPwd/delete":
            if remove_first:
                lock.codes = [c for c in lock.codes if str(c["keyboardPwdId"]) != str(data["keyboardPwdId"])]
            return _refuse(-1007)()
        return lock.call(account_id, path, data, priority)

    monkeypatch.setattr(ttlock, "_call", call)


def test_a_cleaning_delete_answering_minus_1007_while_the_lock_lists_the_code_is_retried(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    _own(lock, row)
    _cleaning_delete_says_minus_1007(lock, monkeypatch, remove_first=False)
    cleaning_codes.process_queue()
    after = _clean_row(job)
    assert after["state"] == "revoke_pending" and after["last_error"] == "code_missing"
    assert after["pin_enc"] is not None and [c["keyboardPwdId"] for c in lock.codes] == ["7001"]


def test_a_cleaning_delete_answering_minus_1007_for_a_code_the_list_confirms_gone_is_revoked(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    _own(lock, row)
    _cleaning_delete_says_minus_1007(lock, monkeypatch, remove_first=True)
    cleaning_codes.process_queue()
    after = _clean_row(job)
    assert after["state"] == "revoked" and after["pin_enc"] is None


def test_a_cleaning_delete_answering_minus_1007_with_an_incomplete_list_is_retried(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    _own(lock, row)
    def call(account_id, path, data, priority):
        if path == "/v3/keyboardPwd/delete":
            return _refuse(-1007)()
        return {"pages": 1}  # a list answer without a list: unknown

    monkeypatch.setattr(ttlock, "_call", call)
    cleaning_codes.process_queue()
    assert _clean_row(job)["state"] == "revoke_pending"
