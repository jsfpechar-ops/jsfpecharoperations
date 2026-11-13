# 1173: the door-code issue queue cannot be starved by rows that never get issued

Status: review
Depends on: 1181 (merged in the base) | Base commit: claude/zealous-maxwell-a7ub54 HEAD (8f1b54cd) | Branch: task/1173-issue-queue-starvation
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 25 calls used; 1173b is the follow-up and must not be started in this chat)

## 1. Objective

A pending or retrying door-code row that `issue()` cannot issue (`not_eligible`, `no_account`, `bad_window`) is put back to `pending` with no new `next_attempt_at`, so `_issue_due` takes it again on every tick; 20 such rows (`BATCH`) block every newer row app-wide. Fix: those releases wait a backoff, a stay that has ended expires, and rows never tried come before rows that keep failing.

## 2. Context

Rules: rule 5 (SQL through `db` helpers, portable on SQLite and PostgreSQL), no new dependency, no migration. Tests run on SQLite and on the local PostgreSQL 16 (`UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest`).

**The bug (reproduced on SQLite with `BATCH = 3`, pre-existing, review finding F1).** `issue()` claims a row (`attempts + 1`), then releases it through `_release_issue_claim(..., decrement_attempt=True, reason=...)` for `not_eligible`, `no_account`, `bad_window`. The release sets state `pending`, takes the attempt back and keeps `next_attempt_at`, so the row stays due. `_issue_due` orders the due rows by `next_attempt_at` (oldest first), so the oldest stuck rows come first for ever and a newer healthy row is never reached. A stay whose last day has passed is also "not eligible" (`_eligible_sql` needs `r.date_to >= today`), so it never reaches the `end_ms < now` branch of `issue()` that would expire it: it is stuck for good.

**Decisions (the brief owns them; do not change them).**

