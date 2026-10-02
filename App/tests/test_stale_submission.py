"""A batch left 'running' by a dead process is held for a person, not resent."""
from __future__ import annotations

import json
import time

from app import db, reporting


def _guest(reservation: int, name: str, now: str) -> int:
    return db.insert(
        "guest",
        {"reservation_id": reservation, "surname": name, "first_name": "Test",
         "nationality": "GBR", "created_at": now, "updated_at": now},
    )


def _batch(apartment: int, guests: list, now: str) -> int:
    return db.insert(
        "submission",
        {"apartment_id": apartment, "created_at": now, "mode": "auto",
         "state": "running", "guest_ids": json.dumps(guests)},
    )


def test_a_running_batch_without_a_live_claim_becomes_outcome_unknown():
    db.init_db()
    now = db.utcnow()
    apartment = db.insert("apartment", {"internal_name": "Stale flat", "created_at": now})
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": "stale-1", "date_from": "2026-01-01",
         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
    )
    dead, sending, moved_on = (_guest(reservation, n, now) for n in ("Dead", "Sending", "Moved"))
    # A fresh row counts as stale once its claim has lapsed: the age of the
    # row is not what matters, the lease is.
    dead_batch = _batch(apartment, [dead], now)
    live_batch = _batch(apartment, [sending], now)
    db.insert("submission_claim", {"guest_id": sending, "claim_token": "t", "claimed_at": time.time()})
    old_batch = _batch(apartment, [moved_on], now)
    newer = db.insert(
        "submission",
        {"apartment_id": apartment, "created_at": now, "mode": "auto",
         "state": "error", "guest_ids": json.dumps([moved_on])},
    )
    db.execute("UPDATE guest SET submission_id = ? WHERE id = ?", (newer, moved_on))

    assert reporting.recover_stale_submissions(apartment) == 2

    def state(sid):
        return db.query_one("SELECT state FROM submission WHERE id = ?", (sid,))["state"]

    def pointer(gid):
        return db.query_one("SELECT submission_id FROM guest WHERE id = ?", (gid,))["submission_id"]

    assert state(dead_batch) == "outcome_unknown"
    assert state(old_batch) == "outcome_unknown"
    assert state(live_batch) == "running"
    assert pointer(dead) == dead_batch
    assert pointer(sending) is None
    assert pointer(moved_on) == newer, "a newer batch keeps the guest's pointer"
    assert reporting.apartment_in_doubt(apartment)
