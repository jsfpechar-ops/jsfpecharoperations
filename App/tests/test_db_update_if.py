"""Task 3.1: compare-and-set updates and updates inside a caller's transaction.

``db.update_if`` is the compare-and-set a background job needs so a request
cannot overwrite a state it read before the job changed it. ``db.update_in``
lets a caller make several writes, including guest writes, atomic.
"""
from __future__ import annotations

import pytest

from app import db


def _insert_alert() -> int:
    return db.insert(
        "alert",
        {
            "level": "info",
            "kind": "t",
            "message": "m",
            "created_at": db.utcnow(),
            "dedupe_key": "t:update_if",
        },
    )


def _level(alert_id: int) -> str:
    return db.query_one("SELECT level FROM alert WHERE id = ?", (alert_id,))["level"]


def test_update_if_applies_only_while_expected_matches():
    db.init_db()
    alert_id = _insert_alert()
    try:
        assert db.update_if("alert", alert_id, {"level": "warning"}, {"level": "info"}) is True
        assert _level(alert_id) == "warning"

        # The row no longer holds "info", so the second write must not apply.
        assert db.update_if("alert", alert_id, {"level": "critical"}, {"level": "info"}) is False
        assert _level(alert_id) == "warning"
    finally:
        db.execute("DELETE FROM alert WHERE id = ?", (alert_id,))


def test_update_if_with_no_values_is_a_no_op():
    db.init_db()
    alert_id = _insert_alert()
    try:
        assert db.update_if("alert", alert_id, {}, {"level": "info"}) is False
        assert _level(alert_id) == "info"
    finally:
        db.execute("DELETE FROM alert WHERE id = ?", (alert_id,))


def test_update_in_persists_after_the_immediate_block():
    db.init_db()
    alert_id = _insert_alert()
    try:
        db.update("alert", alert_id, {"level": "warning"})
        with db.immediate() as cur:
            db.update_in(cur, "alert", alert_id, {"level": "info"})
        assert _level(alert_id) == "info"
    finally:
        db.execute("DELETE FROM alert WHERE id = ?", (alert_id,))


def test_update_in_rolls_back_when_the_block_raises():
    db.init_db()
    alert_id = _insert_alert()
    try:
        db.update("alert", alert_id, {"level": "warning"})
        with pytest.raises(RuntimeError):
            with db.immediate() as cur:
                db.update_in(cur, "alert", alert_id, {"level": "info"})
                raise RuntimeError("boom")
        # The whole transaction rolled back, so the earlier level survives.
        assert _level(alert_id) == "warning"
    finally:
        db.execute("DELETE FROM alert WHERE id = ?", (alert_id,))