| Topic | Decision | Why |
|---|---|---|
| Backoff `not_eligible` | 15 min | Eligibility has no start time, so there is no moment to wait for. It ends when an operator pause ends or the host fixes the stay, at an unknown time, and a guest may be waiting. Test `test_operator_pause_keeps_the_row_pending_until_the_plan_is_back` shows that case. |
| Backoff `no_account` | 15 min | The host must reconnect TTLock; nothing resets the row when they do, so a long wait would delay a waiting guest. Same as the move retry (15). |
| Backoff `bad_window` | 60 min | The saved hours are invalid and need a host edit; the UI validates 0 to 23, so this is a rare data fault. |
| Cost of 15 min | 4 cheap tries per hour per stuck row, no lock call (the release comes before any TTLock call). With the order below the batch still reaches new rows. | |
| Expiry | `_expire_ended_stays`, first phase of `reconcile`: `pending`/`retrying` rows whose reservation is active, not archived and has `date_to < local date` become `expired`. Not `valid_to`: `_reissue_lost_pin` keeps the old window's `valid_to` on a pending row while the stay may have been extended, so `valid_to` would expire a live stay. Cancelled or archived stays stay with `_handle_cancellations` (`revoked`). | |
| Order | `ORDER BY (attempts > 0), (next_attempt_at IS NOT NULL), next_attempt_at, id`. Rows never tried (attempts 0) first, then NULL `next_attempt_at` (1181), then oldest, then id. `(expr)` is a boolean on PostgreSQL and 0/1 on SQLite; false sorts first on both. | `ensure_row` inserts a new row with `next_attempt_at = now`, not NULL, so without the `attempts` key a new row sorted after every older retry (the review's F2). A row that failed has `attempts >= 1`; a released row has `attempts` 0 but is now put off by its backoff. |
| Revoke batch (`_handle_cancellations`, due query ~1170) | **Checked, no change.** Its rows are `revoke_pending` rows of cancelled stays. `_revoke_one` ends every try in `revoked`, `revoke_failed`, or a retry that sets `next_attempt_at` (1, 15, 60 min); a row skipped by the lease (2 min) is the only one left due and it clears itself. The `_stay_is_live` branch is a race: the due query excludes live stays. No row goes back with an unchanged `next_attempt_at`. | |

**State machine.** `TRANSITIONS` had no `pending -> expired` or `retrying -> expired`. Added here, pinned in `App/tests/test_sm_door_code_state.py` (`PINNED`) and mirrored in `go/internal/statemachine/tables.go`; `App/tests/test_sm_go_parity.py` fails if they differ.

**Existing tests that change.** `test_operator_pause_keeps_the_row_pending_until_the_plan_is_back` now sees the 15-minute backoff, so it clears `next_attempt_at` before the second `_issue_due` ("time passes"). `test_null_order_portability.py` is rewritten for the review's F2: the old docstring said a new row has NULL `next_attempt_at`, but `ensure_row` sets it to now. NULL belongs to re-issue rows (`pin_lost`) and rows whose time was cleared. Its competing rows are now "released rows whose backoff ended" (attempts 0), because with the new `attempts` key retries with `attempts = 1` would no longer compete with a NULL row, and the PostgreSQL bite of the 1181 fix would stop biting.

**Anchors.** Each `sub(old, new)` in the scripts asserts that `old` occurs exactly once. If the assertion fails, STOP (section 8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | `TRANSITIONS`, `RELEASE_RETRY_MINUTES`, `_release_issue_claim`, `_issue_due` order, `_expire_ended_stays`, `reconcile` |
| App/tests/test_sm_door_code_state.py | edit | one `PINNED` line |
| go/internal/statemachine/tables.go | edit | `pending` and `retrying` get `expired` |
| App/tests/test_door_code_lost_pin.py | edit | the operator-pause test clears the backoff |
| App/tests/test_null_order_portability.py | overwrite | F2: real states, new order |
| App/tests/test_issue_queue_starvation.py | create | 4 test functions (6 cases): starvation, backoff, order, expiry |
| docs/tasks/1173-report.md | create | report (section 9) |

No other file may change. (The card work, finding F4, and the docstring renumbers are brief 1173b.)

## 4. Steps

All commands run from the repo root unless a step says `cd App`. End the commit message with the attribution lines your session gives you. Never use `git rebase`, `git commit --amend`, `git stash` or `git commit -a`; `git add` only the named files.

1. Preflight and branch. Expect `8f1b54cd` or a later commit that contains it, an empty status, and 1 line from the grep.
```bash
git log -1 --format=%h | tail -3; git status --short | tail -5; grep -c 'ORDER BY (next_attempt_at IS NOT NULL), next_attempt_at LIMIT' App/app/door_codes.py; git checkout -b task/1173-issue-queue-starvation | tail -3
```
2. Edit `App/app/door_codes.py` (six anchors). Expect `ok App/app/door_codes.py`.
```bash
python3 - <<'PY'
p = "App/app/door_codes.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''    PENDING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
    },
    RETRYING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
    },''',
r'''    PENDING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
        EXPIRED,  # _expire_ended_stays: the stay ended before a code was made
    },
    RETRYING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
        EXPIRED,  # _expire_ended_stays: the stay ended before a code was made
    },''',
)

sub(
r'''DELAY_MINUTES = 5
BATCH = 20
''',
r'''DELAY_MINUTES = 5
BATCH = 20
# 1173: issue() puts a row back to pending for these reasons without a try on the lock. The row waits this
# long before _issue_due takes it again, so a stuck row cannot fill the batch every tick.
# not_eligible: the stay or property no longer qualifies (no start time to wait for: eligibility has none).
#   Short, because an operator pause or a host fix ends it at an unknown moment while a guest waits.
# no_account: the host must reconnect TTLock; nothing resets the row then, so keep it short too.
# bad_window: the saved hours are invalid and need a host edit; the UI does not allow it, so long.
RELEASE_RETRY_MINUTES = {"not_eligible": 15, "no_account": 15, "bad_window": 60}
''',
)

sub(
r'''    """Put a row back to pending. ``reason`` is kept so a stuck code says why."""
    if decrement_attempt:
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = attempts - 1, "
            "last_error = COALESCE(?, last_error), updated_at = ? WHERE id = ? AND attempts > 0",
            (PENDING, reason, db.utcnow(), door_code_id),
        )
    else:
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, "
            "last_error = COALESCE(?, last_error), updated_at = ? WHERE id = ?",
            (PENDING, reason, db.utcnow(), door_code_id),
        )
''',
r'''    """Put a row back to pending. ``reason`` is kept so a stuck code says why.

    A reason in RELEASE_RETRY_MINUTES also moves next_attempt_at forward (1173): without it the row
    stays due and _issue_due takes it again on every tick, so 20 such rows block every newer row.
    """
    now = db.utcnow()
    minutes = RELEASE_RETRY_MINUTES.get(reason or "")
    next_at = _iso(_now() + timedelta(minutes=minutes)) if minutes else None
    if decrement_attempt:
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = attempts - 1, "
            "last_error = COALESCE(?, last_error), next_attempt_at = COALESCE(?, next_attempt_at), "
            "updated_at = ? WHERE id = ? AND attempts > 0",
            (PENDING, reason, next_at, now, door_code_id),
        )
    else:
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, "
            "last_error = COALESCE(?, last_error), next_attempt_at = COALESCE(?, next_attempt_at), "
            "updated_at = ? WHERE id = ?",
            (PENDING, reason, next_at, now, door_code_id),
        )
''',
)

sub(
r'''        "ORDER BY (next_attempt_at IS NOT NULL), next_attempt_at LIMIT ?",''',
r'''        "ORDER BY (attempts > 0), (next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",''',
)

sub(
r'''def reconcile() -> Dict[str, int]:''',
r'''def _expire_ended_stays(now_iso: str) -> int:
    """pending/retrying rows of a stay that has ended become expired (1173).

    issue() expires such a row only when it gets as far as the window check, but a stay whose last day
    is past is not eligible any more, so issue() put it back to pending on every tick. The test is the
    one _eligible_sql uses (date_to before the local date). valid_to is not used: a re-issue row
    (pin_lost) keeps the old window's valid_to while the stay may have been extended since.
    Cancelled or archived stays are left to _handle_cancellations (revoked).
    """
    today = deadlines.local_now().date().isoformat()
    return int(
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? "
            "WHERE state IN (?, ?) AND claimed_at IS NULL AND reservation_id IN "
            "(SELECT id FROM reservation WHERE status = 'active' AND archived_at IS NULL AND date_to < ?)",
            (EXPIRED, now_iso, PENDING, RETRYING, today),
        )
        or 0
    )


def reconcile() -> Dict[str, int]:''',
)

sub(
r'''    now_iso = db.utcnow()

    # Issuing comes first: a guest is waiting on it''',
r'''    now_iso = db.utcnow()

    ended = _phase("expire_ended", _expire_ended_stays, now_iso)
    counts["expired"] += int(ended or 0)

    # Issuing comes first: a guest is waiting on it''',
)

sub(
r'''    counts["expired"] = int(expired or 0)
''',
r'''    counts["expired"] += int(expired or 0)
''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
3. Pin the new move in the state-machine test. Expect `ok App/tests/test_sm_door_code_state.py`.
```bash
python3 - <<'PY'
p = "App/tests/test_sm_door_code_state.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''    ("reconcile", ("issued",), ("issued",), ("expired",)),
]''',
r'''    ("reconcile", ("issued",), ("issued",), ("expired",)),
    ("_expire_ended_stays", ("pending", "retrying"), ("pending", "retrying"), ("expired",)),
]''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
4. Mirror it in Go. Expect `ok go/internal/statemachine/tables.go`.
```bash
python3 - <<'PY'
p = "go/internal/statemachine/tables.go"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''		"pending":        {"issuing", "revoked"},
		"retrying":       {"issuing", "revoked"},
''',
r'''		"pending":        {"expired", "issuing", "revoked"},
		"retrying":       {"expired", "issuing", "revoked"},
''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
5. The operator-pause test lets time pass. Expect `ok App/tests/test_door_code_lost_pin.py`.
```bash
python3 - <<'PY'
p = "App/tests/test_door_code_lost_pin.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

