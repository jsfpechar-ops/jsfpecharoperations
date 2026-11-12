"""1162: a cleaning code is called absent only when the lock's whole answer says so.

A fake lock answers /v3/lock/listKeyboardPwd like TTLock: a fuzzy searchStr, 20 codes a
page. The row's own code can sit on page 2 when other names contain its operation name.
"""
from __future__ import annotations

import pytest

from app import cleaning_codes, db, ttlock
from tests.test_cleaning import lock_setup, workspace  # noqa: F401


class CleaningLock:
    def __init__(self):
        self.codes: list[dict] = []
        self.list_calls = 0
        self.added = 0
        self.deleted: list[str] = []
        self.answer = None  # when set, every list call returns this instead

    def add(self, code_id, name, pin="1234567"):
        self.codes.append({"keyboardPwdId": code_id, "keyboardPwdName": name,
                           "keyboardPwd": pin, "keyboardPwdType": 2})

    def crowd(self, name, count):
        for number in range(count):
            self.add(str(500 + number), f"{name}{number}", pin="1111111")

    def call(self, account_id, path, data, priority):
        if path == "/v3/lock/listKeyboardPwd":
            self.list_calls += 1
            if self.answer is not None:
                return dict(self.answer)
            hits = [c for c in self.codes if data["searchStr"] in c["keyboardPwdName"]]
            size, page = data["pageSize"], data["pageNo"]
            return {"list": hits[(page - 1) * size: page * size], "pageNo": page,
                    "pageSize": size, "pages": max(1, -(-len(hits) // size)), "total": len(hits)}
        if path == "/v3/keyboardPwd/add":
            self.added += 1
            self.add("9100", data["keyboardPwdName"], pin=data["keyboardPwd"])
            return {"keyboardPwdId": "9100"}
        if path == "/v3/keyboardPwd/delete":
            self.deleted.append(str(data["keyboardPwdId"]))
            self.codes = [c for c in self.codes if str(c["keyboardPwdId"]) != str(data["keyboardPwdId"])]
            return {}
        raise AssertionError(path)


@pytest.fixture
def lock(monkeypatch):
    fake = CleaningLock()
    monkeypatch.setattr(ttlock, "_call", fake.call)
    return fake


def _queued(ws, monkeypatch, state, attempts):
    """A ttlock cleaning row that already tried `attempts` times, so process_queue reconciles first."""
    _, home = lock_setup(ws, monkeypatch)
    job = cleaning_codes.queue_permanent(home, ws["owner"])
    db.update("cleaning_code", job, {"state": state, "attempts": attempts,
                                     "next_attempt_at": "2000-01-01T00:00:00+00:00"})
    return job, dict(db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,)))


def _row(job):
    return dict(db.query_one("SELECT * FROM cleaning_code WHERE id = ?", (job,)))


def _own(lock, row):
    lock.add("7001", row["operation_ref"], pin=db.decrypt_field(row["pin_enc"]))


def test_issuing_adopts_a_code_on_page_two_without_a_second_add(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "retrying", 1)
    lock.crowd(row["operation_ref"], 25)
    _own(lock, row)
    assert cleaning_codes.process_queue() == 1
    after = _row(job)
    assert after["state"] == "active" and after["provider_code_id"] == "7001"
    assert lock.added == 0 and lock.list_calls == 2


def test_revoking_deletes_a_code_on_page_two(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    lock.crowd(row["operation_ref"], 25)
    _own(lock, row)
    assert cleaning_codes.process_queue() == 1
    assert _row(job)["state"] == "revoked" and lock.deleted == ["7001"]


def test_a_code_absent_from_every_page_is_added_when_issuing(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "retrying", 1)
    lock.crowd(row["operation_ref"], 25)
    assert cleaning_codes.process_queue() == 1
    assert _row(job)["state"] == "active" and lock.added == 1 and lock.list_calls == 2


def test_a_code_absent_from_every_page_is_revoked_as_gone(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    lock.crowd(row["operation_ref"], 25)
    assert cleaning_codes.process_queue() == 1
    assert _row(job)["state"] == "revoked" and lock.deleted == [] and lock.list_calls == 2


def test_a_list_longer_than_the_page_limit_is_unknown_for_issuing(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "retrying", 1)
    lock.crowd(row["operation_ref"], ttlock.LIST_MAX_PAGES * ttlock.LIST_PAGE_SIZE + 5)
    _own(lock, row)
    cleaning_codes.process_queue()
    after = _row(job)
    assert after["state"] == "retrying" and after["last_error"] == "transient"
    assert lock.added == 0 and lock.list_calls == ttlock.LIST_MAX_PAGES


def test_a_list_longer_than_the_page_limit_is_unknown_for_revoking(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    lock.crowd(row["operation_ref"], ttlock.LIST_MAX_PAGES * ttlock.LIST_PAGE_SIZE + 5)
    _own(lock, row)
    cleaning_codes.process_queue()
    after = _row(job)
    assert after["state"] == "revoke_pending" and after["pin_enc"] and lock.deleted == []


NO_LIST = [{}, {"pages": 1}, {"list": None, "pages": 0}, {"list": "oops"}, {"list": {"a": 1}}]


@pytest.mark.parametrize("answer", NO_LIST)
def test_an_answer_without_a_list_never_adds_a_second_code(workspace, lock, monkeypatch, answer):
    job, row = _queued(workspace, monkeypatch, "retrying", 1)
    lock.answer = answer
    cleaning_codes.process_queue()
    after = _row(job)
    assert after["state"] == "retrying" and after["last_error"] == "transient" and lock.added == 0


@pytest.mark.parametrize("answer", NO_LIST)
def test_an_answer_without_a_list_never_marks_a_code_revoked(workspace, lock, monkeypatch, answer):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    lock.answer = answer
    cleaning_codes.process_queue()
    after = _row(job)
    assert after["state"] == "revoke_pending" and after["pin_enc"] and lock.deleted == []


def test_the_retries_are_bounded_and_end_in_a_failed_state(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 5)
    lock.answer = {}
    cleaning_codes.process_queue()
    assert _row(job)["state"] == "revoke_failed" and lock.deleted == []


def test_two_codes_with_the_operation_name_are_still_ambiguous(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "retrying", 1)
    lock.add("7001", row["operation_ref"], pin=db.decrypt_field(row["pin_enc"]))
    lock.add("7002", row["operation_ref"], pin=db.decrypt_field(row["pin_enc"]))
    cleaning_codes.process_queue()
    assert _row(job)["state"] == "failed" and lock.added == 0


def test_codes_named_keeps_only_exact_names(lock):
    lock.crowd("UH Cleaning abc", 3)
    lock.add("7001", "UH Cleaning abc")
    found = ttlock.codes_named(1, "123", "UH Cleaning abc")
    assert [c["keyboardPwdId"] for c in found] == ["7001"]
