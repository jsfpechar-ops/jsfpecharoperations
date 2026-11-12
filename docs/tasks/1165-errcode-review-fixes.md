# 1165: fix the review findings of 1163 (B1 code_missing, M1 lock_setup kind, M2 -1007 on a list) (K-DC-ERRCODE)

Status: review
Depends on: 1163 (its code is in HEAD; this brief edits it) | Base commit: 14b69654 (HEAD of claude/zealous-maxwell-a7ub54, PR #947) | Branch: task/1165-errcode-review-fixes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Next: 1165b (host mail copy and docs) runs after this one.

## 1. Objective

A fresh review of 1163 found three defects. B1: a delete that timed out (the lock ran it) and then answered `-1007` with a lookup that failed leaves `last_error = code_missing`; if the stay then comes back, `_revive_one` calls that a definite refusal and shows a PIN that is gone from the lock. M1: five lock-side errcodes (`-3034`, `-4037`, `-4043`, `-1003`, `-4067`) became kind `config` in 1163 and now stop moves, deletes (a cancelled guest's PIN stays on the lock) and issues at once, where on main they were retried; they get a new kind `lock_setup` that retries slowly. M2: `-1007` on a list call was read as an empty list, which is no independent evidence after a delete said `-1007` and makes a second cleaning code; it becomes "unknown". The rule behind all three: never leave a cancelled guest with a working PIN, never show a guest a dead PIN, and tell the host when they must act.

## 2. Context

Rules: SQL only through `db` helpers; no dependency, no migration, no new state, no new endpoint, no new outbound request (the lookups are the 1155/1163 ones). Anchors are verbatim from HEAD; each script asserts every anchor exists exactly once and stops with an `AssertionError` if not (then STOP, §8). **Tests run on SQLite** (the default when `UBYHOST_DATABASE_URL` is not set): local Postgres is unreliable, CI runs Postgres. Do not set a Postgres URL.

**B1 sequence (the test pins it).** Delete 1 runs on the lock but times out (`last_error = network`). Delete 2 answers `-1007`; the confirming `code_is_listed` fails (`_lock_code_state` -> unknown), so the row stays `revoke_pending` with `last_error = code_missing`. The stay comes back (`_handle_cancellations` -> `_revive_one`). `code_missing` is not in `AMBIGUOUS_DELETE_ERRORS`, so `_delete_result_unknown` is False and `_keep_issued` runs with no lock call. Fix: add `ttlock.CODE_MISSING` to `AMBIGUOUS_DELETE_ERRORS`. The revive then asks the lock once (1 lookup) and re-issues through `_reissue_lost_pin`.

**The kind table after this brief** (`ttlock.ERROR_KINDS`; an unlisted errcode is `transient`):

| kind | errcodes | issue | delete (revoke) | move replace | clock check | cleaning |
|---|---|---|---|---|---|---|
| `lock_setup` (new) | -3034 -4037 -4043 -1003 -4067 | retry after 1 min, handed over after 2 tries with the host mail (as on main) | retry 1, 15, 60 min until `valid_to`, host mail `cancelled_not_deleted` at try 3, then `revoke_failed` (as `transient`) | retry every 60 min until the stay starts (the `moved_during_stay` mail then tells the host); no mail on each try | alert `door_code_clock`, next try in 7 days (right for -4043 "not supported") | retry 1, 5, 15, 60, 240 min, 5 tries, then `failed` / `revoke_failed` |
| `config` | 10000 10001 -4063 30008, missing account or password | hand over at once | `revoke_failed` at once | host mail, skipped from then on | alert, 7 days | `failed` at once |
| `code_missing` | -1007 | as `transient` | one list call, `revoked` only if the whole list lacks the id; else retry; now also leaves a delete's result open (B1) | as `transient` | as `transient` | same as delete |
| `offline`, `transient`, `network`, `rate`, `budget` | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged |

**M2 decision.** `ttlock._read_listing` (the loop under `code_is_listed` and `codes_named`) returns `None` ("unknown") on `-1007` on any page, never an empty list. Cost, accepted: a lock with no codes at all that answers `-1007` makes a delete confirmation unknown, so the delete retries and ends `revoke_failed` with the host mail (the safe side). A cleaning `_find` that gets `None` already raises `transient` (no second code). `find_code_by_name` (door issue retry) still raises the `-1007` as before.

**Stale failures.** A `config:*` or `lock_setup:*` `last_error` on an issued row comes only from a failed move replace. A successful move replace and a re-issue already write `last_error = NULL`. New: when the stay is back on the code's own window (`valid_from` and `valid_to` equal the wanted window) the stale failure is cleared, so the row is not left with a dead error. (The 0037 rule that skips `config` rows from then on is unchanged; it is an account-level kind.)

Anchors (in the scripts): `door_codes.py` `AMBIGUOUS_DELETE_ERRORS`, `GATEWAY_RETRY_KINDS`, `delay = 60 if kind == "budget" else 15`, the `_handle_moves` window-equal `continue`; `ttlock.py` the `ERROR_KINDS` block from `# The host (or the server's region setting)` and `CODE_MISSING = "code_missing"`, the `_read_listing` docstring tail and its `except TTLockError as exc:` body; `cleaning_codes.py` the `_failure` kind set; the tests' `NEW_CODES` lines and the three 1163 `-1007` list tests.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | `AMBIGUOUS_DELETE_ERRORS` gains `code_missing`; `lock_setup` joins `GATEWAY_RETRY_KINDS`; move retry 60 min for it; stale move failure cleared |
| App/app/ttlock.py | edit | kind `lock_setup` for five codes, `LOCK_SETUP` constant; `-1007` on a list is unknown |
| App/app/cleaning_codes.py | edit | `_failure` retries `lock_setup` |
| App/tests/test_door_code_ambiguous_delete.py | edit | B1 sequence test (appended) |
| App/tests/test_ttlock_error_map.py | edit | map table, three `-1007` list tests rewritten, cleaning tests, `lock_setup` delete and cleaning tests |
| App/tests/test_ttlock_lock_setup.py | create | issue, move, stale clear, clock check tests |
| docs/tasks/1165-report.md | create | report (§9) |

1165b (mail copy, docs) edits `test_ttlock_lock_setup.py` after this brief; 1165 goes first. No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Run `grep -c "CODE_MISSING" App/app/ttlock.py | tail -30` (expected `2`) and `grep -c "LOCK_SETUP" App/app/ttlock.py | tail -30` (expected `0`, else STOP). Then `git switch -c task/1165-errcode-review-fixes | tail -30`; expected `Switched to a new branch`.

**Step 2. Code (B1, M1, M2).** Write the script to `/tmp/1165_code.py` (the heredoc ends at the line `PYEOF`), then run it from the repo root with `python3 /tmp/1165_code.py | tail -30` (no output means success):
```bash
cat > /tmp/1165_code.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

DC = "App/app/door_codes.py"
TT = "App/app/ttlock.py"

# B1: code_missing leaves a delete's result open.
swap(DC, '''# (stored as lookup_failed:<n>; _delete_result_unknown reads it).
AMBIGUOUS_DELETE_ERRORS = ("", "network", "transient", LOOKUP_FAILED)''', '''# (stored as lookup_failed:<n>; _delete_result_unknown reads it), or code_missing (-1007: the
# code is not on the lock, which an earlier delete that timed out may have caused, and the
# confirming lookup could not say).
AMBIGUOUS_DELETE_ERRORS = ("", "network", "transient", LOOKUP_FAILED, ttlock.CODE_MISSING)''')

# M1: lock_setup retries like a transient answer, slowly.
swap(DC, 'GATEWAY_RETRY_KINDS = ("offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING)', '''GATEWAY_RETRY_KINDS = (
    "offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING, ttlock.LOCK_SETUP,
)''')
swap(DC, '                delay = 60 if kind == "budget" else 15\n',
        '                delay = 60 if kind in ("budget", ttlock.LOCK_SETUP) else 15\n')
swap(DC, '''        if row["valid_from"] and row["valid_to"]:
            if _iso_to_ms(row["valid_from"]) == start_ms and _iso_to_ms(row["valid_to"]) == end_ms:
                continue
''', '''        if row["valid_from"] and row["valid_to"]:
            if _iso_to_ms(row["valid_from"]) == start_ms and _iso_to_ms(row["valid_to"]) == end_ms:
                if (row["last_error"] or "").startswith(("lock_setup", "config")):
                    # The stay is back on the code's own window: an old move failure is stale.
                    db.execute(
                        "UPDATE door_code SET last_error = NULL, next_attempt_at = NULL, "
                        "updated_at = ? WHERE id = ? AND state = ?",
                        (now_iso, row["id"], ISSUED),
                    )
                continue
''')
swap("App/app/cleaning_codes.py",
     '{"offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING}',
     '{"offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING, ttlock.LOCK_SETUP}')

swap(TT, '''    # The host (or the server's region setting) must fix the setup: no retry.
    -1003: "config",
    -4037: "config",
    -4043: "config",
    -3034: "config",
    -4067: "config",
    -4063: "config",
    30008: "config",
''', '''    # The lock's own setup is missing (no gateway, network, NB registration, lock not found,
    # function not supported). The host can fix it later, so it is retried slowly like a
    # transient answer, and a failure is handed to the host at the usual threshold.
    -1003: "lock_setup",
    -4037: "lock_setup",
    -4043: "lock_setup",
    -3034: "lock_setup",
    -4067: "lock_setup",
    # The account or the server's region setting is wrong: no retry, the host or operator fixes it.
    -4063: "config",
    30008: "config",
''')
swap(TT, 'CODE_MISSING = "code_missing"\n', 'CODE_MISSING = "code_missing"\nLOCK_SETUP = "lock_setup"\n')

# M2: -1007 on a list call is unknown, never empty.
swap(TT, '''    raised as they are, except -1007 ("No password data of this lock") on page 1: the lock
    has no codes at all, an empty list (the kept entries are then none).
    """''', '''    raised as they are, except -1007 ("No password data of this lock") on any page: that is
    not evidence about one code (a delete just answered it too), so the list is unknown (None),
    never empty.
    """''')
swap(TT, '''            if exc.code == NO_PASSCODE_DATA and page == 1:
                return kept
            raise''', '''            if exc.code == NO_PASSCODE_DATA:
                return None
            raise''')
PYEOF
```

**Step 3. Test file.** Create `App/tests/test_ttlock_lock_setup.py` with exactly this (the heredoc ends at the line `TESTEOF`), then run `wc -l App/tests/test_ttlock_lock_setup.py | tail -30`; expected about 160 lines:
```bash
cat > App/tests/test_ttlock_lock_setup.py <<'TESTEOF'
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

TESTEOF
```

**Step 4. Test edits.** Write the script to `/tmp/1165_tests.py` (ends at `PYEOF`), run it from the repo root with `python3 /tmp/1165_tests.py | tail -30` (no output means success). It appends the B1 test and the cleaning tests, and rewrites the 1163 `-1007` list tests (they pinned "page 1 = empty", which is now wrong):
```bash
cat > /tmp/1165_tests.py <<'PYEOF'
def swap(path, old, new):
    s = open(path, encoding="utf-8").read()
    assert s.count(old) == 1, (path, old[:70])
    open(path, "w", encoding="utf-8").write(s.replace(old, new))

EM = "App/tests/test_ttlock_error_map.py"
AM = "App/tests/test_door_code_ambiguous_delete.py"

# B1 test (appended).
with open(AM, "a", encoding="utf-8") as f:
    f.write('''

def test_a_minus_1007_after_a_timed_out_delete_with_an_unconfirmed_lookup_still_re_issues(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)  # delete 1 ran on the lock, the answer was lost
    assert _row(row)["last_error"] == "network" and lock.pins == {}
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")

    def refuse(*a, **k):
        raise ttlock.TTLockError("no password data", code=-1007, kind=ttlock.CODE_MISSING)

    monkeypatch.setattr(ttlock, "delete_code", refuse)  # delete 2: -1007, confirmation fails
    door_codes._revoke_one(row)
    held = _row(row)
    assert held["state"] == door_codes.REVOKE_PENDING and held["last_error"] == "code_missing"
    assert lock.lookups == 1
    lock.lookups = 0
    lock.lookup_error = None
    _revive(stay)
    _tick()
    _assert_new_working_pin(lock, row, sent)
    assert lock.lookups == 1
''')

swap(EM, "from __future__ import annotations\n\nimport pytest",
     "from __future__ import annotations\n\nfrom datetime import datetime, timedelta, timezone\n\nimport pytest")
swap(EM, '''    (-1003, "config"), (-4037, "config"), (-4043, "config"), (-3034, "config"),
    (-4067, "config"), (-4063, "config"), (30008, "config"),''', '''    (-1003, "lock_setup"), (-4037, "lock_setup"), (-4043, "lock_setup"), (-3034, "lock_setup"),
    (-4067, "lock_setup"), (-4063, "config"), (30008, "config"),''')
# M2 tests: -1007 on a list is unknown, never empty.
swap(EM, '''def test_minus_1007_on_the_list_too_means_the_lock_has_no_codes(world, monkeypatch):
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


''', '''def test_minus_1007_on_the_list_after_a_delete_that_said_it_too_is_unknown_not_gone(world, monkeypatch):
    lock, stay, row, notices = world
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-1007))
    monkeypatch.setattr(ttlock, "code_is_listed", REAL_CODE_IS_LISTED)
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: _refuse(-1007)())
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKE_PENDING and after["last_error"] == "code_missing"
    assert after["pin_enc"] is not None and notices == []


def test_a_list_answering_minus_1007_on_any_page_is_unknown_never_empty(monkeypatch):
    pages = []

    def call(account_id, path, data, priority):
        pages.append(data["pageNo"])
        if data["pageNo"] == 1:
            return {"list": [{"keyboardPwdId": str(n), "keyboardPwdName": "UH-1"} for n in range(20)]}
        return _refuse(-1007)()

    monkeypatch.setattr(ttlock, "_call", call)
    assert ttlock.code_is_listed(1, "9", "UH-1", "99") is None and pages == [1, 2]
    monkeypatch.setattr(ttlock, "_call", lambda *a, **k: _refuse(-1007)())
    assert ttlock.code_is_listed(1, "9", "UH-1", "99") is None
    assert ttlock.codes_named(1, "9", "UH Cleaning abc") is None


def test_a_cleaning_issue_retry_whose_list_answers_minus_1007_adds_no_second_code(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "retrying", 1)
    _own(lock, row)
    real = lock.call

    def call(account_id, path, data, priority):
        if path == "/v3/lock/listKeyboardPwd":
            return _refuse(-1007)()
        return real(account_id, path, data, priority)

    monkeypatch.setattr(ttlock, "_call", call)
    cleaning_codes.process_queue()
    after = _clean_row(job)
    assert after["state"] == "retrying" and lock.added == 0 and after["last_error"] == "transient"


''')
# Appended: the cleaning unknown-lookup test (Low) and the M1 behaviour tests.
with open(EM, "a", encoding="utf-8") as f:
    f.write('''

def test_a_cleaning_delete_answering_minus_1007_with_an_unknown_lookup_is_not_counted_deleted(workspace, lock, monkeypatch):
    job, row = _queued(workspace, monkeypatch, "revoke_pending", 1)
    _own(lock, row)
    monkeypatch.setattr(ttlock, "code_is_listed", lambda *a, **k: None)  # the list could not be read in full
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-1007))
    cleaning_codes.process_queue()
    after = _clean_row(job)
    assert after["state"] == "revoke_pending" and after["pin_enc"] is not None
    assert after["last_error"] == "code_missing"
''')
    f.write('''

@pytest.mark.parametrize("code", [-3034, -4037, -4043, -1003, -4067])
def test_a_lock_setup_answer_on_delete_is_retried_to_the_end_with_no_lookup_and_a_host_mail_at_try_three(world, monkeypatch, code):
    lock, stay, row, notices = world
    lock.pins.clear()  # a lookup would say "gone": it must not even be asked
    monkeypatch.setattr(ttlock, "delete_code", _refuse(code))
    for attempt in (1, 2, 3):
        db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
        door_codes._revoke_one(row)
        after = _row(row)
        assert after["state"] == door_codes.REVOKE_PENDING and after["last_error"] == "lock_setup"
        assert notices == (["cancelled_not_deleted"] if attempt == 3 else [])
    wait = datetime.fromisoformat(after["next_attempt_at"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=55) < wait <= timedelta(minutes=60) and lock.lookups == 0
    db.execute("UPDATE door_code SET valid_to = ?, next_attempt_at = NULL WHERE id = ?", ("2000-01-01T00:00:00+00:00", row))
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_FAILED


def test_a_config_answer_on_delete_still_ends_revoke_failed_at_once(world, monkeypatch):
    lock, stay, row, notices = world
    monkeypatch.setattr(ttlock, "delete_code", _refuse(-4063))
    door_codes._revoke_one(row)
    assert _row(row)["state"] == door_codes.REVOKE_FAILED and notices == ["cancelled_not_deleted"]


@pytest.mark.parametrize("revoking", [False, True])
def test_a_lock_setup_answer_on_a_cleaning_code_is_retried_not_failed(workspace, lock, monkeypatch, revoking):
    job, row = _queued(workspace, monkeypatch, "revoke_pending" if revoking else "pending", 0)
    _own(lock, row)

    def call(account_id, path, data, priority):
        if path in ("/v3/keyboardPwd/add", "/v3/keyboardPwd/delete"):
            return _refuse(-3034)()
        return lock.call(account_id, path, data, priority)

    monkeypatch.setattr(ttlock, "_call", call)
    cleaning_codes.process_queue()
    after = _clean_row(job)
    assert after["state"] == ("revoke_pending" if revoking else "retrying")
    assert after["last_error"] == "lock_setup" and after["pin_enc"] is not None
''')
PYEOF
```
Then, from `App/`: `.venv/bin/python -m pytest tests/test_ttlock_lock_setup.py tests/test_ttlock_error_map.py tests/test_door_code_ambiguous_delete.py -q --tb=short 2>&1 | tail -30`; expected `70 passed`.

**Step 5. Revert-bite.** Write the script to `/tmp/1165_bite.py` (ends at `PYEOF`), run it from `App/` with `python3 /tmp/1165_bite.py | tail -30`. Each case puts one old behaviour back, runs the three test files and restores the file. Expected: eight lines starting `BITES` and none starting `NO BITE`. Afterwards `git diff --stat | tail -30` must be the same as before this step.
```bash
cat > /tmp/1165_bite.py <<'PYEOF'
import subprocess

TESTS = [
    "tests/test_ttlock_lock_setup.py",
    "tests/test_ttlock_error_map.py",
    "tests/test_door_code_ambiguous_delete.py",
]
CASES = [
    ("B1 code_missing ambiguous", "app/door_codes.py", "LOOKUP_FAILED, ttlock.CODE_MISSING)", "LOOKUP_FAILED)"),
    ("M1 map -3034 back to config", "app/ttlock.py", '    -3034: "lock_setup",', '    -3034: "config",'),
    ("M1 delete retry set", "app/door_codes.py", "ttlock.CODE_MISSING, ttlock.LOCK_SETUP,\n)", "ttlock.CODE_MISSING,\n)"),
    ("M1 move delay 60", "app/door_codes.py",
     'delay = 60 if kind in ("budget", ttlock.LOCK_SETUP) else 15', 'delay = 60 if kind == "budget" else 15'),
    ("M1 stale failure cleared", "app/door_codes.py",
     'startswith(("lock_setup", "config")):', 'startswith(("zzz",)):'),
    ("M1 cleaning retry set", "app/cleaning_codes.py", "ttlock.CODE_MISSING, ttlock.LOCK_SETUP}", "ttlock.CODE_MISSING}"),
    ("M2 -1007 on a list is unknown", "app/ttlock.py",
     "            if exc.code == NO_PASSCODE_DATA:\n                return None",
     "            if exc.code == NO_PASSCODE_DATA and page == 1:\n                return kept"),
    ("Low cleaning _already_gone is False", "app/cleaning_codes.py", ") is False\n", ") is not True\n"),
]
for label, path, old, new in CASES:
    text = open(path, encoding="utf-8").read()
    assert text.count(old) == 1, (label, old)
    try:
        open(path, "w", encoding="utf-8").write(text.replace(old, new))
        out = subprocess.run(
            [".venv/bin/python", "-m", "pytest", *TESTS, "-q", "--tb=no", "-p", "no:cacheprovider"],
            capture_output=True, text=True,
        ).stdout
    finally:
        open(path, "w", encoding="utf-8").write(text)
    failed = [line for line in out.splitlines() if line.startswith("FAILED")]
    print("BITES" if failed else "NO BITE", len(failed), label)
PYEOF
```

## 5. Do not touch

`ttlock._call`, `ttlock.ALLOWED_PATHS`, the 1155/1155b/1164 code, `mail_notify.py` and the i18n files (1165b), any migration, any template or CSS. Hard rules: SQL only through `db`, no new dependency, no host copy in this brief.

## 6. Commands

From `App/` (SQLite; do not set a Postgres URL):
1. `.venv/bin/python -m pytest tests/test_ttlock_lock_setup.py tests/test_ttlock_error_map.py tests/test_door_code_ambiguous_delete.py -q --tb=short 2>&1 | tail -30` -> `70 passed`.
2. Test-map rows "Door codes, TTLock" and "Cleaning": `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_cleaning*.py -q --tb=short -x 2>&1 | tail -30` -> no failures (about `417 passed`; browser files may skip when `playwright` is not installed; this brief touches no template or CSS).
3. `.venv/bin/python -m ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30` -> `All checks passed!`.
4. `git status --short | tail -30`: if a stray untracked file `App/config` (22 bytes, a test artifact) shows, delete it with `rm App/config`; nothing else may be untracked except the new test file and the report.
From the repo root: `python3 scripts/context_lint.py | tail -3` -> `context lint: OK` (a WARN about overlapping open briefs on `test_ttlock_lock_setup.py` is expected: 1165 goes first).

## 7. Acceptance

- [ ] Step 5 prints eight `BITES` lines.
- [ ] The B1 test (`test_a_minus_1007_after_a_timed_out_delete_with_an_unconfirmed_lookup_still_re_issues`) passes, and fails with `LOOKUP_FAILED)` as the only member of `AMBIGUOUS_DELETE_ERRORS` (step 5, case 1).
- [ ] `-3034 -4037 -4043 -1003 -4067` map to `lock_setup`, `-4063` and `30008` to `config` (the parametrized map test).
- [ ] A `lock_setup` delete is retried with `lookups == 0`, mailed once at try 3, `revoke_failed` only past `valid_to`; a `config` delete is `revoke_failed` at once.
- [ ] A `lock_setup` issue is `retrying` after the first try and `failed` after the second; a `config` issue is `failed` at once.
- [ ] A `lock_setup` move waits about 60 minutes, sends no mail, and a later success clears `last_error`.
- [ ] A list answering `-1007` is `None` from `code_is_listed` and `codes_named`; a cleaning issue retry adds no second code; a cleaning delete with an unknown lookup is not counted deleted.
- [ ] Commands 1 to 4 of §6 pass; `git diff --stat` shows only the files of §3.

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

Write `docs/tasks/1165-report.md` (600 tokens at most) and set `Status: review` at the top of this brief. The report has: 1. `git diff --stat`. 2. Each command with the last 5 lines of its output (the step 5 lines in full). 3. §7 ticked. 4. Deviations. 5. Questions. 6. Owner steps left.

## Risk list (for the reviewer)

`door_codes.py` diff (`_handle_moves` stale clear, `GATEWAY_RETRY_KINDS`, `AMBIGUOUS_DELETE_ERRORS`), `ttlock.py` `_read_listing` and `ERROR_KINDS`. Cost to accept: a lock with no codes answering `-1007` makes a delete end `revoke_failed` with the host mail. Not covered here: Postgres (CI runs it). Known issue for the orchestrator (not this brief): the 1164 recovered batch on a manual or inactive apartment keeps `retried_at` NULL, and if the apartment later becomes active and automatic, `_retry_outcome_unknown_batches` resends it once however old.

## Owner steps

1. Open the PR for `task/1165-errcode-review-fixes` after 1165b is also done, keep it a draft until then.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>` once CI (Postgres) is green.
