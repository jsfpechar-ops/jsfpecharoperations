# 1162: a cleaning code is called absent only when the lock's whole answer says so

Status: todo
Depends on: 1160, 1160b, 1160c (merged) | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 | Branch: task/1162-cleaning-code-paging
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`cleaning_codes._find` reconciles a cleaning code with the lock by reading only page 1 (20 codes) of a fuzzy `listKeyboardPwd` search, and trusts any answer, even one without a `list`. A miss makes `process_queue` add a second permanent code (after a timeout) or call a live code revoked and leave it on the door. Fix: `_find` reads through the same paging loop as `ttlock.code_is_listed` (a full page reads on, at most `ttlock.LIST_MAX_PAGES` calls); a non-list answer, or a list still full after the last page, is unknown: it raises a transient error and takes the existing retry path. Also, the first-line docstrings of two door-code tests say 1157/1157b; the briefs were renumbered, so they become 1160/1160b.

## 2. Context

Rules: SQL only through `db` helpers; no dependency, no migration, no new state transition, no new endpoint. Anchors are verbatim from HEAD after 1160, 1160b and 1160c; the script in step 2 asserts each anchor exists exactly once and stops with an `AssertionError` if not (then STOP, §8).

**What `_find` is for.** Only `process_queue` calls it (the guest-code worker, one row at a time), to find the row's own provider code by its exact `operation_ref` name (`UH Cleaning <16 hex>`) before acting, because an earlier attempt may have timed out after the lock had already done the work:
- issuing (`state` `retrying`, `attempts > 1`): `code_id = _find(row) if attempts > 1 else None`; a found id is adopted, `None` makes the worker call `ttlock.add_permanent_code`.
- revoking (`state` `revoke_pending`): `code_id = _find(row) if attempts > 1 else (row["provider_code_id"] or _find(row))`; a found id is deleted on the lock, then the row becomes `revoked` with `pin_enc` wiped, whether or not an id was found.

**What a miss caused.** `_find` returned `None` ("not on the lock") for an incomplete read:
1. Issuing: the code that a timed-out add had created sat on page 2 (other names containing the operation name, e.g. a busy lock), so `_find` said `None`, the worker added a **second** permanent code with the same PIN and name, and the first stayed on the lock as an **orphan** (later `_find` calls then raised `ambiguous operation` and the row ended `failed`).
2. Revoking: the code was not on page 1, so `_find` said `None`, nothing was deleted, and the row became `revoked` with its PIN wiped: the cleaning code **still opens the door** and the app no longer knows it.
3. An answer without a `list` (`{}`, `{"pages": 1}`, `{"list": null}`) was read as an empty list, with the same two outcomes; a `list` that was a string or an object raised `AttributeError` or matched wrongly.

**The paging loop (1160/1160c, kept as the single loop).** `ttlock.code_is_listed` holds the loop today: it sends `searchStr` and `pageNo 1..LIST_MAX_PAGES` (`LIST_MAX_PAGES = 5`, `LIST_PAGE_SIZE = 20`), a non-list `list` answers `None`, a page shorter than 20 ends the list, `pages` is not trusted. Step 2 moves that loop into `ttlock._read_listing(account_id, lock_id, name, keep, stop_at_first=False)`, which returns only the entries `keep` accepts (unrelated PINs are not retained) or `None` when the list is incomplete. `code_is_listed` becomes a thin caller (`stop_at_first=True`, so its call counts stay as in 1160: it stops at the page that holds the id). The new `ttlock.codes_named(account_id, lock_id, name)` is the second caller: exact `keyboardPwdName` matches, read to the end of the list (no early stop) so a second code with the same name is still seen as `ambiguous operation`. The adoption needs only name, PIN and type, never a time window (permanent codes have none), so there is no window matching.

**New rule in `_find`.** `codes_named` returns `None` -> `raise ttlock.TTLockError("incomplete code list", kind="transient")`. `process_queue` already catches `TTLockError` and calls `_failure`: transient errors retry with delays 1, 5, 15, 60, 240 minutes while `attempts < 5`; after that an issuing row becomes `failed` (the owner can re-queue it, `queue_permanent`) and a revoking row becomes `revoke_failed` (kept with its `pin_enc` so `remove` can queue it again). Never `revoked` and never a second add on unknown. A complete list with no match stays `None` (really absent). Nothing else in `cleaning_codes.py` changes.

