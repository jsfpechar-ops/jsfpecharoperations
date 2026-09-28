"""One property's failure must not stop the sweep for everyone (AR-05).

``reporting.sweep`` used to abort on any exception, so a single bad row or a
locked database left every later property unfiled on every run. The
``DecryptionError`` branch already contained the unreadable-guest case; this
pins the catch-all that keeps the loop going for anything else, and the alert
that makes the stop visible.
"""
from __future__ import annotations

from app import db, reporting


def test_one_failing_property_does_not_stop_the_sweep(monkeypatch):
    db.init_db()
    now = db.utcnow()
    entity_ids = []

    def seed(token: str) -> int:
        """A minimal active, non-manual apartment, enough for the sweep."""
        entity_id = db.insert(
            "legal_entity",
            {"name": f"Sweep containment {token}", "created_at": now},
        )
        entity_ids.append(entity_id)
        return db.insert(
            "apartment",
            {
                "legal_entity_id": entity_id,
                "internal_name": f"Flat {token}",
                "permalink_token": token,
                "automation_mode": "auto",
                "active": 1,
                "created_at": now,
            },
        )

    first_id = seed("tok-sweep-contain-1")
    second_id = seed("tok-sweep-contain-2")

    calls = []

    def fake_submit_for_apartment(apartment_id, mode="auto"):  # noqa: ARG001
        calls.append(apartment_id)
        if apartment_id == first_id:
            raise RuntimeError("boom")
        return []

    monkeypatch.setattr(reporting, "submit_for_apartment", fake_submit_for_apartment)

    try:
        # The RuntimeError for the first property must not propagate.
        reporting.sweep()

        assert first_id in calls, "the failing property was not reached"
        assert second_id in calls, "the sweep stopped instead of moving on"

        card = db.query_one(
            "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL",
            (f"sweep_failed:{first_id}",),
        )
        assert card is not None, "a contained failure that stays silent is a silent drop"
    finally:
        for apartment_id in (first_id, second_id):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        for entity_id in entity_ids:
            db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
