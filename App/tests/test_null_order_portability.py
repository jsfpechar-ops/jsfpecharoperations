"""A due row with NULL next_attempt_at is taken before other due rows on SQLite and PostgreSQL (task 1172).

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
            r"ORDER BY (CASE WHEN .+? END, )?\((\w+\.)?next_attempt_at IS NOT NULL\), (\w+\.)?next_attempt_at", sql
        ), sql