**Outbound request (for the PR, rule 2).** `_find` made exactly 1 `POST /v3/lock/listKeyboardPwd`; it now makes 1 to 5: one per page of 20 codes whose name contains the operation name, stopping at the first page with fewer than 20 codes or at the limit of 5 (a list that ends exactly on a full page costs one extra, empty page). The operation name is `UH Cleaning <16 random hex>`, so in practice a search matches 0 or 1 codes and the cost stays 1 call; the 5 is a worst-case bound. Same endpoint (already in `ttlock.ALLOWED_PATHS`), same host, same payload plus `pageNo`, priority `NORMAL` as before. Only on a retry (`attempts > 1`) or a revoke with no stored provider id; a row is tried at most 5 times, so at most 25 calls per row over its life. Reason: concluding that a code is absent from a partial list adds a duplicate code or leaves a working one on the door. No new personal data.

Anchors (all in the script of step 2): `ttlock.py` the import line `from typing import Any, Dict, List, Optional, Tuple`, the head of `code_is_listed` up to `for page in range(1, LIST_MAX_PAGES + 1):`, and its tail from `items = answer.get("list")` to `return None`; `cleaning_codes.py` the head of `_find` up to `if len(matches) > 1:`; the two docstring first lines in the door-code tests.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/ttlock.py | edit | `Callable` import; `_read_listing` (the loop); `code_is_listed` thin; `codes_named` |
| App/app/cleaning_codes.py | edit | `_find` uses `codes_named`; `None` raises a transient error |
| App/tests/test_cleaning_code_lookup_pages.py | create | 19 cases with a fake lock that pages like TTLock |
| App/tests/test_door_code_lookup_pages.py | edit | first docstring line 1157 -> 1160 |
| App/tests/test_door_code_reissue_notice.py | edit | first docstring line 1157b -> 1160b |
| docs/tasks/1162-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1160c is in: `grep -c "def code_is_listed" App/app/ttlock.py | tail -30` -> `1`, `grep -c "def _read_listing" App/app/ttlock.py | tail -30` -> `0`, `grep -c "isinstance(items, list)" App/app/ttlock.py | tail -30` -> `1` (else STOP). Then `git switch -c task/1162-cleaning-code-paging | tail -30`; expected `Switched to a new branch`.