sub(
r'''    assert lock.made == 0
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    door_codes._issue_due(db.utcnow())
    back = _row(row)''',
r'''    assert lock.made == 0
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    # 1173: the paused row waits its backoff (15 minutes) so it cannot starve other rows; time passes.
    assert _row(row)["next_attempt_at"] is not None
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
    door_codes._issue_due(db.utcnow())
    back = _row(row)''',
)

open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
6. Overwrite `App/tests/test_null_order_portability.py`. The guard stops the step if the file is not the 1181 version. Expect `written`.
```bash
head -1 App/tests/test_null_order_portability.py | grep -q "A new row (NULL next_attempt_at)" || { echo "STOP: not the 1181 file"; exit 1; }
cat > App/tests/test_null_order_portability.py <<'EOF'
"""A due row with NULL next_attempt_at is taken before other due rows on SQLite and PostgreSQL (task 1181).

SQLite sorts NULL first ascending, PostgreSQL sorts it last. Every due-row query that has a LIMIT must say
which it wants. Which rows have NULL: a re-issue row (_reissue_lost_pin sets state pending, last_error
pin_lost, attempts 0, next_attempt_at NULL) and a row whose retry time was cleared. A brand-new row
(ensure_row) has next_attempt_at = now, not NULL; task 1173 (test_issue_queue_starvation.py) covers its order.
"""
from __future__ import annotations

import re

from app import db, door_codes
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401


def _released(stay: int, minute: int) -> int:
    """A row put back by issue() whose backoff has ended: attempts 0, next_attempt_at in the past."""
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ? WHERE id = ?",
        (door_codes.PENDING, f"2000-01-01T00:{minute:02d}:00+00:00", row_id),
    )
    return row_id


def _seed_due_rows_and_one_pin_lost(count: int) -> int:
    for _ in range(count):
        _, _, stay = _stay(registered_minutes_ago=5)
        _released(stay, minute=1)
    _, _, stay = _stay(registered_minutes_ago=1)
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 0, last_error = 'pin_lost', next_attempt_at = NULL "
        "WHERE id = ?",
        (door_codes.PENDING, row_id),
    )
    return row_id


def test_issue_due_takes_a_pin_lost_row_before_other_due_rows(monkeypatch):
    monkeypatch.setattr(door_codes, "BATCH", 3)
    new_id = _seed_due_rows_and_one_pin_lost(5)
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert len(seen) == 3
    assert new_id in seen  # fails on PostgreSQL with the old ORDER BY (NULL last)


def test_due_queries_put_null_next_attempt_first(monkeypatch):
    """Backend independent: the generated SQL itself names the NULL order, so SQLite catches a revert too."""
    sql_seen = []
    real = db.query

    def spy(sql, params=()):
        sql_seen.append(sql)
        return real(sql, params)

    monkeypatch.setattr(db, "query", spy)
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: True)
    monkeypatch.setattr(door_codes, "_revoke_one", lambda rid: None)
    door_codes._issue_due(db.utcnow())
    door_codes.reconcile()
    ordered = [s for s in sql_seen if "next_attempt_at" in s and "ORDER BY" in s and "LIMIT" in s]
    assert len(ordered) >= 2, sql_seen
    for sql in ordered:
        assert re.search(
            r"ORDER BY (\(attempts > 0\), )?\((\w+\.)?next_attempt_at IS NOT NULL\), (\w+\.)?next_attempt_at", sql
        ), sql
EOF
echo written
```
7. Create `App/tests/test_issue_queue_starvation.py`. Expect `written`.
```bash
cat > App/tests/test_issue_queue_starvation.py <<'EOF'
"""Task 1173: rows that cannot be issued never starve newer rows; ended stays expire.

issue() puts a row back to pending for not_eligible, no_account and bad_window without a try on the lock.
Before 1173 such a row stayed due and was taken again on every tick, so BATCH of them blocked every newer row.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db, deadlines, door_codes, ttlock
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401

OLD = "2000-01-01T00:00:00+00:00"


def _stuck(reason: str) -> int:
    """A pending row that issue() cannot issue for ``reason``; due long ago, never tried."""
    owner, apartment, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    if reason == "not_eligible":
        db.execute("UPDATE reservation SET registration_completed_at = NULL WHERE id = ?", (stay,))
    elif reason == "no_account":
        db.execute("UPDATE lock_account SET status = 'error' WHERE owner_user_id = ?", (owner,))
    else:
        db.execute("UPDATE apartment SET checkin_hour = 99 WHERE id = ?", (apartment,))
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", (OLD, row_id))
    return row_id


def _healthy() -> int:
    _, _, stay = _stay(registered_minutes_ago=1)
    return door_codes.ensure_row(stay)  # a new row: attempts 0, next_attempt_at = now


def _row(row_id: int):
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))


def _in(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).replace(microsecond=0).isoformat()


@pytest.fixture
def lock(monkeypatch):
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("4821937", "code-1"))
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: None)


def test_stuck_rows_do_not_starve_a_healthy_new_row(monkeypatch, lock):
    monkeypatch.setattr(door_codes, "BATCH", 3)
    stuck = [_stuck("not_eligible") for _ in range(4)]  # more than one batch
    healthy = _healthy()
    door_codes._issue_due(db.utcnow())  # the first 3 stuck rows are tried and put off
    assert _row(healthy)["state"] == door_codes.PENDING
    door_codes._issue_due(db.utcnow())  # 1 stuck row left: the healthy row fits in the batch
    assert _row(healthy)["state"] == door_codes.ISSUED  # never, before 1173: the stuck rows stay first
    assert all(_row(r)["state"] == door_codes.PENDING for r in stuck)


@pytest.mark.parametrize(
    "reason, minutes", [("not_eligible", 15), ("no_account", 15), ("bad_window", 60)]
)
def test_a_released_row_waits_its_backoff_before_it_is_taken_again(monkeypatch, lock, reason, minutes):
    row_id = _stuck(reason)
    seen = []
    real = door_codes.issue
    monkeypatch.setattr(
        door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or real(rid, allow_gateway=allow_gateway)
    )
    door_codes._issue_due(db.utcnow())
    row = _row(row_id)
    assert seen == [row_id] and row["state"] == door_codes.PENDING and row["last_error"] == reason
    assert row["attempts"] == 0  # the release still takes back the attempt
    wait = datetime.fromisoformat(row["next_attempt_at"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=minutes - 1) < wait <= timedelta(minutes=minutes)
    door_codes._issue_due(_in(minutes - 2))
    assert seen == [row_id]  # not taken before the backoff ends
    door_codes._issue_due(_in(minutes + 1))
    assert seen == [row_id, row_id]  # taken again afterwards


def test_a_new_row_is_taken_before_repeated_retries(monkeypatch):
    """New rows are inserted with next_attempt_at = now, which sorts after every older retry."""
    monkeypatch.setattr(door_codes, "BATCH", 3)
    for _ in range(5):
        _, _, stay = _stay(registered_minutes_ago=5)
        row_id = door_codes.ensure_row(stay)
        db.execute(
            "UPDATE door_code SET state = ?, attempts = 2, next_attempt_at = ? WHERE id = ?",
            (door_codes.RETRYING, OLD, row_id),
        )
    new_id = _healthy()
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert len(seen) == 3 and new_id in seen  # fails on SQLite and PostgreSQL without the attempts order


def test_pending_and_retrying_rows_of_an_ended_stay_expire_and_live_ones_do_not(lock):
    today = deadlines.local_now().date()
    ids = {}
    for name, state in (("pending", door_codes.PENDING), ("retrying", door_codes.RETRYING)):
        _, _, stay = _stay(registered_minutes_ago=30)
        row_id = door_codes.ensure_row(stay)  # the stay is live now, so the row can be made
        db.execute("UPDATE door_code SET state = ?, next_attempt_at = ? WHERE id = ?", (state, OLD, row_id))
        db.execute(
            "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
            ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
        )
        ids[name] = row_id
    live = _healthy()
    counts = door_codes.reconcile()
    assert _row(ids["pending"])["state"] == door_codes.EXPIRED
    assert _row(ids["retrying"])["state"] == door_codes.EXPIRED
    assert counts["expired"] == 2
    assert _row(live)["state"] == door_codes.ISSUED
EOF
echo written
```
8. New and changed tests on SQLite. Expect `40 passed` (`test_issue_queue_starvation.py` has 6 cases) and no `failed`.
```bash
cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_null_order_portability.py tests/test_door_code_lost_pin.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30
```
9. Test-map rows (door codes and TTLock, admin ops) plus the state-machine tests, SQLite. Expect `522 passed, 2 skipped` (the 2 Playwright skips are fine).
```bash
cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_admin_operations.py tests/test_null_order_portability.py tests/test_issue_queue_starvation.py tests/test_sm_*.py -q --tb=short -x 2>&1 | tail -30
```
10. Lint. Expect `All checks passed!`.
```bash
cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30
```
11. Go (tables.go changed). Expect no `gofmt` output and `ok`.
```bash
cd go && gofmt -l internal/statemachine | tail -5; go vet ./internal/statemachine 2>&1 | tail -5; go test ./internal/statemachine 2>&1 | tail -5
```
12. PostgreSQL: start it if needed, then run steps 8 and 9 again on it. Expect `accepting connections` (or the cluster starts), the schema step prints its last lines without an error, then `26 passed` for the first run and `367 passed, 3 skipped` for the second.
```bash
pg_isready -h localhost || sudo pg_ctlcluster 16 main start
cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python scripts/pg_schema.py apply --expect-database ubytest 2>&1 | tail -3
```
```bash
cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_null_order_portability.py tests/test_door_code_lost_pin.py tests/test_sm_door_code_state.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -30
```
   If PostgreSQL will not start, write "not run" for steps 12 and the bites on PostgreSQL in the report; CI (`test-postgres`, `test-postgres-full`) runs them.
