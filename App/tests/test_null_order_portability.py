"""A new row (NULL next_attempt_at) is processed before due retries on SQLite and PostgreSQL (task 1170).

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
