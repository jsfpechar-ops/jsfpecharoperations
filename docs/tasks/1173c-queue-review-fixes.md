# 1173c: fixes from the fresh review of 1173 and 1173b (tests that guard nothing, lost codes of extended stays, queue order, a stale card)

Status: todo
Depends on: 1173b (both are in the base) | Base commit: claude/zealous-maxwell-a7ub54 HEAD (21d70cf3, PR #950) | Branch: task/1173c-queue-review-fixes
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (about 18 calls planned; if you reach 25, stop and write the report as `blocked`)

## 1. Objective

Close five findings of the review of 1173 and 1173b. M1: three mutants of the 1173/1173b code pass every test, so add tests that kill them. M2: a row that expired before it ever got a lock code never comes back when the stay is extended; delete it so `ensure_row` makes a new one. L1: rows that `issue()` put back for `not_eligible`, `no_account` or `bad_window` sort ahead of real retries every 15 minutes; make them go last. L4: the `door_code_delayed` card stays open when its stay expires or is revoked without a code; close it in the 1173b sweep.

## 2. Context

Rules: AGENTS.md hard rules 1 (UbyPort first: this touches door codes only), 4 (no new dependency), 5 (SQL only through `db.py` helpers, Postgres-portable; no schema change here). No UI, no template, no copy.

Code that changes, all in `App/app/door_codes.py` (current text, verbatim):

`_issue_due` (the due query):
```python
    due = db.query(
        "SELECT id FROM door_code WHERE state IN (?, ?) "
        "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "ORDER BY (attempts > 0), (next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",
        (PENDING, RETRYING, now_iso, BATCH),
    )
```
`_expire_ended_stays` (the guard the new tests pin):
```python
            "WHERE state IN (?, ?) AND claimed_at IS NULL AND reservation_id IN "
            "(SELECT id FROM reservation WHERE status = 'active' AND archived_at IS NULL AND date_to < ?)",
```
`_resolve_unverified_cards` (1173b sweep): one `UPDATE alert ... kind = 'door_code_pin_unverified' ... AND NOT EXISTS (SELECT 1 FROM door_code dc WHERE dc.reservation_id = alert.reservation_id AND dc.state = ?)`.

`_handle_cancellations` deletes a `revoked` row of a revived stay (`DELETE FROM door_code WHERE id = ? AND state = ?`, then audit `door_code_reset`). `TRANSITIONS` has `EXPIRED: set()` and `REVOKED: set()`: a delete is not a transition, so the state machine and its Go mirror (`go/internal/statemachine`) do not change.

### Decisions in this brief (the orchestrator made them; do not reopen)

**L1, the order.** `_issue_due` takes rows in three ranks: rank 0 untried new rows (and re-issue rows with `last_error = 'pin_lost'`, `next_attempt_at` NULL), rank 1 real retries (`attempts > 0`), rank 2 released rows (`last_error` is one of `RELEASE_RETRY_MINUTES`' keys, whatever `attempts` is). Final clause:
```sql
ORDER BY CASE WHEN last_error IN (?, ?, ?) THEN 2 WHEN attempts > 0 THEN 1 ELSE 0 END, (next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?
```
The three `?` are `RELEASE_REASONS = tuple(RELEASE_RETRY_MINUTES)` (not_eligible, no_account, bad_window), passed between `now_iso` and `BATCH`. `last_error` NULL makes `IN` NULL, so the `WHEN` is skipped: correct on both databases. The `(next_attempt_at IS NOT NULL)` term after the CASE keeps the 1172 NULL-first order on SQLite and PostgreSQL. A released row that is tried again and fails for a real reason gets a new `last_error`, so it becomes rank 1. `App/tests/test_null_order_portability.py` has a regex for the old clause; step 5 updates it.

**M2, the revive rule.** New `_revive_unissued_expired()`, called as a `_phase` right after `_expire_ended_stays` and before `_issue_due`. It deletes a door_code row when ALL hold: `state = 'expired'`; `provider_code_id IS NULL` (never got a lock code); its stay is eligible again by `_eligible_sql()` (active, not archived, registered, `date_to >= Prague today`, lock set up, live/manual rule); and the stay window end (`ttlock.stay_window(date_from, date_to, checkin_hour, checkout_hour, config.DOOR_CODE_BUFFER_HOURS)`) is not before now. The delete is guarded (`WHERE id = ? AND state = 'expired'`) and audited `door_code_reset`, exactly like a revoked row of a revived stay. The same tick's `_issue_due` makes the new pending row through `ensure_row`. The window check is the guard against a loop: on the check-out day the stay is still eligible (`date_to >= today`) but `issue()` expires a row whose window end has passed. Rows that had a code (`provider_code_id` set) are never deleted. A stay that cannot get a row again (no TTLock account) simply has no row, which the guest page shows as waiting or delayed: acceptable.

**L4.** `_resolve_unverified_cards` gets a second `UPDATE alert`: kind `door_code_delayed`, open, and the stay has a door_code row in state `expired` or `revoked`. A stay with no row, or with a row that was deleted for a revival, is not swept (it still waits for a code; `_alert_delayed` raises that card). The function keeps its name.

**L3, not fixed (known issue, orchestrator records it):** a card resolved while a row is `revoke_pending`, then the delete refused and the stay revived: `_keep_issued` restores the row without a lock lookup and the card stays closed.

### Test helpers (already in the repo)

`App/tests/test_issue_queue_starvation.py` has `_stuck(reason)`, `_healthy()`, `_row()`, `OLD`, the `lock` fixture and imports `datetime`, `timedelta`, `pytest`, `db`, `deadlines`, `door_codes`, `ttlock`, `_stay`. `App/tests/test_door_code_unverified_card.py` has `_issued_stay`, `_card`, `_open`, `_row`, the `lock` fixture and imports `alerts`, `db`, `deadlines`, `door_codes`, `ttlock`, `timedelta`, `_stay`. The second stay of a test needs another `lock_id`, or the two stays share a period and the second code is refused (`period_shared`): step 4 adds that parameter.

Anchors: each `sub(old, new)` asserts `old` occurs exactly once; if not, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | `RELEASE_REASONS`, the due ORDER BY, `_revive_unissued_expired` and its `_phase` call, the second UPDATE in `_resolve_unverified_cards` |
| App/tests/test_issue_queue_starvation.py | edit | append 8 test cases (7 functions, one parametrized twice) |
| App/tests/test_door_code_unverified_card.py | edit | `_issued_stay(lock_id)` parameter; append 3 tests |
| App/tests/test_null_order_portability.py | edit | one regex learns the CASE clause |
| docs/tasks/1173c-queue-review-fixes.md | edit | `Status: todo` to `review` |
| docs/tasks/1173c-report.md | create | report |

No other file may change. No Go file changes, so no Go test.

## 4. Steps

Run from the repo root unless `cd App`. End commit messages with the attribution lines your session gives you. Never use `git rebase`, `git commit --amend`, `git stash` or `git commit -a`; `git add` only the named files. Restore a bitten file only with `git checkout HEAD -- <file>`, and check `git diff HEAD --stat` is empty before every commit.

1. Preflight: 1173 and 1173b are in the tree. Expect `1`, `2`, an empty status, and the new branch.
```bash
grep -c 'RELEASE_RETRY_MINUTES = ' App/app/door_codes.py; grep -c '_resolve_unverified_cards' App/app/door_codes.py; git status --short | tail -5; git checkout -b task/1173c-queue-review-fixes | tail -3
```
   The `2` is the definition and its call: it proves 1173b is in the tree.
2. Edit `App/app/door_codes.py` (six anchors). Expect `ok App/app/door_codes.py`.
```bash
python3 - <<'PY'
p = "App/app/door_codes.py"
s = open(p, encoding="utf-8").read()

def sub(old, new):
    global s
    assert s.count(old) == 1, ("anchor not found exactly once", old[:70])
    s = s.replace(old, new)

# L1
sub(
r'''RELEASE_RETRY_MINUTES = {"not_eligible": 15, "no_account": 15, "bad_window": 60}
''',
r'''RELEASE_RETRY_MINUTES = {"not_eligible": 15, "no_account": 15, "bad_window": 60}
# 1173c: _issue_due takes rows in this order: new rows (rank 0), real retries (1), released rows (2).
# A released row has attempts 0 again, so without the rank it sorts with the new rows and, being older,
# ahead of them and of every real retry, every time its backoff ends.
RELEASE_REASONS = tuple(RELEASE_RETRY_MINUTES)
''',
)
sub(
r'''        "ORDER BY (attempts > 0), (next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",
        (PENDING, RETRYING, now_iso, BATCH),
    )''',
r'''        "ORDER BY CASE WHEN last_error IN (?, ?, ?) THEN 2 WHEN attempts > 0 THEN 1 ELSE 0 END, "
        "(next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",
        (PENDING, RETRYING, now_iso, *RELEASE_REASONS, BATCH),
    )''',
)

# M2
sub(
r'''def _expire_ended_stays(now_iso: str) -> int:''',
r'''def _revive_unissued_expired() -> int:
    """Delete an expired row that never got a code when its stay is live again (1173c).

    expired is terminal and ensure_row never overwrites a row, so a stay that ended before a code was made
    and was then extended would stay without one. Like a revoked row of a revived stay (_handle_cancellations)
    the row is deleted; the same tick's _issue_due makes a new one. Only rows with no lock code
    (provider_code_id IS NULL), only stays eligible again, and only when the window end is still ahead:
    without that check issue() would expire the new row on every tick of the check-out day.
    """
    clause, today = _eligible_sql()
    rows = db.query(
        f"SELECT dc.id, r.date_from, r.date_to, a.checkin_hour, a.checkout_hour "
        f"FROM door_code dc JOIN reservation r ON r.id = dc.reservation_id "
        f"JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE dc.state = ? AND dc.provider_code_id IS NULL AND {clause}",
        (EXPIRED, today),
    )
    now_ms = int(_now().timestamp() * 1000)
    revived = 0
    for row in rows:
        try:
            _, end_ms = ttlock.stay_window(
                row["date_from"], row["date_to"], row["checkin_hour"], row["checkout_hour"],
                config.DOOR_CODE_BUFFER_HOURS,
            )
        except ValueError:
            continue
        if end_ms < now_ms:
            continue
        # Guarded: only a row that is still expired is deleted.
        removed = db.execute("DELETE FROM door_code WHERE id = ? AND state = ?", (row["id"], EXPIRED))
        if removed:
            revived += 1
            db.audit("door_code_reset", f"door_code={row['id']}", actor="system")
    return revived


def _expire_ended_stays(now_iso: str) -> int:''',
)
sub(
r'''    counts["expired"] += int(ended or 0)

''',
r'''    counts["expired"] += int(ended or 0)
    _phase("revive_expired", _revive_unissued_expired)

''',
)

# L4
sub(
r'''    """Close the "code not confirmed" card of a stay whose code is no longer issued (1173b).

    Covers revoke, expiry and a deleted row. A new code (issue, move) resolves the card where it is made.
    """
    db.execute(
        "UPDATE alert SET resolved_at = ? WHERE kind = ? AND resolved_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM door_code dc "
        "WHERE dc.reservation_id = alert.reservation_id AND dc.state = ?)",
        (db.utcnow(), "door_code_pin_unverified", ISSUED),
    )
''',
r'''    """Close the cards of a stay whose code row has ended (1173b, 1173c).

    "Code not confirmed" (door_code_pin_unverified): the stay has no issued row any more (revoke, expiry,
    deleted row). "Code is taking too long" (door_code_delayed): the stay's row is expired or revoked, so
    no code is coming. A deleted row of a live stay is not swept: _alert_delayed raises that card again.
    A new code (issue, move) resolves both where it is made.
    """
    now = db.utcnow()
    db.execute(
        "UPDATE alert SET resolved_at = ? WHERE kind = ? AND resolved_at IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM door_code dc "
        "WHERE dc.reservation_id = alert.reservation_id AND dc.state = ?)",
        (now, "door_code_pin_unverified", ISSUED),
    )
    db.execute(
        "UPDATE alert SET resolved_at = ? WHERE kind = ? AND resolved_at IS NULL "
        "AND EXISTS (SELECT 1 FROM door_code dc "
        "WHERE dc.reservation_id = alert.reservation_id AND dc.state IN (?, ?))",
        (now, "door_code_delayed", EXPIRED, REVOKED),
    )
''',
)
open(p, "w", encoding="utf-8").write(s)
print("ok", p)
PY
```
3. Append the tests to `App/tests/test_issue_queue_starvation.py`. Expect `appended`.
```bash
cat >> App/tests/test_issue_queue_starvation.py <<'EOF'


# --- 1173c ---------------------------------------------------------------------------------------------


def _released() -> int:
    """A row issue() put back for not_eligible: attempts 0 again, its backoff over (due long ago)."""
    row_id = _stuck("not_eligible")
    db.execute("UPDATE door_code SET last_error = 'not_eligible' WHERE id = ?", (row_id,))
    return row_id


def test_released_rows_sort_after_new_rows_and_real_retries(monkeypatch):
    """25 released rows are older than a new row and a real retry; they still go last (1173c)."""
    monkeypatch.setattr(door_codes, "BATCH", 3)
    for _ in range(25):
        _released()
    _, _, stay = _stay(registered_minutes_ago=5)
    retry_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 2, last_error = 'network', next_attempt_at = ? WHERE id = ?",
        (door_codes.RETRYING, OLD, retry_id),
    )
    new_id = _healthy()
    seen = []
    monkeypatch.setattr(door_codes, "issue", lambda rid, allow_gateway=False: seen.append(rid) or True)
    door_codes._issue_due(db.utcnow())
    assert len(seen) == 3 and new_id in seen and retry_id in seen
    assert seen[:2] == [new_id, retry_id]  # new rows, then real retries, then released rows


def test_a_pending_row_of_a_stay_that_ends_today_is_not_expired(lock):
    """The test is date_to < today (the one _eligible_sql uses), not <=: the check-out day is still live."""
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=2)).isoformat(), today.isoformat(), stay),
    )
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", (OLD, row_id))
    assert door_codes._expire_ended_stays(db.utcnow()) == 0
    assert _row(row_id)["state"] == door_codes.PENDING


@pytest.mark.parametrize(
    "change",
    ["status = 'cancelled'", "archived_at = '2026-01-01T00:00:00+00:00'"],
    ids=["cancelled", "archived"],
)
def test_a_cancelled_or_archived_ended_stay_is_revoked_not_expired(lock, change):
    """_expire_ended_stays leaves it to _handle_cancellations: the row ends revoked (1173c)."""
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute(
        f"UPDATE reservation SET {change}, date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
    )
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", (OLD, row_id))
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.REVOKED


def _expired_unissued(stay_end_offset_days: int):
    """A stay whose row expired before any code was made, then its dates changed to end today + offset."""
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute("UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ? WHERE id = ?", (door_codes.EXPIRED, OLD, row_id))
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today + timedelta(days=stay_end_offset_days)).isoformat(), stay),
    )
    return stay, row_id


def test_an_expired_row_without_a_code_comes_back_when_the_stay_is_extended(lock):
    stay, old_id = _expired_unissued(2)
    door_codes.reconcile()
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (stay,))
    assert row["state"] == door_codes.ISSUED and row["provider_code_id"] == "code-1"
    assert db.query_one(
        "SELECT 1 AS n FROM audit WHERE action = 'door_code_reset' AND detail = ?", (f"door_code={old_id}",)
    )


def test_an_expired_row_stays_expired_when_its_window_has_ended(monkeypatch, lock):
    """date_to is today, so the stay is eligible, but the window ended: reviving it would loop every tick."""
    _, row_id = _expired_unissued(0)
    monkeypatch.setattr(ttlock, "stay_window", lambda *a, **k: (0, 1))
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED


def test_an_expired_row_that_had_a_code_stays_expired(lock):
    _, row_id = _expired_unissued(2)
    db.execute("UPDATE door_code SET provider_code_id = 'code-9' WHERE id = ?", (row_id,))  # issued, then expired
    assert door_codes._revive_unissued_expired() == 0
    assert _row(row_id)["state"] == door_codes.EXPIRED
EOF
echo appended
```
4. Edit `App/tests/test_door_code_unverified_card.py`: the helper gets a `lock_id` parameter, then three tests are appended. Expect `ok` then `appended`.
```bash
python3 - <<'PY'
p = "App/tests/test_door_code_unverified_card.py"
s = open(p, encoding="utf-8").read()
old = '''def _issued_stay(monkeypatch):
    """A stay with an issued code on its own window (no move pending)."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("1111111", "c1"))
    _, _, stay = _stay(registered_minutes_ago=1)
'''
new = '''def _issued_stay(monkeypatch, lock_id: str = "35662508"):
    """A stay with an issued code on its own window (no move pending). Another lock_id: a second property."""
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: ("1111111", "c1"))
    _, apartment, stay = _stay(registered_minutes_ago=1)
    db.execute("UPDATE apartment SET lock_id = ? WHERE id = ?", (lock_id, apartment))
'''
assert s.count(old) == 1, "anchor not found exactly once"
open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
PY
cat >> App/tests/test_door_code_unverified_card.py <<'EOF'


# --- 1173c ---------------------------------------------------------------------------------------------


def test_a_revoked_stay_closes_only_its_own_card(monkeypatch):
    """The sweep matches the card to its stay: stay B keeps its code and its card (1173c)."""
    stay_a, _ = _issued_stay(monkeypatch)
    stay_b, _ = _issued_stay(monkeypatch, lock_id="35662509")
    _card(stay_a)
    _card(stay_b)
    db.execute("UPDATE reservation SET status = 'cancelled' WHERE id = ?", (stay_a,))
    door_codes.reconcile()
    assert _open(stay_a) is None
    assert _open(stay_b) is not None


def _delayed_card(stay: int) -> None:
    apartment = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (stay,))["apartment_id"]
    alerts.raise_alert(
        "warning", "door_code_delayed", "Door code is taking too long",
        dedupe_key=f"door_code_delayed:{stay}", apartment_id=apartment, reservation_id=stay,
    )


def test_the_delayed_card_closes_when_the_stay_ends_without_a_code(lock):
    today = deadlines.local_now().date()
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    _, _, other = _stay(registered_minutes_ago=30)
    other_id = door_codes.ensure_row(other)
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id IN (?, ?)", ("2999-01-01T00:00:00+00:00", row_id, other_id))
    _delayed_card(stay)
    _delayed_card(other)
    db.execute(
        "UPDATE reservation SET date_from = ?, date_to = ? WHERE id = ?",
        ((today - timedelta(days=3)).isoformat(), (today - timedelta(days=1)).isoformat(), stay),
    )
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.EXPIRED
    assert alerts.open_alert(f"door_code_delayed:{stay}") is None
    assert alerts.open_alert(f"door_code_delayed:{other}") is not None  # still waiting: the card stays


def test_the_delayed_card_closes_when_a_waiting_stay_is_cancelled(lock):
    _, _, stay = _stay(registered_minutes_ago=30)
    row_id = door_codes.ensure_row(stay)
    db.execute("UPDATE door_code SET next_attempt_at = ? WHERE id = ?", ("2999-01-01T00:00:00+00:00", row_id))
    _delayed_card(stay)
    db.execute("UPDATE reservation SET status = 'cancelled' WHERE id = ?", (stay,))
    door_codes.reconcile()
    assert _row(row_id)["state"] == door_codes.REVOKED
    assert alerts.open_alert(f"door_code_delayed:{stay}") is None
EOF
echo appended
```
5. Update the regex in `App/tests/test_null_order_portability.py`. Expect `ok`.
```bash
python3 - <<'PY'
p = "App/tests/test_null_order_portability.py"
s = open(p, encoding="utf-8").read()
old = r'r"ORDER BY (\(attempts > 0\), )?\((\w+\.)?next_attempt_at IS NOT NULL\), (\w+\.)?next_attempt_at", sql'
new = r'r"ORDER BY (CASE WHEN .+? END, )?\((\w+\.)?next_attempt_at IS NOT NULL\), (\w+\.)?next_attempt_at", sql'
assert s.count(old) == 1, "anchor not found exactly once"
open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
PY
```
6. New tests and the order-portability test, SQLite. Expect `22 passed` (20 in the two 1173 files, 2 in the portability file).
```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
```
7. Test-map rows (door codes and TTLock, admin ops), the state-machine tests including `test_sm_go_parity.py`, and ruff, SQLite. Expect `536 passed, 2 skipped` (2 Playwright skips are fine) and `All checks passed!`.
```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_admin_operations.py tests/test_issue_queue_starvation.py tests/test_sm_*.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
(cd App && .venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30)
```
8. Commit before the bites. Expect an empty status afterwards.
```bash
git add App/app/door_codes.py App/tests/test_issue_queue_starvation.py App/tests/test_door_code_unverified_card.py App/tests/test_null_order_portability.py
git commit -q -m '1173c: review fixes (revive unissued expired rows, released rows last, card sweeps, tests)' && git status --short | tail -5
```
9. PostgreSQL: start if needed, apply the schema, run steps 6 and 7 on it. Expect `accepting connections`, `PostgreSQL schema apply OK`, `22 passed`, then `389 passed, 3 skipped` (3 skips: 2 Playwright, 1 sqlite-only). If PostgreSQL will not start, write "not run" in the report and go on.
```bash
pg_isready -h localhost || sudo pg_ctlcluster 16 main start
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python scripts/pg_schema.py apply --expect-database ubytest 2>&1 | tail -3)
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_issue_queue_starvation.py tests/test_door_code_unverified_card.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_admin_operations.py tests/test_issue_queue_starvation.py tests/test_null_order_portability.py -q --tb=short -x 2>&1 | tail -30)
```
10. Revert-bites. The script below applies eight one-line mutations to `door_codes.py` one at a time, runs the two test files, and restores the file in a `finally`. It prints `BITE FAILS AS EXPECTED <name>` per bite and `ALL BITES CAUGHT` at the end. A line `BITE NOT CAUGHT` or `ANCHOR NOT FOUND` means a test guards nothing: STOP. It is a scratch file in `/tmp`, not part of the repo. Write it, then run it on SQLite and on PostgreSQL, each from `App/`, then prove the tree is clean.
```bash
cat > /tmp/bites_1173c.py <<'EOF'
# 1173c revert-bites. Run from App/. Each bite edits app/door_codes.py, runs the two test files, restores the file.
import subprocess, sys
P = "app/door_codes.py"
orig = open(P, encoding="utf-8").read()
S = "tests/test_issue_queue_starvation.py::"
U = "tests/test_door_code_unverified_card.py::"
BITES = [
    ("A: expiry test <= instead of <",
     'archived_at IS NULL AND date_to < ?)",', 'archived_at IS NULL AND date_to <= ?)",',
     [S + "test_a_pending_row_of_a_stay_that_ends_today_is_not_expired"]),
    ("B: expiry ignores cancelled and archived",
     "(SELECT id FROM reservation WHERE status = 'active' AND archived_at IS NULL AND date_to < ?)",
     "(SELECT id FROM reservation WHERE date_to < ?)",
     [S + "test_a_cancelled_or_archived_ended_stay_is_revoked_not_expired"]),
    ("C: card sweep not matched to its stay",
     '"WHERE dc.reservation_id = alert.reservation_id AND dc.state = ?)",', '"WHERE dc.state = ?)",',
     [U + "test_a_revoked_stay_closes_only_its_own_card"]),
    ("M2a: revive without the window check",
     "        if end_ms < now_ms:\n            continue\n        # Guarded", "        # Guarded",
     [S + "test_an_expired_row_stays_expired_when_its_window_has_ended"]),
    ("M2b: revive also rows that had a code",
     "WHERE dc.state = ? AND dc.provider_code_id IS NULL AND {clause}", "WHERE dc.state = ? AND {clause}",
     [S + "test_an_expired_row_that_had_a_code_stays_expired"]),
    ("M2c: revive phase not called",
     '    _phase("revive_expired", _revive_unissued_expired)\n', "",
     [S + "test_an_expired_row_without_a_code_comes_back_when_the_stay_is_extended"]),
    ("L1: old ORDER BY",
     '"ORDER BY CASE WHEN last_error IN (?, ?, ?) THEN 2 WHEN attempts > 0 THEN 1 ELSE 0 END, "\n        "(next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",\n        (PENDING, RETRYING, now_iso, *RELEASE_REASONS, BATCH),',
     '"ORDER BY (attempts > 0), (next_attempt_at IS NOT NULL), next_attempt_at, id LIMIT ?",\n        (PENDING, RETRYING, now_iso, BATCH),',
     [S + "test_released_rows_sort_after_new_rows_and_real_retries"]),
    ("L4: delayed card sweep matches nothing",
     '(now, "door_code_delayed", EXPIRED, REVOKED),', '(now, "door_code_delayed_off", EXPIRED, REVOKED),',
     [U + "test_the_delayed_card_closes_when_the_stay_ends_without_a_code",
      U + "test_the_delayed_card_closes_when_a_waiting_stay_is_cancelled"]),
]
bad = 0
try:
    for name, old, new, expect in BITES:
        if orig.count(old) != 1:
            print("ANCHOR NOT FOUND", name); bad += 1; continue
        open(P, "w", encoding="utf-8").write(orig.replace(old, new))
        r = subprocess.run([".venv/bin/python", "-m", "pytest", "tests/test_issue_queue_starvation.py",
                            "tests/test_door_code_unverified_card.py", "-q", "--tb=no", "-p", "no:cacheprovider"],
                           capture_output=True, text=True)
        failed = [l[7:].split(" ")[0].split("[")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
        ok = all(e in failed for e in expect)
        print(("BITE FAILS AS EXPECTED " if ok else "BITE NOT CAUGHT ") + name, "|", r.stdout.strip().splitlines()[-1])
        bad += 0 if ok else 1
finally:
    open(P, "w", encoding="utf-8").write(orig)
print("ALL BITES CAUGHT" if bad == 0 else f"{bad} BITE(S) NOT CAUGHT: STOP")
sys.exit(1 if bad else 0)
EOF
echo written
```
```bash
(cd App && env -u UBYHOST_DATABASE_URL python3 /tmp/bites_1173c.py 2>&1 | tail -12)
(cd App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest python3 /tmp/bites_1173c.py 2>&1 | tail -12)
git diff HEAD --stat | tail -3
```
    Expect on both databases eight `BITE FAILS AS EXPECTED` lines and `ALL BITES CAUGHT` (the failed counts per bite are: A 1, B 2, C 1, M2a 1, M2b 1, M2c 1, L1 1, L4 2); the last command prints nothing. If it prints anything, run `git checkout HEAD -- App/app/door_codes.py` and check again.
11. Context lint, then the report and the commit. Expect an OK line; before the commit `git diff HEAD --stat` lists only the two docs.
```bash
python3 scripts/context_lint.py | tail -3
git diff HEAD --stat | tail -5
sed -i 's/^Status: todo/Status: review/' docs/tasks/1173c-queue-review-fixes.md
git add docs/tasks/1173c-report.md docs/tasks/1173c-queue-review-fixes.md
git commit -q -m '1173c: report' && git status --short | tail -3
```

## 5. Do not touch

Anything outside section 3, including `TRANSITIONS`, `go/`, `db.py`, `migrations/`, `_keep_issued`, `_revive_one`, `_tell_host_unverified`. Hard rules 3, 4, 5 of AGENTS.md. Do not push, merge or deploy. Do not fix L3.

## 6. Commands

The steps carry them: SQLite 6 and 7, PostgreSQL 9, bites 10, lint 11. No Go change, so no Go commands. Never the full suite.

## 7. Acceptance

- [ ] `git diff 21d70cf3 --stat` lists the four files of section 3 plus the two task docs (the base may be later if #950 merged; then use the branch point).
- [ ] Step 6 `22 passed`, step 7 `536 passed, 2 skipped` and ruff `All checks passed!` on SQLite; step 9 `22 passed` and `389 passed, 3 skipped` on PostgreSQL (or "not run").
- [ ] Step 10: `ALL BITES CAUGHT` on both databases and `git diff HEAD --stat` empty afterwards.
- [ ] Lint OK.

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor assertion fails, a test fails twice, a bite is not caught, you reach 25 tool calls or about 50k tokens, a file outside section 3 needs a change, or you need push, merge, secrets or deploy.

## 9. Report

`docs/tasks/1173c-report.md` (600 tokens at most): 1. `git diff --stat`; 2. each command with the last 5 lines (SQLite and PostgreSQL side by side for the bites); 3. section 7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py`: the new ORDER BY (portable CASE, params order), `_revive_unissued_expired` (its DELETE is guarded by state and touches only expired rows with no lock code, never a row whose window ended), the second UPDATE in `_resolve_unverified_cards` (kind `door_code_delayed`, rows expired or revoked only).

## Owner steps

1. Open the PR when the checks are green, including test-postgres and test-postgres-full, and merge with `scripts/merge-pr-on-green.sh`.
