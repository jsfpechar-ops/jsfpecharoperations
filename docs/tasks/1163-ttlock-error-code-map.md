# 1163: map every TTLock errcode our calls can get to the kind that decides what we do (K-DC-ERRCODE)

Status: review
Depends on: 1162 (merged) | Base commit: 9e95c0e9 (HEAD of claude/zealous-maxwell-a7ub54 after 1162, 1161 and 1161b) | Branch: task/1163-ttlock-error-codes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`ttlock.ERROR_KINDS` maps 22 errcodes; the rest of TTLock's official table (owner pasted it 2026-10-26) becomes kind `transient`. A lock-offline answer is then retried correctly but also triggers the 1155b list lookup (and a list that does not show the code then calls the PIN revoked). A frozen or missing lock, a wrong region host (`30008`) and a refused PIN are retried as if the cloud were flaky, and a delete answering `-1007` ("passcode not on the lock") is never recognised. Fix: map every code our calls can receive to an existing kind (`offline`, `config`, `bug`), add one new kind `code_missing` for `-1007` and wire it, and document the whole table once.

## 2. Context

Rules: SQL only through `db` helpers; no dependency, no migration, no new state, no new endpoint, no host copy (so no i18n file changes). Anchors are verbatim from HEAD after 1162 and 1161; the scripts assert each anchor exists exactly once and stop with an `AssertionError` if not (then STOP, §8). Go has no TTLock client (`grep -rin "keyboardPwd\|errcode" go --include=*.go` finds nothing; the palette only reads a `ttlock enabled` flag), so nothing is mirrored there.

**What each kind does today** (read from `door_codes.py`, `cleaning_codes.py`, `routes/admin.py`):
- Issue (`issue()`): `reauth`, `permission`, `config`, `disabled` hand over at once (row `failed`, `door_code_failed` alert, host mail; `storage` and `duplicate` also in the period-taken path); `budget` retries in 60 min without counting; every other kind (incl. `offline`, `transient`, `bug`) retries after 1 minute and fails after `ISSUE_MAX_ATTEMPTS = 2` (`PERIOD_TAKEN_MAX_ATTEMPTS = 4` on the custom-add path). So `bug` is already bounded; nothing retries for ever.
- Revoke (`_revoke_one`): kinds in `GATEWAY_RETRY_KINDS` (`offline`, `transient`, `network`, `rate`, `budget`) retry after 1, 15, 60 minutes until `valid_to` (host mail `cancelled_not_deleted` at attempt 3), then `revoke_failed`; any other kind (`config`, `permission`, `bug`, ...) is `revoke_failed` at once with the host mail. An errcode that is not `None` and not in `ERROR_KINDS` first triggers `_already_gone` (1155b): one `code_is_listed` lookup, and only `PIN_GONE` counts as revoked.
- Move replace (`door_codes` ~line 1267): `permission`, `reauth`, `config`, `disabled` mail the host and are not retried; everything else retries every 15 minutes.
- Clock check (`check_lock_clocks`, ~line 1340): `offline`, `transient`, `network`, `rate`, `budget` retry in a day; anything else raises the `door_code_clock` alert and waits 7 days (right for `-4043` "not supported").
- Cleaning (`cleaning_codes._failure`): the same retry set; any other kind ends `failed` / `revoke_failed` at once (kept for the owner to re-queue).
- Smart-locks page (`routes/admin.py` ~796): only `budget` and `reauth` read the kind.
- There is no separate "offline host alert": an offline answer retries, then the `door_code_failed` alert and mail say "gateway offline" (`mail_notify._DOOR_CODE_REASON_KINDS`: `offline` -> that text). Unchanged.

