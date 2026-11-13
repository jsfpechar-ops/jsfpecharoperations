# 1172: NULL order is the same on SQLite and PostgreSQL in "due rows" queries

Status: todo
Depends on: none | Base commit: claude/zealous-maxwell-a7ub54 HEAD (4bdf1939) | Branch: task/1172-null-order
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three `ORDER BY <nullable column> LIMIT ?` queries must say where NULL goes, so a brand-new row (NULL) is taken first on PostgreSQL too. Today PostgreSQL sorts NULL last, so a guest's brand-new door code can wait behind a full batch of due retries (likely cause of the one-off test-postgres-full failure in `test_door_code_handover.py::test_an_issued_code_names_the_real_first_use_deadline`, row never issued).

## 2. Context

SQLite sorts NULL first in ascending order, PostgreSQL sorts NULL last. Rule 5: SQL stays portable. `NULLS FIRST` works on the local SQLite (3.53.1) but CI's SQLite version is not pinned by us, so use the portable form `ORDER BY (col IS NOT NULL), col`: false (NULL) sorts before true on both databases.

Audit of every `ORDER BY` on a nullable column in `App/app` and `go/internal` (all other `ORDER BY ... LIMIT` hits sort by `id` or by NOT NULL columns):

| # | file:line | Column | Intended order | Today SQLite / PostgreSQL | Fix |
|---|---|---|---|---|---|
| 1 | App/app/door_codes.py:1506 (`_issue_due`) | `next_attempt_at` (nullable) | NULL (new code, guest waiting) first, then oldest retry | NULL first / NULL last: bug | yes |
| 2 | App/app/door_codes.py:1174 (`_handle_cancellations` revoke batch) | `dc.next_attempt_at` (nullable) | NULL (revoke not yet tried) first | NULL first / NULL last | yes (same pattern) |
| 3 | App/app/admin_ops.py:182 (`feeds_needing_attention`) | `COALESCE(last_checked_at, last_sync_at)` (both nullable; NULL = never checked) | never-checked first (most stale), then oldest | NULL first / NULL last: with `limit` the worst feed is cut off | yes |
| 4 | App/app/door_codes.py:1530 | `issued_at` | filter `issued_at IS NOT NULL` | no NULLs reach the sort | no |
| 5 | App/app/jobqueue.py:77, go/internal/jobs/queue.go:63 | `run_at` | oldest first | `run_at TEXT NOT NULL` (migrations_pg/00003_job.sql) | no |
| 6 | App/app/meta_capi.py:233, push.py:331, mail.py:747, cleaning_codes.py:260, go/internal/metacapi/send.go:437, pushsend/pushsend.go:287 | order by `id`; `next_attempt_at` only filtered | by id | NULL not in sort key | no |
| 7 | App/app/admin_ops.py:102, 139, 255; admin_funnel.py:127; go/internal/posthog/sync.go:347 | `since` (COALESCE ending in `g.updated_at`), `created_at` | oldest first | `created_at TEXT NOT NULL` on submission, email_outbox, user_account | no |
| 8 | billing_analytics.py:118, 125, 131 | `trial_ends_at`, `due_date`, `period_end` | soonest first | rows are filtered with `>= ?`, `< ?`, `cancel_at_period_end = 1`; `period_end` of a cancelling account is set | no |

There is no Go twin of rows 1-3 (Go jobs touch `door_code` nowhere in a sorted due query), so no 1170b. Verified on the real local PostgreSQL 16: with the old `ORDER BY` the new tests failed (`assert 6 in [1, 2, 3]`, `assert [7] == [10]`); with the fix 11 passed. SQLite: the behaviour tests pass with the old code (that is the bug: SQLite hides it), so `test_due_queries_put_null_next_attempt_first` asserts the generated SQL and fails on SQLite when reverted.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | two `ORDER BY` lines (rows 1, 2) |
| App/app/admin_ops.py | edit | one `ORDER BY` (row 3) |
| App/tests/test_null_order_portability.py | new | two door-code tests |
| App/tests/test_admin_operations.py | edit | append one test |

No other file may change.

## 4. Steps

1. In `App/app/door_codes.py` replace the anchor (exactly one, in the revoke batch):
   ```
           "ORDER BY dc.next_attempt_at LIMIT ?",
   ```
   with
   ```
           "ORDER BY (dc.next_attempt_at IS NOT NULL), dc.next_attempt_at LIMIT ?",
   ```
   Check: `grep -n "IS NOT NULL), dc.next_attempt_at" App/app/door_codes.py | tail -30` shows 1 line.
2. In `App/app/door_codes.py` replace the anchor (in `_issue_due`, exactly one):
   ```
           "ORDER BY next_attempt_at LIMIT ?",
   ```
   with
   ```
           "ORDER BY (next_attempt_at IS NOT NULL), next_attempt_at LIMIT ?",
   ```
   Check: `grep -n "ORDER BY (next_attempt_at IS NOT NULL)" App/app/door_codes.py | tail -30` shows 1 line.
3. In `App/app/admin_ops.py` replace the anchor (in `feeds_needing_attention`):
   ```
           f"AS workspace {where} ORDER BY last_checked LIMIT ?",
   ```
   with (the alias `last_checked` cannot sit inside an expression on PostgreSQL, so the full COALESCE is repeated)
   ```
           f"AS workspace {where} "
           "ORDER BY (COALESCE(f.last_checked_at, f.last_sync_at) IS NOT NULL), last_checked LIMIT ?",
   ```
   Check: `grep -n "IS NOT NULL), last_checked" App/app/admin_ops.py | tail -30` shows 1 line.