**Step 2. Apply the code and docstring changes.** Write the script below to `/tmp/1162_step2.py` (the heredoc ends at the line `PYEOF`), then run it from the repo root with `python3 /tmp/1162_step2.py | tail -30` (every `swap` asserts its old text exists exactly once; no output means success):
```bash
cat > /tmp/1162_step2.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:60])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

swap("App/app/ttlock.py", '''def code_is_listed(account_id: int, lock_id: str, name: str, code_id: str) -> Optional[bool]:
    """Is the lock code with this id on the lock? True, False, or None when it cannot be told.

    ``searchStr`` is a fuzzy match (UH-7 also lists UH-70 and UH-700), so the answer is read
    page by page, at most LIST_MAX_PAGES calls. A full page (LIST_PAGE_SIZE codes) is always
    read on past, whatever ``pages`` says. False only when a short or empty page ended the
    list and the id was on no page. None when an answer has no ``list`` array, or when the
    page limit ran out first. The id decides, not the name or the window. TTLock errors are
    raised as they are.
    """
    for page in range(1, LIST_MAX_PAGES + 1):
''', '''def _read_listing(
    account_id: int, lock_id: str, name: str, keep: Callable[[dict], bool], stop_at_first: bool = False
) -> Optional[List[dict]]:
    """The one paging loop over /v3/lock/listKeyboardPwd; returns only the entries ``keep`` accepts.

    ``searchStr`` is a fuzzy match (UH-7 also lists UH-70 and UH-700), so the answer is read
    page by page, at most LIST_MAX_PAGES calls. A full page (LIST_PAGE_SIZE codes) is always
    read on past, whatever ``pages`` says. The kept entries (possibly none) are returned only
    when a short or empty page ended the list, or, with ``stop_at_first``, at the first kept
    entry. None when an answer has no ``list`` array, or when the page limit ran out first:
    the list is then incomplete and nothing may be concluded from it. TTLock errors are
    raised as they are.
    """
    kept: List[dict] = []
    for page in range(1, LIST_MAX_PAGES + 1):
''')

swap("App/app/ttlock.py", '''        items = answer.get("list")
        if not isinstance(items, list):
            return None
        if any(str(raw.get("keyboardPwdId")) == str(code_id) for raw in items):
            return True
        if len(items) < LIST_PAGE_SIZE:
            return False
    return None
''', '''        items = answer.get("list")
        if not isinstance(items, list):
            return None
        kept.extend(raw for raw in items if keep(raw))
        if kept and stop_at_first:
            return kept
        if len(items) < LIST_PAGE_SIZE:
            return kept
    return None


def code_is_listed(account_id: int, lock_id: str, name: str, code_id: str) -> Optional[bool]:
    """Is the lock code with this id on the lock? True, False, or None when it cannot be told.

    False only when the whole list was read and the id was on no page. The id decides, not
    the name or the window.
    """
    found = _read_listing(
        account_id, lock_id, name,
        lambda raw: str(raw.get("keyboardPwdId")) == str(code_id), stop_at_first=True,
    )
    return None if found is None else bool(found)


def codes_named(account_id: int, lock_id: str, name: str) -> Optional[List[dict]]:
    """Every lock code whose name is exactly ``name`` (raw entries), or None when the list is incomplete.

    An empty list means the whole list was read and no code has that name. Reads to the end
    of the list (no early stop), so a second code with the same name is seen.
    """
    return _read_listing(account_id, lock_id, name, lambda raw: raw.get("keyboardPwdName") == name)
''')

swap("App/app/ttlock.py", "from typing import Any, Dict, List, Optional, Tuple\n",
     "from typing import Any, Callable, Dict, List, Optional, Tuple\n")

swap("App/app/cleaning_codes.py", '''def _find(row: dict) -> str | None:
    # The narrow exact-name match is an idempotency lookup, never a code-list
    # poll. Do not retain unrelated PINs returned by TTLock.
    answer = ttlock._call(row["lock_account_id"], "/v3/lock/listKeyboardPwd", {
        "lockId": int(row["lock_id"]), "searchStr": row["operation_ref"],
        "pageNo": 1, "pageSize": 20, "orderBy": 1,
    }, ttlock.NORMAL)
    matches = [entry for entry in answer.get("list", []) if
               entry.get("keyboardPwdName") == row["operation_ref"]]
    if len(matches) > 1:
''', '''def _find(row: dict) -> str | None:
    # The narrow exact-name match is an idempotency lookup, never a code-list
    # poll. Do not retain unrelated PINs returned by TTLock. None means the whole
    # list was read and the operation is not on the lock; an incomplete list
    # (non-list answer, more pages than ttlock.LIST_MAX_PAGES) raises a transient
    # error, so the caller neither adds a second code nor calls a code revoked.
    matches = ttlock.codes_named(row["lock_account_id"], row["lock_id"], row["operation_ref"])
    if matches is None:
        raise ttlock.TTLockError("incomplete code list", kind="transient")
    if len(matches) > 1:
''')

swap("App/tests/test_door_code_lookup_pages.py", '"""1157: a door code is called gone', '"""1160: a door code is called gone')
swap("App/tests/test_door_code_reissue_notice.py", '"""1156, 1157b: the host is told once', '"""1156, 1160b: the host is told once')
PYEOF
```
Command: `cd App && .venv/bin/python -c "import app.cleaning_codes" 2>&1 | tail -30` -> no output. Then, from the repo root, `git diff --stat | tail -30` -> 4 files changed (`ttlock.py`, `cleaning_codes.py`, the two door-code tests), `4 files changed, 45 insertions(+), 18 deletions(-)` (a few lines off is fine; a fifth file is not).