**The mapping (final).** `offline` (retry later, no lookup): `-3002`, `-3003`, `-3035`, `-3036`, `-3037`, `-2025`. `config` (host or server setting must be fixed, no retry): `-1003`, `-4037`, `-4043`, `-3034`, `-4067`, `-4063`, `30008`. `bug`: `80002`, `-2009`, `-2032`, `-3006`, `-3045`. New kind `code_missing`: `-1007`. Not mapped on purpose (our calls never get them, so the default `transient` stays): the eKey codes `-1008 -1016 -1018 -1027 -2019 -2020 -2023 -3039 -3046 -4064` (`/v3/key/list` is the only eKey endpoint in `ALLOWED_PATHS`), `-1021 -1023` (IC card), `-3011` (transfer), `-4082` (auto-lock), and `-3016` (the pasted table gives no meaning). `-4063` ("delete or transfer locks first") can only come from `/v3/user/delete` (`delete_account`); `config` is its closest kind (the host removes the locks first). `30008` is the server's `UBYHOST_TTLOCK_API_BASE` pointing at the wrong region: as `config` it stops at once like `10000`/`10001` do; there is still no separate operator alert (not part of this brief).

**Why mapped codes also matter for the 1155b lookup.** `_already_gone` skipped the lookup for every errcode in `ERROR_KINDS`. Before this brief a `-3036` ("lock offline") was unmapped, so it cost a list call, and if that call did not list the id the PIN was called revoked on an answer that says nothing about the code. Mapping the offline codes closes that.

**Decision: `-1007` on a delete.** `-1007` ("No password data of this lock") on `keyboardPwd/delete` means the cloud holds no such passcode. It is a new kind `code_missing`, and it is still confirmed by `code_is_listed` (the 1155b lookup), not trusted alone: a wrong reading must never leave a cancelled guest's PIN working. `_already_gone` runs the lookup for `-1007` and for unmapped codes only (never for any other mapped code). `PIN_GONE` -> the normal `revoked` write, `door_code_revoked` audit and `cancelled_deleted` mail, with the audit detail ending `via=gone:-1007` (and a `DOOR_CODE_PROBLEM stage=delete_gone` log line) so the cases are told apart. `PIN_PRESENT` or `PIN_UNKNOWN` -> the existing retry path, so `code_missing` joins `GATEWAY_RETRY_KINDS` (it behaved as `transient` before; `last_error` now reads `code_missing`). Cost unchanged: one `listKeyboardPwd` page loop, 1 to 5 calls, same endpoint, host and payload, only after a `-1007` or unmapped refusal of a delete.
**`-1007` on the list.** `code_is_listed` can get it (a lock with no codes at all). Left as an error it would be `PIN_UNKNOWN` for ever, and the delete would retry until `valid_to` and mail the host falsely. So `_read_listing` (the loop `code_is_listed` and `codes_named` share) reads `-1007` on page 1 as an empty list (`code_is_listed` -> `False`, `codes_named` -> `[]`). On page 2 or later it is contradictory and is raised as it is (unknown). Effect on cleaning (`cleaning_codes._find`): `-1007` on page 1 is now "the lock has no code with that name", the same conclusion 1162 draws from any complete empty list.
**Open question for the owner (not decided here).** TTLock support said (`docs/TTLOCK.md`, `-3008` row) that a type-3 random code does not exist on the lock until first use. If an unused random code is also absent from the cloud's list, "delete says `-1007` and the list shows no id" would call a never-typed PIN revoked while it may still open the door at its start time. The 1155b path has the same exposure today for unmapped answers; this brief does not widen it beyond `-1007`.

