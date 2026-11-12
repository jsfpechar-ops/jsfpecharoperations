"""1157: a door code is called gone only when the lock's whole answer says so.

A fake lock answers /v3/lock/listKeyboardPwd like TTLock: a fuzzy searchStr, 20 codes a
page, with pages and total. UH-<id> also matches UH-<id>0 and UH-<id>1, so on a busy lock
the row's own code can sit on page 2.
"""
from __future__ import annotations

import itertools

import pytest

from app import config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state
from tests.test_door_code_lost_pin import _expire_lease, _revive, _row

UNMAPPED = -3999
CODE = "9001"  # the row's own code id; the lock's ids are numbers, as TTLock's are


class Crash(BaseException):
    """A process death: nothing in door_codes catches it."""


class ListLock:
    """The lock's code list and the three TTLock paths door_codes uses."""

    def __init__(self):
        self.codes: list[dict] = []
        self.list_calls = 0
        self.list_error = None
        self.after_delete = None
        self.made = 0
        self._seq = itertools.count(100)
        self._decoys = itertools.count(500)

    def add(self, code_id, name, pin="4821937"):
        self.codes.append({"keyboardPwdId": code_id, "keyboardPwdName": name, "keyboardPwd": pin})

    def crowd(self, name, count):
        """count other codes whose names contain `name` (UH-7 also matches UH-70, UH-71, ...)."""
        for number in range(count):
            self.add(str(next(self._decoys)), f"{name}{number}", pin="1111111")

    def call(self, account_id, path, data, priority):
        if path == "/v3/lock/listKeyboardPwd":
            self.list_calls += 1
            if self.list_error:
                raise self.list_error
            hits = [c for c in self.codes if data["searchStr"] in c["keyboardPwdName"]]
            size, page = data["pageSize"], data["pageNo"]
            return {
                "list": hits[(page - 1) * size : page * size],
                "pageNo": page,
                "pageSize": size,
                "pages": max(1, -(-len(hits) // size)),
                "total": len(hits),
            }
        if path == "/v3/keyboardPwd/delete":
            present = [c for c in self.codes if str(c["keyboardPwdId"]) == str(data["keyboardPwdId"])]
            if not present:
                raise ttlock.TTLockError("no such passcode", code=UNMAPPED, kind="transient")
            self.codes.remove(present[0])
            if self.after_delete:
                raise self.after_delete
            return {}
        if path == "/v3/keyboardPwd/get":
            self.made += 1
            code_id = str(next(self._seq))
            self.add(code_id, data["keyboardPwdName"], pin="5550000")
            return {"keyboardPwd": "5550000", "keyboardPwdId": code_id}
        raise AssertionError(path)


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = ListLock()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "_call", lock.call)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_delayed_notice", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.push, "door_code_missing", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail, "drain", lambda **k: None)
    sent: list = []
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: sent.append(row_id))
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    db.execute(
        "UPDATE door_code SET valid_from = ?, provider_code_id = ? WHERE id = ?",
        ("2098-12-30T00:00:00+00:00", CODE, row),
    )
    yield lock, stay, row, sent
    _purge()


def _busy(lock, row, others=30):
    """Others first, then the row's own code: on a 20-a-page list it is on page 2."""
    lock.crowd(f"UH-{row}", others)
    lock.add(CODE, f"UH-{row}")


def _fresh_row(row):
    return door_codes._lock_code_state(_row(row), _owner(row))


def _owner(row):
    return db.query_one(
        "SELECT a.owner_user_id FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id WHERE dc.id = ?",
        (row,),
    )["owner_user_id"]


def test_a_code_on_page_two_is_present(world):
    lock, stay, row, sent = world
    _busy(lock, row)
    assert _fresh_row(row) == door_codes.PIN_PRESENT
    assert lock.list_calls == 2


def test_a_code_missing_from_every_page_is_gone(world):
    lock, stay, row, sent = world
    lock.crowd(f"UH-{row}", 30)
    assert _fresh_row(row) == door_codes.PIN_GONE
    assert lock.list_calls == 2


def test_a_list_longer_than_the_page_limit_is_unknown_not_gone(world):
    lock, stay, row, sent = world
    lock.crowd(f"UH-{row}", ttlock.LIST_MAX_PAGES * ttlock.LIST_PAGE_SIZE + 5)
    lock.add(CODE, f"UH-{row}")
    assert _fresh_row(row) == door_codes.PIN_UNKNOWN
    assert lock.list_calls == ttlock.LIST_MAX_PAGES


def test_an_answer_without_a_pages_field_reads_on_while_the_page_is_full(world, monkeypatch):
    lock, stay, row, sent = world
    _busy(lock, row)
    real = lock.call

    def no_pages(account_id, path, data, priority):
        answer = real(account_id, path, data, priority)
        answer.pop("pages", None)
        return answer

    monkeypatch.setattr(ttlock, "_call", no_pages)
    assert _fresh_row(row) == door_codes.PIN_PRESENT
    lock.codes.clear()
    lock.crowd(f"UH-{row}", 20)  # exactly one full page, no pages field: ask for page 2
    assert _fresh_row(row) == door_codes.PIN_GONE