**Step 3. Door-code paging tests and the cleaning tests still pass.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code_lookup_pages.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_recancel.py tests/test_cleaning.py -q --tb=short 2>&1 | tail -30` -> all pass, none failed (`test_cleaning.py` still adopts and reconciles with its short fake lists).

**Step 4. Create `App/tests/test_cleaning_code_lookup_pages.py`** with exactly:
```python
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
```
Command, from `App/`: `.venv/bin/python -m pytest tests/test_cleaning_code_lookup_pages.py -q --tb=short 2>&1 | tail -30` -> `19 passed`.

**Step 5. Commit.** `git add App/app/ttlock.py App/app/cleaning_codes.py App/tests/test_cleaning_code_lookup_pages.py App/tests/test_door_code_lookup_pages.py App/tests/test_door_code_reissue_notice.py && git commit -m "1162: a cleaning code is called absent only when the lock's whole list says so" | tail -30` -> a commit line.

**Step 6. Revert-bite, four runs.** Each run, from the repo root: apply the `sed`, check `git diff --stat | tail -30` shows `1 file changed`, run `T`, expect the named result, then `git checkout App/app | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_cleaning_code_lookup_pages.py tests/test_door_code_lookup_pages.py -q --tb=no -rf 2>&1 | tail -30` (36 tests; unbitten: `36 passed`; run `T` once first to see it). Run `T` from the repo root's `App/` and come back (`cd ..`) after.
- (a) Unknown read as absent, in `_find`: `sed -i 's/raise ttlock.TTLockError("incomplete code list", kind="transient")/return None/' App/app/cleaning_codes.py` then `T`: `13 failed, 23 passed` (the two page-limit cases, ten no-list cases, `retries_are_bounded`).
- (b) Non-list guard off in the loop: `sed -i 's/if not isinstance(items, list):/if False:/' App/app/ttlock.py` then `T`: `16 failed, 20 passed`.
- (c) Page 1 only, as before: `sed -i 's/range(1, LIST_MAX_PAGES + 1)/range(1, 2)/' App/app/ttlock.py` then `T`: `11 failed, 25 passed`.
- (d) Name filter dropped in `codes_named`: `sed -i 's/lambda raw: raw.get("keyboardPwdName") == name)/lambda raw: True)/' App/app/ttlock.py` then `T`: `5 failed, 31 passed`.
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 7. Test-map rows and lint.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_cleaning*.py tests/test_sm_cleaning_code_state.py tests/test_sm_go_parity.py -q --tb=short -rs 2>&1 | tail -30` -> `372 passed, 3 skipped` (the three skips are `playwright` not installed; the passed count may differ by a few if a test was added meanwhile, a failure may not). Then `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 8. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_cleaning_code_lookup_pages.py tests/test_door_code_lookup_pages.py tests/test_cleaning.py -q --tb=short 2>&1 | tail -30` -> all pass (or report `not run: no Postgres`).

**Step 9. Report.** Write `docs/tasks/1162-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root -> OK.

## 5. Do not touch

`door_codes.py`, `ttlock.find_code_by_name`, `ttlock.ERROR_KINDS`, `cleaning_codes._failure` and `process_queue`, `docs/context/*`, migrations, `go/`. Hard rules: 2 (the outbound note above goes into the PR), 3, 4, 5.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 3 to 8 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] Step 4 shows `19 passed`; Step 3 shows no failure.
- [ ] The four revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] The test-map rows pass with only the three `playwright` skips; ruff passes; Postgres run passes or is reported as not run.
- [ ] `grep -c "listKeyboardPwd" App/app/cleaning_codes.py | tail -30` -> `0` (one paging loop, in `ttlock.py`).
- [ ] The two door-code test files start with `1160` / `1156, 1160b`.
- [ ] The report states the outbound-request reason: 1 call before, 1 to 5 now (normally 1), at most 25 per row.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (a `swap` assertion fails or a Step 1 count differs);
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1162-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/ttlock.py` `_read_listing` (kept entries returned only after a short page, or at the first kept entry with `stop_at_first`; `None` on a non-list answer or after the page limit), `App/app/cleaning_codes.py` `_find` (`None` from `codes_named` must raise, never return), the 19 new cases.

## Owner steps

1. Open the pull request for `task/1162-cleaning-code-paging` as a draft; put the outbound-request note from §2 in its description.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8).