**Passcode-format codes.** Our PINs come from `ttlock._random_custom_pin` (7 digits, `1000000` to `9999999`) in `add_custom_code`, which already retries once with a new PIN on `-3007`. A random 7-digit PIN can be "too simple" (`1234567`, `7777777`), so `-2032` joins `-3007` in that retry (`NEW_PIN_ERRCODES`); a second refusal is raised (kind `bug`, then `issue()`'s existing cap). `-3006` (length), `-3045` (digit), `-2009`, `80002` cannot be cured by another random 7-digit PIN, so they are raised at once as `bug` (one call). `add_permanent_code` (cleaning) takes its PIN from the caller and has no retry: its `bug` ends the row `failed` for the owner.

**Cleaning codes mirror the door codes.** `cleaning_codes._failure` retries only its own kind set, so `code_missing` is added to it (a `-1007` retries with the 1, 5, 15, 60, 240 minute delays, `last_error` reads `code_missing`). A cleaning delete that answers `-1007` is confirmed like a door delete: new `cleaning_codes._already_gone` calls `ttlock.code_is_listed` (the same exhaustive `_read_listing` loop, 1 to 5 `listKeyboardPwd` calls, same endpoint, host and payload, only after a `-1007` refusal of a cleaning delete) and only a fully read list without the id counts as deleted (the normal `revoked` write with `pin_enc` wiped). A lookup that fails, is incomplete or still lists the id re-raises the `-1007`, so the row is retried. Unlike door codes it is not run for unmapped errcodes (cleaning never did that; no behaviour is added there).

Anchors (all in the scripts below): `ttlock.py` the end of `ERROR_KINDS` (`-3007: "duplicate",` and `}`), `if exc.code != -3007:` in `add_custom_code`, and the `_read_listing` docstring tail and its `answer = _call(` block (the 1162 text); `cleaning_codes.py` the `_failure` head and the `if code_id:` delete in `process_queue`; `door_codes.py` the `GATEWAY_RETRY_KINDS` line, the `_already_gone` docstring and first lines, the `attempts = int(row["attempts"])` block of `_revoke_one`, and the `door_code_revoked` audit.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/ttlock.py | edit | 19 `ERROR_KINDS` entries, `CODE_MISSING`, `NO_PASSCODE_DATA`, `NEW_PIN_ERRCODES`; `-1007` on list page 1 is empty; `-2032` retries with a new PIN |
| App/app/cleaning_codes.py | edit | `_failure` retries `code_missing`; new `_already_gone` (list-confirmed `-1007`) around the cleaning delete |
| App/app/door_codes.py | edit | `GATEWAY_RETRY_KINDS` gains `code_missing`; `_already_gone` runs the lookup for `-1007` and unmapped only; audit detail `via=gone:<code>` |
| App/tests/test_ttlock_error_map.py | create | 37 cases (19 parametrized map checks, 18 behavioural) |
| docs/plans/ttlock-door-codes.md | edit | new section 3.1: the full error table with our kind |
| docs/TTLOCK.md | edit | three error rows updated (no longer "unmapped today") |
| docs/tasks/1163-report.md | create | report (§9) |

1162 (merged) and 1163 both touch `ttlock.py`: 1162 went first and 1163's anchors are the post-1162 text. No other open brief may edit `ERROR_KINDS`, `add_custom_code`, `_read_listing`, `door_codes._revoke_one` or `_already_gone` before this merges (`context lint` warns on overlaps). 

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1162 is in: `grep -c "def _read_listing" App/app/ttlock.py | tail -30` -> `1`, `grep -c "def codes_named" App/app/ttlock.py | tail -30` -> `1`, `grep -c "NEW_PIN_ERRCODES" App/app/ttlock.py | tail -30` -> `0` (else STOP). Then `git switch -c task/1163-ttlock-error-codes | tail -30`; expected `Switched to a new branch`.

**Step 2. Code.** Write the script to `/tmp/1163_code.py` (the heredoc ends at the line `PYEOF`), then run it from the repo root with `python3 /tmp/1163_code.py | tail -30` (no output means success):
```bash
cat > /tmp/1163_code.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

swap("App/app/ttlock.py", '''    -3007: "duplicate",
}
''', '''    -3007: "duplicate",
    # 1163: the rest of TTLock's official error table that our calls can get
    # (full table and meanings: docs/plans/ttlock-door-codes.md section 3).
    # The passcode is not on the lock; a delete confirms it with a list call.
    -1007: "code_missing",
    # The lock or its gateway cannot be reached now: retry later, never a lookup.
    -3002: "offline",
    -3003: "offline",
    -3035: "offline",
    -3036: "offline",
    -3037: "offline",
    -2025: "offline",
    # The host (or the server's region setting) must fix the setup: no retry.
    -1003: "config",
    -4037: "config",
    -4043: "config",
    -3034: "config",
    -4067: "config",
    -4063: "config",
    30008: "config",
    # Our request was malformed or the code is unusable: a UbyHost bug, no endless retry.
    80002: "bug",
    -2009: "bug",
    -2032: "bug",
    -3006: "bug",
    -3045: "bug",
}
CODE_MISSING = "code_missing"
NO_PASSCODE_DATA = -1007
# A PIN the lock refuses is replaced once by a new random PIN (the second refusal is raised).
NEW_PIN_ERRCODES = (-3007, -2032)
''')

swap("App/app/ttlock.py", '''        if exc.code != -3007:
            raise''', '''        if exc.code not in NEW_PIN_ERRCODES:
            raise''')

swap("App/app/ttlock.py", '''    the list is then incomplete and nothing may be concluded from it. TTLock errors are
    raised as they are.
    """
    kept: List[dict] = []
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
        items = answer.get("list")
''', '''    the list is then incomplete and nothing may be concluded from it. TTLock errors are
    raised as they are, except -1007 ("No password data of this lock") on page 1: the lock
    has no codes at all, an empty list (the kept entries are then none).
    """
    kept: List[dict] = []
    for page in range(1, LIST_MAX_PAGES + 1):
        try:
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
        except TTLockError as exc:
            if exc.code == NO_PASSCODE_DATA and page == 1:
                return kept
            raise
        items = answer.get("list")
''')

swap("App/app/door_codes.py", 'GATEWAY_RETRY_KINDS = ("offline", "transient", "network", "rate", "budget")',
     'GATEWAY_RETRY_KINDS = ("offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING)')

swap("App/app/door_codes.py", '''    TTLock answers a delete of a missing code with an errcode this repo does not map
    (the not-found number is not recorded, so none is guessed). Only such an unmapped
    errcode, never a network error or a mapped one, costs one list call; the code counts
    as deleted only when the lock confirms it is gone.
    """
    if exc.code is None or exc.code in ttlock.ERROR_KINDS:
        return False
''', '''    TTLock answers a delete of a missing code with -1007 (kind code_missing) or with an
    errcode this repo does not map. Only those two, never a network error or any other
    mapped errcode (offline, permission, config, ...), cost one list call; the code counts
    as deleted only when the lock confirms it is gone.
    """
    mapped = ttlock.ERROR_KINDS.get(exc.code)
    if exc.code is None or mapped not in (None, ttlock.CODE_MISSING):
        return False
''')

swap("App/app/door_codes.py", '''    attempts = int(row["attempts"])
    try:
        try:
            ttlock.delete_code(
                int(account["id"]),
                row["lock_id"],
                row["provider_code_id"] or "",
            )
        except ttlock.TTLockError as exc:
            if not _already_gone(exc, row, apartment["owner_user_id"]):
                raise
''', '''    attempts = int(row["attempts"])
    via = ""
    try:
        try:
            ttlock.delete_code(
                int(account["id"]),
                row["lock_id"],
                row["provider_code_id"] or "",
            )
        except ttlock.TTLockError as exc:
            if not _already_gone(exc, row, apartment["owner_user_id"]):
                raise
            via = f" via=gone:{exc.code}"
            log.warning("DOOR_CODE_PROBLEM stage=delete_gone door_code=%s errcode=%s", row_id, exc.code)
''')

swap("App/app/door_codes.py", '''        db.audit(
            "door_code_revoked",
            f"door_code={row_id}",
''', '''        db.audit(
            "door_code_revoked",
            f"door_code={row_id}{via}",
''')

swap("App/app/cleaning_codes.py", '''def _failure(row: dict, error: ttlock.TTLockError, revoking: bool) -> None:
    transient = error.kind in {"offline", "transient", "network", "rate", "budget"}
''', '''def _already_gone(error: ttlock.TTLockError, row: dict, code_id: str) -> bool:
    """A refused delete that may only mean "that code is no longer on the lock" (-1007).

    Same rule as door_codes._already_gone: -1007 is never trusted alone; the exhaustive
    list (ttlock.code_is_listed, 1 to LIST_MAX_PAGES calls) must be read in full without
    the id. A lookup that fails or is incomplete means not gone: the delete is retried.
    """
    if error.kind != ttlock.CODE_MISSING:
        return False
    try:
        return ttlock.code_is_listed(
            row["lock_account_id"], row["lock_id"], row["operation_ref"], code_id,
        ) is False
    except ttlock.TTLockError:
        return False


def _failure(row: dict, error: ttlock.TTLockError, revoking: bool) -> None:
    transient = error.kind in {"offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING}
''')

swap("App/app/cleaning_codes.py", '''                if code_id:
                    ttlock.delete_code(row["lock_account_id"], row["lock_id"], code_id)
''', '''                if code_id:
                    try:
                        ttlock.delete_code(row["lock_account_id"], row["lock_id"], code_id)
                    except ttlock.TTLockError as error:
                        if not _already_gone(error, row, code_id):
                            raise
''')
PYEOF
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output. Then from the repo root `git diff --stat | tail -30` -> only `cleaning_codes.py`, `door_codes.py` and `ttlock.py` (about `82 insertions(+), 22 deletions(-)`).

**Step 3. Tests.** Create `App/tests/test_ttlock_error_map.py` with exactly (the heredoc ends at the line `TESTEOF`):
```bash
cat > App/tests/test_ttlock_error_map.py <<'TESTEOF'
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
TESTEOF
```
Command (from `App/`, Postgres): `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_ttlock_error_map.py -q --tb=short 2>&1 | tail -30` -> `37 passed`.

**Step 4. Revert-bite.** Write the script to `/tmp/1163_bite.py`, run it from the repo root. Each case puts one change back, runs the new test file, restores the file and prints `BITES` when the failure count is the expected one:
```bash
cat > /tmp/1163_bite.py <<'PYEOF'
import subprocess, sys

CASES = [
    ("already_gone", "App/app/door_codes.py",
     "if exc.code is None or mapped not in (None, ttlock.CODE_MISSING):",
     "if exc.code is None or exc.code in ttlock.ERROR_KINDS:", 3),
    ("retry_kinds", "App/app/door_codes.py", '"budget", ttlock.CODE_MISSING)', '"budget")', 2),
    ("map_1007", "App/app/ttlock.py", '    -1007: "code_missing",\n', "", 4),
    ("map_offline", "App/app/ttlock.py", '    -3036: "offline",\n', "", 2),
    ("list_1007", "App/app/ttlock.py", "if exc.code == NO_PASSCODE_DATA and page == 1:", "if False:", 2),
    ("new_pin", "App/app/ttlock.py", "NEW_PIN_ERRCODES = (-3007, -2032)", "NEW_PIN_ERRCODES = (-3007,)", 2),
    ("clean_retry", "App/app/cleaning_codes.py", '"budget", ttlock.CODE_MISSING}', '"budget"}', 1),
    ("clean_gone", "App/app/cleaning_codes.py", "if error.kind != ttlock.CODE_MISSING:", "if True:", 1),
    ("audit_via", "App/app/door_codes.py", 'f"door_code={row_id}{via}"', 'f"door_code={row_id}"', 1),
]
bad = 0
for name, path, old, new, want in CASES:
    original = open(path, encoding="utf-8").read()
    assert original.count(old) == 1, (name, old)
    try:
        open(path, "w", encoding="utf-8").write(original.replace(old, new))
        out = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "tests/test_ttlock_error_map.py", "-q", "--tb=no"],
            capture_output=True, text=True, cwd="App",
        ).stdout.strip().splitlines()[-1]
    finally:
        open(path, "w", encoding="utf-8").write(original)
    ok = f"{want} failed" in out
    bad += not ok
    print(("BITES " if ok else "NO BITE ") + name + ": " + out)
