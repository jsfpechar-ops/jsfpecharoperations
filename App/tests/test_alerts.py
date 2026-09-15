"""Persistent host alerts and deduplication rules."""
from __future__ import annotations

from app import alerts, db


def test_open_alert_is_refreshed_instead_of_duplicated():
    db.init_db()
    key = "alerts-test-refresh"
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
    try:
        alerts.raise_alert("warning", "test", "First message", dedupe_key=key)
        first = db.query_one("SELECT id, message FROM alert WHERE dedupe_key = ?", (key,))
        alerts.raise_alert("critical", "test", "Updated message", detail="more", dedupe_key=key)
        rows = db.query("SELECT id, level, message, detail FROM alert WHERE dedupe_key = ?", (key,))
        assert len(rows) == 1
        assert rows[0]["id"] == first["id"]
        assert rows[0]["level"] == "critical"
        assert rows[0]["message"] == "Updated message"
        assert rows[0]["detail"] == "more"
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))


def test_user_dismissed_alert_does_not_block_future_failures():
    """Hosts may dismiss a banner, but a later rejection must still surface."""
    db.init_db()
    key = "submission_rejected:999001"
    db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
    try:
        past_id = db.insert(
            "alert",
            {
                "level": "critical",
                "kind": "submission_rejected",
                "message": "Old rejection",
                "dedupe_key": key,
                "created_at": db.utcnow(),
                "resolved_at": db.utcnow(),
                "user_dismissed": 1,
            },
        )
        alerts.raise_alert(
            "critical",
            "submission_rejected",
            "New rejection after dismiss",
            dedupe_key=key,
        )
        open_row = db.query_one(
            "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
        )
        assert open_row
        assert open_row["id"] != past_id
        assert open_row["message"] == "New rejection after dismiss"
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