13. Commit the change first, so the bites below can be undone with `git checkout HEAD -- <file>`. Expect `git status --short` to print nothing after the commit.
```bash
git add App/app/door_codes.py App/tests/test_sm_door_code_state.py go/internal/statemachine/tables.go App/tests/test_door_code_lost_pin.py App/tests/test_null_order_portability.py App/tests/test_issue_queue_starvation.py
git commit -q -m '1173: door-code issue queue is not starved by rows that cannot be issued' && git status --short | tail -5
```
Steps 14 to 17 are revert-bites. Each bite edits `door_codes.py` only, runs one test file on SQLite and on PostgreSQL, restores the file and proves the tree is clean. The bite must FAIL; a pass means the test does not guard the fix: STOP. In the commands `tail -8` shows the pytest summary lines.
14. Bite B1. No backoff: the stuck rows stay due. From the repo root:
```bash
cd App && sed -i 's/^RELEASE_RETRY_MINUTES = .*/RELEASE_RETRY_MINUTES = {}/' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; both databases: `4 failed, 2 passed` (`test_stuck_rows_do_not_starve_a_healthy_new_row` and the 3 `test_a_released_row_waits_its_backoff_before_it_is_taken_again` cases); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
15. Bite B2. No `attempts` order: a new row (next_attempt_at = now) sorts after older retries. From the repo root:
```bash
cd App && sed -i 's/ORDER BY (attempts > 0), (next_attempt_at IS NOT NULL)/ORDER BY (next_attempt_at IS NOT NULL)/' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; both databases: `1 failed, 5 passed` (`test_a_new_row_is_taken_before_repeated_retries`); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
16. Bite B3. No NULL clause (the 1181 fix): this is the bite that differs between the databases. From the repo root:
```bash
cd App && sed -i 's/(attempts > 0), (next_attempt_at IS NOT NULL), next_attempt_at, id/(attempts > 0), next_attempt_at, id/' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_null_order_portability.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_null_order_portability.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; SQLite: `1 failed, 1 passed` (only the SQL-text test `test_due_queries_put_null_next_attempt_first`; SQLite sorts NULL first anyway). PostgreSQL: `2 failed` (that one and `test_issue_due_takes_a_pin_lost_row_before_other_due_rows`); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
17. Bite B4. Expiry compares the wrong way round: ended stays are not expired. From the repo root:
```bash
cd App && sed -i 's/AND date_to < ?)",/AND date_to > ?)",/' app/door_codes.py && git diff --stat | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=no 2>&1 | tail -8
UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py -q --tb=no 2>&1 | tail -8
cd .. && git checkout HEAD -- App/app/door_codes.py && git diff HEAD --stat | tail -3
```
   Expect: the `git diff --stat` after the `sed` shows `1 file changed`; both databases: `1 failed, 5 passed` (`test_pending_and_retrying_rows_of_an_ended_stay_expire_and_live_ones_do_not`); the last command prints nothing (empty `git diff HEAD --stat`). If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` again and check again before going on.
