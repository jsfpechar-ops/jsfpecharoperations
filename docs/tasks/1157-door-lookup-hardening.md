# 1157: a door code is called gone only when the lock's whole answer says so

Status: review
Depends on: 1155, 1155b (merged) | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 (bccafce4 or later) | Branch: task/1157-door-lookup-hardening
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`_lock_code_state` asks the lock for the row's PIN with `ttlock.find_code_by_name`, which reads only page 1 (20 codes) of a fuzzy `searchStr` and needs name, start and end to match; a miss counts as `PIN_GONE`. On a busy lock UH-7 also matches UH-70 and UH-71, so the row's own code can sit on page 2: 1155b then marks a cancelled stay `revoked` while the PIN still opens the door, and 1155 orphans a code. Fix: a new `ttlock.code_is_listed` reads the list page by page (at most 5 calls) and matches on the code id; `PIN_GONE` only when the whole list was read and the id is not in it, otherwise `PIN_UNKNOWN` (today's safe path). Two smaller faults in the same code: a stale `last_error` on an issued row hides a lost PIN from the lookup, and a lookup that goes through `_revoke_one`'s claim is counted twice, so it gives up after 2 lookups instead of 3.

## 2. Context

Rules: SQL only through `db` helpers; no dependency, no migration (the lookup count lives in `last_error`, a text column), no new state transition. Anchors are verbatim from HEAD after 1155, 1155b and 1156; the script in step 2 asserts each anchor exists exactly once and stops with an `AssertionError` if not (then STOP, §8).

**Why the old lookup was wrong.** `ttlock.find_code_by_name` (kept as is, `issue()` retries still use it: an adopt-by-name miss there only makes `issue()` ask TTLock for the same period code again) sends `searchStr`, `pageNo 1`, `pageSize 20`, then needs `keyboardPwdName`, `startDate` and `endDate` to match. `_lock_code_state` (door_codes.py) turns "not found on page 1" into `PIN_GONE`; `_revoke_one` (via `_already_gone`, 1155b) treats `PIN_GONE` as a successful delete and `_revive_one` (1155) treats it as a lost PIN and issues a new code.

**The response shape.** `/v3/lock/listKeyboardPwd` answers `{"list": [...], "pageNo", "pageSize", "pages", "total"}` (`App/tests/test_ttlock.py` `test_find_code_by_name_requires_matching_window` queues `{"list": [...], "pages": 1}`). Each entry has `keyboardPwdId`. The new helper reads `pages`; if `pages` is missing it reads on while a page is full (20) and stops at the first short page. `LIST_MAX_PAGES = 5` bounds the cost (100 codes); a list that is longer, or still full after 5 pages, answers `None`, which `_lock_code_state` turns into `PIN_UNKNOWN`.

**Decision (match key).** The row's `provider_code_id` decides, not the name or the window: a code with the same name but another id is not this row's PIN. `_lock_code_state` no longer needs `valid_from` / `valid_to`; it still returns `PIN_UNKNOWN` without an account or without a `provider_code_id`. Unknown keeps today's safe path: `_revoke_one` retries (1, 15, 60 minutes), `_revive_one` keeps the row `revoke_pending` and gives up after 3 lookups with the `door_code_pin_unverified` audit. Never `revoked` on unknown.

**Item 3: stale `last_error`.** The `issued -> revoke_pending` UPDATE in `_handle_cancellations` resets `attempts` but not `last_error`. `_revive_one` decides that a delete may have run with `attempts` and `last_error in AMBIGUOUS_DELETE_ERRORS`, so a stale `transient:-3` (an old `issue()` failure text) on an issued row made the lookup skip after a crash. The UPDATE now also sets `last_error = NULL`. Nothing reads `last_error` of an issued row for another purpose: `issue()` sets it to NULL on success and `_keep_issued` sets it to NULL too.

**Item 4: lookup count.** `_note_failed_lookup` used `attempts` as the lookup counter. Through `_revoke_one` the claim adds 1 to `attempts` and the note added 1 more, so the third try came on the second lookup, and `attempts` could reach 2 and make the `attempts == 3` `cancelled_not_deleted` mail fire early if the stay was cancelled again. Now `attempts` is only the delete counter: the lookup count is stored in `last_error` as `lookup_failed:<n>`, `_note_failed_lookup(row_id, claim, claimed)` takes back the claim's own +1 when `claimed` is true (the call came through `_revoke_one`) and never adds one itself. The new helper `_delete_result_unknown` reads `last_error` (`""`, `network`, `transient` or any `lookup_failed...`). Giving up after `LOOKUP_MAX_TRIES = 3` is unchanged in the revive loop and now exact through the claim.

**Outbound request (for the PR, rule 2).** `_lock_code_state` used 1 `POST /v3/lock/listKeyboardPwd`; it now uses 1 to 5 (one per page of 20 codes, stopping at the page that holds the code, at the last page, or at the limit of 5). Same endpoint (already in `ttlock.ALLOWED_PATHS`), same host, same payload plus `pageNo`; only for a revived row whose delete may have run, or an unmapped delete refusal; at most 3 lookups per row. Reason: concluding that a PIN is gone from a partial list leaves a working PIN on the door or a second code on the lock. No new personal data. Not changed here (note for the orchestrator): `cleaning_codes._find` has the same page-1 limit with an exact operation name.

Anchors (all in the script of step 2): `door_codes.py` the two functions `_lock_code_state` and `_note_failed_lookup`, the line `        and (item["last_error"] or "") in AMBIGUOUS_DELETE_ERRORS`, the line `        if _note_failed_lookup(row_id, claim) < LOOKUP_MAX_TRIES:`, the `issued -> revoke_pending` UPDATE in `_handle_cancellations`; `ttlock.py` the line pair `def change_code_period(` / `    account_id: int,`; the two 1155 / 1155b test fixtures.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/ttlock.py | edit | `LIST_PAGE_SIZE`, `LIST_MAX_PAGES`, `code_is_listed` |
| App/app/door_codes.py | edit | `_lock_code_state`, `_delete_result_unknown`, `_note_failed_lookup`, 3 one-line changes |
| App/tests/test_door_code_ambiguous_delete.py | edit | fixture patches `code_is_listed`; 2 assertions |
| App/tests/test_door_code_recancel.py | edit | fixture patches `code_is_listed` |
| App/tests/test_door_code_lookup_pages.py | create | 9 tests |
| docs/tasks/1157-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1156 is in: `grep -c "def _tell_host_reissued" App/app/door_codes.py | tail -30` -> `1` (else STOP). Then `git switch -c task/1157-door-lookup-hardening | tail -30`; expected `Switched to a new branch`.

**Step 2. Apply the code and fixture changes.** From the repo root run this script (every `swap` asserts its old text exists exactly once):
```bash
python3 - <<'EOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:60])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

swap("App/app/door_codes.py", '''# a timeout or non-JSON answer (network), a server fault (transient), or a lookup that failed.
''', '''# a timeout or non-JSON answer (network), a server fault (transient), or a lookup that failed
# (stored as lookup_failed:<n>; _delete_result_unknown reads it).
''')

swap("App/app/door_codes.py", '''def _lock_code_state(row, owner_user_id: int) -> str:
    """Ask the lock, with one list call, whether the row's PIN still exists.

    PIN_UNKNOWN when the answer cannot be had (no account, no window, TTLock error):
    nothing is assumed either way. A code with the same name and window but another
    id is not this row's PIN, so it counts as gone.
    """
    account = ttlock.account_for(owner_user_id)
    if (
        not account
        or account["status"] != "ok"
        or not row["valid_from"]
        or not row["valid_to"]
        or not row["provider_code_id"]
    ):
        return PIN_UNKNOWN
    try:
        found = ttlock.find_code_by_name(
            int(account["id"]),
            row["lock_id"],
            f"UH-{row['id']}",
            _iso_to_ms(row["valid_from"]),
            _iso_to_ms(row["valid_to"]),
        )
    except ttlock.TTLockError:
        return PIN_UNKNOWN
    if found and str(found[1]) == str(row["provider_code_id"]):
        return PIN_PRESENT
    return PIN_GONE


def _note_failed_lookup(row_id: int, claim: str) -> int:
    """Count a failed lookup in attempts (restarted at 1 by the first one); return the count."""
    db.execute(
        "UPDATE door_code SET attempts = CASE WHEN last_error = ? THEN attempts + 1 ELSE 1 END, "
        "last_error = ?, updated_at = ? WHERE id = ? AND claimed_at = ?",
        (LOOKUP_FAILED, LOOKUP_FAILED, claim, row_id, claim),
    )
    row = db.query_one("SELECT attempts FROM door_code WHERE id = ?", (row_id,))
    return int(row["attempts"]) if row else LOOKUP_MAX_TRIES
''', '''def _lock_code_state(row, owner_user_id: int) -> str:
    """Ask the lock whether the row's PIN still exists (1 to LIST_MAX_PAGES list calls).

    PIN_GONE only when the lock's whole answer was read and the row's code id is not in it.
    PIN_UNKNOWN when the answer cannot be had or is incomplete (no account, no code id,
    TTLock error, more pages than the page limit): nothing is assumed either way. The code
    id decides, not the name or the window: UH-7 also matches UH-70 on the lock.
    """
    account = ttlock.account_for(owner_user_id)
    if not account or account["status"] != "ok" or not row["provider_code_id"]:
        return PIN_UNKNOWN
    try:
        listed = ttlock.code_is_listed(
            int(account["id"]),
            row["lock_id"],
            f"UH-{row['id']}",
            row["provider_code_id"],
        )
    except ttlock.TTLockError:
        return PIN_UNKNOWN
    if listed is None:
        return PIN_UNKNOWN
    return PIN_PRESENT if listed else PIN_GONE


def _delete_result_unknown(last_error) -> bool:
    """True when last_error leaves a delete's result open (see AMBIGUOUS_DELETE_ERRORS)."""
    text = last_error or ""
    return text in AMBIGUOUS_DELETE_ERRORS or text.startswith(LOOKUP_FAILED)


def _note_failed_lookup(row_id: int, claim: str, claimed: bool) -> int:
    """Count a failed lookup in last_error ("lookup_failed:<n>"); return n.

    attempts is the delete counter and is not a lookup counter: it is not raised here, and
    the add of 1 that _revoke_one made when it claimed the row (claimed=True) is taken back,
    so lookups never move the delete retry delays or the attempts == 3 mail.
    """
    row = db.query_one("SELECT last_error FROM door_code WHERE id = ?", (row_id,))
    previous = (row["last_error"] or "") if row else ""
    count = 1
    if previous.startswith(LOOKUP_FAILED + ":"):
        try:
            count = int(previous.split(":", 1)[1]) + 1
        except ValueError:
            count = 1
    db.execute(
        "UPDATE door_code SET attempts = attempts - ?, last_error = ?, updated_at = ? "
        "WHERE id = ? AND claimed_at = ?",
        (1 if claimed else 0, f"{LOOKUP_FAILED}:{count}", claim, row_id, claim),
    )
    return count
''')

swap("App/app/door_codes.py", '''        and (item["last_error"] or "") in AMBIGUOUS_DELETE_ERRORS
''', '''        and _delete_result_unknown(item["last_error"])
''')

swap("App/app/door_codes.py", '''        if _note_failed_lookup(row_id, claim) < LOOKUP_MAX_TRIES:
''', '''        if _note_failed_lookup(row_id, claim, held_claim is not None) < LOOKUP_MAX_TRIES:
''')

swap("App/app/door_codes.py", '''                    "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ?, "
                    "claimed_at = NULL, updated_at = ? WHERE id = ? AND state = ?",
                    (REVOKE_PENDING, now_iso, now_iso, row["id"], ISSUED),''', '''                    "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ?, "
                    "claimed_at = NULL, last_error = NULL, updated_at = ? WHERE id = ? AND state = ?",
                    (REVOKE_PENDING, now_iso, now_iso, row["id"], ISSUED),''')

swap("App/app/ttlock.py", '''def change_code_period(
    account_id: int,
''', '''LIST_PAGE_SIZE = 20
LIST_MAX_PAGES = 5


def code_is_listed(account_id: int, lock_id: str, name: str, code_id: str) -> Optional[bool]:
    """Is the lock code with this id on the lock? True, False, or None when it cannot be told.

    ``searchStr`` is a fuzzy match (UH-7 also lists UH-70 and UH-700), so the answer is read
    page by page, at most LIST_MAX_PAGES calls. False only when the last page was read and
    the id was not on any page. None when the page limit ran out first. The id decides,
    not the name or the window. TTLock errors are raised as they are.
    """
    for page in range(1, LIST_MAX_PAGES + 1):
        answer = _call(
            account_id,
            "/v3/lock/listKeyboardPwd",
            {
                "lockId": int(lock_id),
                "searchStr": name,
                "orderBy": 1,
                "pageNo": page,
                "pageSize": LIST_PAGE_SIZE,
            },
            NORMAL,
        )
        items = answer.get("list") or []
        if any(str(raw.get("keyboardPwdId")) == str(code_id) for raw in items):
            return True
        try:
            last_page = int(answer["pages"])
        except (KeyError, TypeError, ValueError):
            last_page = None
        if last_page is not None and page >= last_page:
            return False
        if last_page is None and len(items) < LIST_PAGE_SIZE:
            return False
    return None


def change_code_period(
    account_id: int,
''')

swap("App/tests/test_door_code_ambiguous_delete.py", '''    def find(*args, **kwargs):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        for code_id, pin in lock.pins.items():
            return pin, code_id
        return None
''', '''    def listed(account_id, lock_id, name, code_id):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        return str(code_id) in lock.pins
''')

swap("App/tests/test_door_code_ambiguous_delete.py", '''    monkeypatch.setattr(ttlock, "find_code_by_name", find)
''', '''    monkeypatch.setattr(ttlock, "code_is_listed", listed)
''')

swap("App/tests/test_door_code_ambiguous_delete.py", '''    assert held["state"] == door_codes.REVOKE_PENDING and held["last_error"] == door_codes.LOOKUP_FAILED
    assert held["attempts"] == 1 and lock.lookups == 1''', '''    assert held["state"] == door_codes.REVOKE_PENDING and held["last_error"] == "lookup_failed:1"
    assert held["attempts"] == 1 and lock.lookups == 1''')

swap("App/tests/test_door_code_ambiguous_delete.py", '''    assert _row(row)["attempts"] == 2 and lock.lookups == 2''', '''    assert _row(row)["last_error"] == "lookup_failed:2" and _row(row)["attempts"] == 1 and lock.lookups == 2''')

swap("App/tests/test_door_code_recancel.py", '''    def find(*args, **kwargs):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        for code_id, pin in lock.pins.items():
            return pin, code_id
        return None
''', '''    def listed(account_id, lock_id, name, code_id):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        return str(code_id) in lock.pins
''')

swap("App/tests/test_door_code_recancel.py", '''    monkeypatch.setattr(ttlock, "find_code_by_name", find)
''', '''    monkeypatch.setattr(ttlock, "code_is_listed", listed)
''')

EOF
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output. Then `git diff --stat | tail -30` -> 4 files changed (`door_codes.py`, `ttlock.py`, the two test files and nothing else).

**Step 3. Create `App/tests/test_door_code_lookup_pages.py`** with exactly:
```python
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
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_recancel.py tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30` -> `41 passed`.

**Step 4. Commit.** `git add App/app/ttlock.py App/app/door_codes.py App/tests/test_door_code_ambiguous_delete.py App/tests/test_door_code_recancel.py App/tests/test_door_code_lookup_pages.py && git commit -m "1157: a door code is called gone only when the lock's whole answer says so" | tail -30`.
Commit message ends with the attribution lines the session reminder gives.

**Step 5. Revert-bite, five runs.** Each run, from the repo root: apply the `sed`, run `T`, expect the named result, then `git checkout App/app | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py -q --tb=no -rf 2>&1 | tail -30`. After each `sed`, `git diff --stat | tail -30` must show `1 file changed, 1 insertion(+), 1 deletion(-)`.
- (a) Stop after page 1 (the old behaviour): `sed -i 's/^        if last_page is not None and page >= last_page:$/        if True:/' App/app/ttlock.py` then `T`: `7 failed, 9 passed` (`code_on_page_two_is_present`, `code_missing_from_every_page_is_gone`, `list_longer_than_the_page_limit`, `answer_without_a_pages_field`, `cancelled_stay_whose_code_is_on_page_two`, `revived_row_whose_code_is_on_page_two`, `incomplete_list_keeps_a_cancelled_row_pending`).
- (b) Incomplete counts as gone: `sed -i '/^def code_is_listed/,/^def change_code_period/ s/^    return None$/    return False/' App/app/ttlock.py` then `T`: `2 failed, 14 passed` (`list_longer_than_the_page_limit`, `incomplete_list_keeps_a_cancelled_row_pending`).
- (c) No pages field, no read-on: `sed -i 's/^        if last_page is None and len(items) < LIST_PAGE_SIZE:$/        if last_page is None:/' App/app/ttlock.py` then `T`: `1 failed, 15 passed` (`answer_without_a_pages_field`).
- (d) Claim counted as a lookup: `sed -i 's/(1 if claimed else 0, f"/(0, f"/' App/app/door_codes.py` then `T`: `1 failed, 15 passed` (`lookups_through_the_claim_give_up_after_exactly_three`).
- (e) Stale error kept: `sed -i 's/"claimed_at = NULL, last_error = NULL, updated_at = ? WHERE id = ? AND state = ?",/"claimed_at = NULL, updated_at = ? WHERE id = ? AND state = ?",/' App/app/door_codes.py` then `T`: `1 failed, 15 passed` (`stale_error_on_an_issued_row`).
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 6. Door-codes row (test-map) and lint.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -rs 2>&1 | tail -30` -> no failures; only the two `playwright` skips. Then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 7. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_recancel.py -q --tb=short 2>&1 | tail -30` -> all pass (or report `not run: no Postgres`).

**Step 8. Report.** Write `docs/tasks/1157-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root.

## 5. Do not touch

`ttlock.find_code_by_name` and its `issue()` caller, `cleaning_codes.py`, `ttlock.ERROR_KINDS` (no errcode is guessed), `_revive_one`, `_revoke_one`, `_already_gone` bodies, `docs/context/*`, migrations, `go/`. Hard rules: 3, 4, 5.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 2 to 7 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] `test_door_code_lookup_pages.py` is 9 passed; step 3 shows `41 passed` with the 1149, 1155, 1155b files.
- [ ] The five revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] The door-codes row passes with only the two `playwright` skips; ruff passes; Postgres run passes or is reported as not run.
- [ ] The report repeats the outbound-request reason from §2 for the PR description and says `cleaning_codes._find` has the same page-1 limit.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (an `AssertionError` from the script), or 1155, 1155b or 1156 is not in the tree;
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1157-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/ttlock.py` `code_is_listed` (when it may say False), `App/app/door_codes.py` `_lock_code_state` (only a full read says gone), `_note_failed_lookup` (the claim take-back and the `lookup_failed:<n>` text).

## Owner steps

1. Open the pull request for `task/1157-door-lookup-hardening` as a draft; paste the outbound-request reason from §2 into its description.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8). Merge 1157 before 1157b.
3. The orchestrator then adds one line to `docs/context/decisions.md` (lookup reads the whole list, id match, unknown is safe) and a known-issues line for `cleaning_codes._find`.