def test_a_cancelled_stay_whose_code_is_on_page_two_is_not_marked_revoked(world, monkeypatch):
    lock, stay, row, sent = world
    _busy(lock, row)
    real_call = lock.call

    def refuse_delete(account_id, path, data, priority):
        if path == "/v3/keyboardPwd/delete":
            raise ttlock.TTLockError("odd", code=UNMAPPED, kind="transient")
        return real_call(account_id, path, data, priority)

    monkeypatch.setattr(ttlock, "_call", refuse_delete)
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKE_PENDING and after["next_attempt_at"] is not None
    assert _audits("door_code_revoked") == 0


def test_a_revived_row_whose_code_is_on_page_two_keeps_its_pin_and_makes_no_second_code(world, monkeypatch):
    lock, stay, row, sent = world
    _busy(lock, row)
    db.execute("UPDATE door_code SET attempts = 1, last_error = ? WHERE id = ?", ("network", row))
    _expire_lease(row)
    _revive(stay)
    door_codes._handle_cancellations(db.utcnow())
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == CODE
    assert lock.made == 0


def test_an_incomplete_list_keeps_a_cancelled_row_pending(world, monkeypatch):
    lock, stay, row, sent = world
    lock.crowd(f"UH-{row}", ttlock.LIST_MAX_PAGES * ttlock.LIST_PAGE_SIZE + 5)
    lock.add(CODE, f"UH-{row}")
    real_call = lock.call

    def refuse_delete(account_id, path, data, priority):
        if path == "/v3/keyboardPwd/delete":
            raise ttlock.TTLockError("odd", code=UNMAPPED, kind="transient")
        return real_call(account_id, path, data, priority)

    monkeypatch.setattr(ttlock, "_call", refuse_delete)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and _audits("door_code_revoked") == 0


def test_lookups_through_the_claim_give_up_after_exactly_three(world):
    lock, stay, row, sent = world
    lock.list_error = ttlock.TTLockError("busy", kind="transient")
    db.execute("UPDATE door_code SET attempts = 1, last_error = ? WHERE id = ?", ("network", row))
    _revive(stay)  # the stay is live when _revoke_one claims the row
    for expected in (1, 2):
        _expire_lease(row)
        door_codes._revoke_one(row)
        held = _row(row)
        assert held["state"] == door_codes.REVOKE_PENDING and held["attempts"] == 1
        assert held["last_error"] == f"lookup_failed:{expected}" and lock.list_calls == expected
    unverified = _audits("door_code_pin_unverified")
    _expire_lease(row)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.ISSUED and lock.list_calls == 3
    assert _audits("door_code_pin_unverified") == unverified + 1


def test_a_stale_error_on_an_issued_row_does_not_hide_a_lost_pin(world):
    lock, stay, row, sent = world
    lock.add(CODE, f"UH-{row}")
    db.execute(
        "UPDATE door_code SET state = ?, last_error = ? WHERE id = ?",
        (door_codes.ISSUED, "transient:-3", row),
    )
    lock.after_delete = Crash()  # the lock drops the code, then the process dies
    with pytest.raises(Crash):
        door_codes._handle_cancellations(db.utcnow())  # issued -> revoke_pending -> delete
    assert lock.codes == [] and _row(row)["last_error"] is None
    _revive(stay)
    _expire_lease(row)
    door_codes._handle_cancellations(db.utcnow())
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] != CODE
    assert lock.made == 1


def test_a_code_with_the_same_name_but_another_id_is_gone(world):
    lock, stay, row, sent = world
    lock.add("7777", f"UH-{row}")  # same name as the row's code, not its id
    assert _fresh_row(row) == door_codes.PIN_GONE
    lock.add(CODE, f"UH-{row}")
    assert _fresh_row(row) == door_codes.PIN_PRESENT


NO_LIST = [{}, {"list": None, "pages": 0}, {"pages": 1}, {"list": "oops", "pages": 1}, {"list": {"a": 1}}]


@pytest.mark.parametrize("answer", NO_LIST)
def test_an_answer_without_a_list_is_unknown_and_never_revokes(world, monkeypatch, answer):
    lock, stay, row, sent = world
    real_call = lock.call

    def broken(account_id, path, data, priority):
        if path == "/v3/lock/listKeyboardPwd":
            lock.list_calls += 1
            return dict(answer)
        if path == "/v3/keyboardPwd/delete":
            raise ttlock.TTLockError("odd", code=UNMAPPED, kind="transient")
        return real_call(account_id, path, data, priority)

    monkeypatch.setattr(ttlock, "_call", broken)
    assert ttlock.code_is_listed(1, "1", f"UH-{row}", CODE) is None
    assert _fresh_row(row) == door_codes.PIN_UNKNOWN
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and _audits("door_code_revoked") == 0


def test_an_empty_list_is_the_end_even_when_pages_is_not_a_number(world, monkeypatch):
    lock, stay, row, sent = world
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: {"list": [], "pages": "x"})
    assert ttlock.code_is_listed(1, "1", f"UH-{row}", CODE) is False


def test_a_full_page_is_read_past_even_when_pages_says_one(world, monkeypatch):
    lock, stay, row, sent = world
    _busy(lock, row)
    real = lock.call

    def pages_one(account_id, path, data, priority):
        answer = real(account_id, path, data, priority)
        answer["pages"] = 1
        return answer

    monkeypatch.setattr(ttlock, "_call", pages_one)
    assert _fresh_row(row) == door_codes.PIN_PRESENT
    assert lock.list_calls == 2