18. Context lint, from the repo root. Expect an OK line.
```bash
python3 scripts/context_lint.py | tail -3
```
19. Write `docs/tasks/1173-report.md` (section 9), set `Status: review` in `docs/tasks/1173-issue-queue-starvation.md`, then:
```bash
git diff HEAD --stat | tail -5
git add docs/tasks/1173-report.md docs/tasks/1173-issue-queue-starvation.md
git commit -q -m '1173: report' && git status --short | tail -3
```
   Before this commit `git diff HEAD --stat` must list only the two docs files.

## 5. Do not touch

Anything outside section 3, including `BATCH`, `_handle_cancellations` and `_revoke_one` (checked, no change), the `door_code_pin_unverified` card (1173b), schema and migrations, and `docs/context/*` (the orchestrator updates status, decisions and known-issues). No `NULLS FIRST`. Hard rules 3, 4, 5 of AGENTS.md. Do not push, merge or deploy.

## 6. Commands

The commands are in the steps (SQLite: steps 8, 9, 14 bites; PostgreSQL: step 12 and the bites; ruff 10; Go 11; lint). Never run the full suite.

## 7. Acceptance

- [ ] `git diff 8f1b54cd --stat` (or the base) lists exactly the six files of section 3 plus the two task docs.
- [ ] Steps 8, 9, 10, 11 green on SQLite; step 12 green on PostgreSQL (or "not run" with the reason).
- [ ] Each of the four bites fails the named test(s) as written, on SQLite and PostgreSQL. B3 shows the difference: SQLite fails only the SQL-text test, PostgreSQL fails 2.
- [ ] After every bite `git diff HEAD --stat` printed nothing; the last commit before the report holds the fixed code (`git show HEAD --stat` after step 13 lists the six files).
- [ ] `python3 scripts/context_lint.py | tail -3` OK.

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor assertion fails, a test fails twice, a bite passes, you reach 25 tool calls or about 50k tokens, a file outside section 3 needs a change, or you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/1173-report.md` (600 tokens at most): 1. `git diff 8f1b54cd --stat`; 2. each command with the last 5 lines (SQLite and PostgreSQL results side by side for the bites); 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left (open the PR, merge after green checks with `scripts/merge-pr-on-green.sh`).

## Risk list (for the reviewer)

`App/app/door_codes.py` (`_release_issue_claim`, `_issue_due` ORDER BY, `_expire_ended_stays`, the first lines of `reconcile`), `go/internal/statemachine/tables.go` (two rows), the changed existing test `test_door_code_lost_pin.py`. Orchestrator at the end: append to known-issues that a release back to `pending` must always move `next_attempt_at` (1173), and record the three backoffs in decisions.

## Owner steps

1. Open the PR when the checks are green, including test-postgres and test-postgres-full, and merge with `scripts/merge-pr-on-green.sh`.