sys.exit(1 if bad else 0)
PYEOF
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest python3 /tmp/1163_bite.py 2>&1 | tail -30
```
Expected: nine lines, all `BITES` (`already_gone: 3 failed`, `retry_kinds: 2`, `map_1007: 4`, `map_offline: 2`, `list_1007: 2`, `new_pin: 2`, `clean_retry: 1`, `clean_gone: 1`, `audit_via: 1`), exit 0. Then `git diff --stat | tail -30` -> the same two source files as Step 2 (the script restores them; a `NO BITE` line means STOP). Re-run Step 3's command -> `37 passed`.

**Step 5. Docs.** Write both scripts and run them from the repo root (no output means success):
```bash
cat > /tmp/1163_plan.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

swap("docs/plans/ttlock-door-codes.md", '''- Every call's `date` must be within 5 minutes of TTLock's clock (`80000`).
''', '''- Every call's `date` must be within 5 minutes of TTLock's clock (`80000`).

### 3.1 Error table (TTLock official list K-DC-ERRCODE, owner 2026-10-26) and our kind

Kind = `ttlock.ERROR_KINDS`; an unlisted errcode is `transient`. What a kind does: `offline`, `transient`, `network`, `rate`, `budget` retry (a delete until `valid_to`); `code_missing` retries like them after one list call; `config`, `permission`, `reauth`, `disabled` stop at once with a host mail; `bug` is retried at most `ISSUE_MAX_ATTEMPTS` times, then handed over.

| Code | Meaning | Kind |
|---|---|---|
| 10003, 10004 | token missing / not authorized | auth |
| 10011 | refresh token invalid | reauth |
| 10007 | username or password wrong | login |
| 10000, 10001 | client id or secret wrong | config |
| 10005, 30001, -2018, 20002 | no permission / not lock admin | permission |
| 30006 / 30007 | call rate / monthly limit | rate / budget |
| 30008 | cross-region domain (cn vs eu): the server's `UBYHOST_TTLOCK_API_BASE` is wrong | config |
| 80000 | `date` off by over 5 minutes | clock |
| 80002 | invalid JSON format | bug |
| 90000, 1 | TTLock internal error, generic failure | transient |
| -3 | invalid parameter | bug |
| -1003 | lock does not exist | config |
| -2025 | lock frozen, cannot operate now | offline |
| -3011 | transfer lock to self (never called) | unmapped |
| -4043 | function not supported by this lock | config |
| -4063 | delete or transfer locks first (account delete) | config |
| -4067 | NB device not registered | config |
| -4082 | auto-lock period invalid (never called) | unmapped |
| -2012 | lock not connected to a gateway | offline |
| -3002 / -3003 | gateway offline / busy | offline |
| -3036 / -3037 | lock offline / busy | offline |
| -3035 | Wi-Fi lock in power-saving mode | offline |
| -3034 | network not configured | config |
| -4037 | no such gateway | config |
| -3016 | no meaning given | unmapped |
| -1007 | no password data of this lock: the passcode is not on the lock | code_missing |
| -2009, -2032, -3006, -3045 | invalid / too simple / not 6-9 digits / digits not supported | bug (-2032 first gets one new random PIN) |
| -3007 / -1026 | duplicate PIN / period already used | duplicate / period_taken |
| -3008 | passcode never used cannot be changed | unused_code |
| -4056, -3009 | lock storage full | storage |
| -1008, -1016, -1018, -1027, -2019, -2020, -2023, -3039, -3046, -4064 | eKey calls (only `/v3/key/list` is called) | unmapped |
| -1021, -1023 | IC card / fingerprint (never called) | unmapped |

`-1007` on a delete: the lock confirms with one list call (`code_is_listed`); only a fully read list without the id counts as revoked (audit detail `via=gone:-1007`). A list that itself answers `-1007` on page 1 is an empty list. Otherwise the delete is retried.
''')
PYEOF
cat > /tmp/1163_docs.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