4. Create `App/tests/test_null_order_portability.py` with exactly:
```python
"""A new row (NULL next_attempt_at) is processed before due retries on SQLite and PostgreSQL (task 1172).

SQLite sorts NULL first ascending, PostgreSQL sorts it last. Every due-row query that has a LIMIT must say
which it wants, so the guest who waits on a brand-new door code is never queued behind 20 retries.
"""
from __future__ import annotations

import re

from app import db, door_codes
from tests.test_door_codes_safeguards import _env, _stay  # noqa: F401


def _retrying(stay: int, minute: int) -> int:
    row_id = door_codes.ensure_row(stay)
    db.execute(
        "UPDATE door_code SET state = ?, attempts = 1, next_attempt_at = ? WHERE id = ?",
        (door_codes.RETRYING, f"2000-01-01T00:{minute:02d}:00+00:00", row_id),
    )
    return row_id


def _seed_retries_and_one_new(count: int) -> int:
    for _ in range(count):
        _, _, stay = _stay(registered_minutes_ago=5)
        _retrying(stay, minute=1)
    _, _, stay = _stay(registered_minutes_ago=1)
    row_id = door_codes.ensure_row(stay)
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row_id,))
    return row_id


def test_issue_due_takes_a_new_row_before_due_retries(monkeypatch):
    monkeypatch.setattr(door_codes, "BATCH", 3)
    new_id = _seed_retries_and_one_new(5)
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
        assert re.search(r"ORDER BY \((\w+\.)?next_attempt_at IS NOT NULL\), (\w+\.)?next_attempt_at", sql), sql
```
5. Append to the end of `App/tests/test_admin_operations.py` (two blank lines before it; no new imports needed):
```python


def test_a_never_checked_feed_is_listed_before_stale_ones():
    """Task 1172: NULL sorts first on SQLite and last on PostgreSQL; the list must put it first on both."""
    host_id = _account("feedsnull", "host")
    assert demo.seed(host_id)
    apartment = db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (host_id,)
    )["id"]
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=admin_ops.FEED_STALE_HOURS + 2)).replace(microsecond=0).isoformat()
    db.execute("UPDATE ical_feed SET active = 0 WHERE apartment_id IN "
               "(SELECT id FROM apartment WHERE owner_user_id = ?)", (host_id,))
    ids = []
    for index in range(3):
        ids.append(db.insert("ical_feed", {
            "apartment_id": apartment, "url": f"https://example.test/stale{index}.ics", "active": 1,
            "created_at": old, "last_status": "ok", "last_sync_at": old, "last_checked_at": old,
        }))
    never = db.insert("ical_feed", {
        "apartment_id": apartment, "url": "https://example.test/never.ics", "active": 1,
        "created_at": old,
    })
    rows = admin_ops.feeds_needing_attention(limit=1)["rows"]
    assert [row["feed_id"] for row in rows] == [never]  # fails on PostgreSQL with the old ORDER BY
```

## 5. Do not touch

Anything outside section 3, including `BATCH`, the queue/Go files, and schema. No `NULLS FIRST`. Hard rules 3, 4, 5 of AGENTS.md.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_null_order_portability.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -30` expect `... passed`.
2. Test-map rows (door codes, TTLock, admin ops): `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_admin_operations.py -q --tb=short -x 2>&1 | tail -30` expect all pass (2 skips that exist today are fine).
3. `.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 app tests 2>&1 | tail -30` expect `All checks passed!`.
4. Bite on SQLite: `git stash push -- app/app/door_codes.py` (path from repo root: `git stash push -- App/app/door_codes.py App/app/admin_ops.py`), run `.venv/bin/python -m pytest tests/test_null_order_portability.py -q --tb=line 2>&1 | tail -30`: expect `test_due_queries_put_null_next_attempt_first` FAILED; then `git stash pop`.
5. Bite on PostgreSQL (if it starts; otherwise write "not run" in the report, CI runs it in test-postgres and test-postgres-full): `sudo pg_ctlcluster 16 main start`; `export UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest`; `.venv/bin/python scripts/pg_schema.py apply --expect-database ubytest 2>&1 | tail -3`; run command 1 (expect pass); repeat the stash from command 4 and rerun command 1: expect 3 FAILED (`assert 6 in [1, 2, 3]` style, `assert [7] == [..]`); `git stash pop`; `unset UBYHOST_DATABASE_URL`.
6. From the repo root: `python3 scripts/context_lint.py | tail -3` expect OK.
(Go: no Go file changes, so no gofmt/vet/test.)

## 7. Acceptance

- [ ] The 3 `ORDER BY` lines match step 1-3, nothing else in `door_codes.py` / `admin_ops.py` changed (`git diff --stat` shows 4 files).
- [ ] Commands 1-3 and 6 green; command 4 shows the SQL-order test failing on the old code.
- [ ] Command 5 shown on PostgreSQL (3 fail on old code, pass on new) or marked not run.

## 8. Stop and ask

Stop, and write the report, if an anchor is not found, a test fails twice, you reach 25 tool calls, a file outside section 3 needs a change, or you need push, merge, secrets or deploy.

## 9. Report

Write `docs/tasks/1172-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left (none).

## Risk list (for the reviewer)

`App/app/door_codes.py` (two lines), `App/app/admin_ops.py` (one line). Orchestrator at the end: append to known-issues that `ORDER BY nullable LIMIT` must use `(col IS NOT NULL), col`.

## Owner steps

1. Open the PR when the green checks show, including test-postgres and test-postgres-full; merge with `scripts/merge-pr-on-green.sh`.