swap("docs/TTLOCK.md", "| Retry with backoff (unmapped today, so `transient`) |\n| `-3036` | Lock offline | Retry with backoff (unmapped today, so `transient`) |\n",
     "| Retry with backoff (kind `offline`, no list lookup on a delete) |\n| `-3036`, `-3037`, `-3035`, `-2025` | Lock offline / busy, Wi-Fi lock power saving, lock frozen | Retry with backoff (kind `offline`) |\n| `-1007` | No password data of this lock: the passcode is not on the lock | Delete: one list call confirms it, then revoked (kind `code_missing`); a list answering `-1007` is an empty list |\n")
swap("docs/TTLOCK.md", "| `-1003`, `-2025`, `-4043`, `-4037`, `30008`, `-3006`, `-2032`, `-3045` | Lock missing, lock frozen, function not supported, gateway missing, wrong region host, passcode length, passcode too simple, unsupported digit | Permanent, but unmapped in `ERROR_KINDS`, so retried as `transient`. Known gap |",
     "| `-1003`, `-4043`, `-4037`, `-3034`, `-4067`, `-4063`, `30008` | Lock missing, function not supported, gateway missing, network not configured, NB device not registered, delete locks first, wrong region host | Kind `config`: no retry, host mail (`30008` is the server's API base setting) |\n| `-2009`, `-2032`, `-3006`, `-3045`, `80002` | Invalid passcode, too simple, length, unsupported digit, invalid JSON | Kind `bug`; `-2032` first gets one new random PIN. Full table: plan `ttlock-door-codes.md` 3.1 |")
PYEOF
python3 /tmp/1163_plan.py | tail -30
python3 /tmp/1163_docs.py | tail -30
```
Command: `git diff --stat docs | tail -30` -> `docs/TTLOCK.md` and `docs/plans/ttlock-door-codes.md` (about `46 insertions(+), 3 deletions(-)`). Then `grep -n "^### 3.1" docs/plans/ttlock-door-codes.md | tail -30` -> one line.

## 5. Do not touch

`App/app/mail_notify.py`, any i18n file, any migration, the Go tree, `docs/context/*`. Hard rules: privacy first (no new personal data; no new outbound request: the `-1007` lookup is the existing `listKeyboardPwd` call, 1 to 5 pages, same host and payload, only after a `-1007` or unmapped refusal of a delete); a cancelled guest must never keep a working PIN (the lookup confirmation stays); no dependency; SQL only through `db`.

## 6. Commands

From `App/` (Postgres on):
1. `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_ttlock_error_map.py -q --tb=short 2>&1 | tail -30` -> `37 passed`.
2. Test-map rows "Door codes, TTLock" and "Cleaning": `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_cleaning*.py -q --tb=short -x 2>&1 | tail -30` -> no failures (about 386 passed; browser files may skip).
3. `.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests tools 2>&1 | tail -30` -> `All checks passed!` (if `tools` does not exist under `App/`, drop it).
4. `.venv/bin/python -m pytest tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30` -> pass (docs only; no host copy was added, so the i18n tests are not needed).
From the repo root: `python3 scripts/context_lint.py | tail -3` -> `context lint: OK` (a WARN about `status.md` is the orchestrator's).

## 7. Acceptance

- [ ] `grep -c '"code_missing"' App/app/ttlock.py | tail -30` -> `1`; every code of the mapping in §2 is in `ERROR_KINDS` with its kind (the parametrized test).
- [ ] A delete answering `-1007` is revoked only when the lock's list was read in full without the id, and not revoked while the lock still lists it (`last_error` reads `code_missing`, row stays `revoke_pending`).
- [ ] An offline or busy answer is retried with `lookups == 0`, even when the lock would say "gone".
- [ ] `-2032` gets exactly one new PIN, then `bug`; `-3006` is raised after one call.
- [ ] Step 4 prints nine `BITES` lines.
- [ ] A cleaning delete answering `-1007` is retried while the lock lists the code, and `revoked` only when the full list lacks it.
- [ ] Commands 2 to 4 of §6 pass; `git diff --stat` shows only the files of §3.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found (a script prints an `AssertionError`);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1163-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/cleaning_codes.py`: `_already_gone` and the `_failure` retry set (a `-1007` must never mark a cleaning code deleted without the full list).
- `App/app/door_codes.py`: `_already_gone` (which errcodes may cost a lookup) and the `via` audit detail in `_revoke_one`.
- `App/app/ttlock.py`: `ERROR_KINDS` (each kind decides retry or stop), the `-1007` read in `_read_listing` (it also changes `codes_named` for cleaning), `NEW_PIN_ERRCODES` in `add_custom_code`.
- The open question in §2 about unused type-3 codes.

## Owner steps

1. After the PR is green, merge it with `scripts/merge-pr-on-green.sh` (it deploys by itself).
2. Optional, no deadline: ask TTLock support what `keyboardPwd/delete` and `listKeyboardPwd` answer for a type-3 code that was never typed on the lock (the open question in section 2).
