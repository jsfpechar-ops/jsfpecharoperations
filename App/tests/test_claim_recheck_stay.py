"""1138: the claim drops a guest whose stay window moved after the list was built."""
from __future__ import annotations

import time

import pytest

from app import config, db, reporting


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db.close_connections()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "wp14.sqlite3")
    db.init_db()
    db.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, n INTEGER NOT NULL)")
    db.execute("INSERT INTO counter (id, n) VALUES (1, 0)")
    yield tmp_path
    db.close_connections()


def _stay():
    now = db.utcnow()
    apartment_id = db.insert("apartment", {"internal_name": "1138 flat", "created_at": now})
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "t1138", "date_from": "2026-12-01",
        "date_to": "2026-12-03", "created_at": now, "updated_at": now,
    })
    guest_id = db.insert("guest", {
        "reservation_id": reservation_id, "stay_from": "2026-12-01", "stay_to": "2026-12-03",
        "created_at": now, "updated_at": now,
    })
    return reservation_id, guest_id


def _pairs(guest_id, reservation_id):
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return [(guest, reservation)]


def _claim(pairs):
    token, claimed = reporting.claim_sendable(pairs)
    reporting.release_sendable_claim(token)
    return claimed


def test_unchanged_pair_is_claimed(fresh_db):
    rid, gid = _stay()
    assert len(_claim(_pairs(gid, rid))) == 1


def test_reservation_dates_moved_after_the_list_drops_the_pair(fresh_db):
    rid, gid = _stay()
    pairs = _pairs(gid, rid)
    db.update("reservation", rid, {"date_to": "2026-12-05"})
    assert _claim(pairs) == []
    assert db.query_one("SELECT 1 AS n FROM submission_claim WHERE guest_id = ?", (gid,)) is None


def test_guest_window_moved_after_the_list_drops_the_pair(fresh_db):
    rid, gid = _stay()
    pairs = _pairs(gid, rid)
    db.update("guest", gid, {"stay_from": "2026-12-02"})
    assert _claim(pairs) == []


def test_guest_edit_bumping_updated_at_drops_the_pair(fresh_db):
    rid, gid = _stay()
    pairs = _pairs(gid, rid)
    db.update("guest", gid, {"updated_at": "2099-01-01T00:00:00+00:00"})
    assert _claim(pairs) == []


def test_a_multi_batch_send_keeps_the_claim_live(fresh_db, monkeypatch):
    """Each batch runs under a claim whose claimed_at was just renewed."""
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    seen = []

    def fake_batch(apartment, pairs, mode="auto", env=None):
        row = db.query_one(
            "SELECT claimed_at FROM submission_claim WHERE claim_token = ?", (token,)
        )
        seen.append(row["claimed_at"])
        # Pretend this batch took ten minutes.
        db.execute(
            "UPDATE submission_claim SET claimed_at = claimed_at - 600 "
            "WHERE claim_token = ?",
            (token,),
        )
        return {"submitted": 1}

    monkeypatch.setattr(reporting, "submit_batch", fake_batch)
    monkeypatch.setattr(config, "UBYPORT_MAX_BATCH", 1)

    results = reporting._send_claimed_batches(
        {"id": 1}, claimed * 3, token, mode="auto", env=None
    )

    assert len(results) == 3
    floor = time.time() - 60
    assert len(seen) == 3 and all(value >= floor for value in seen)
    reporting.release_sendable_claim(token)


def test_a_lost_claim_stops_the_send_and_is_not_resurrected(fresh_db, monkeypatch):
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    calls = []
    monkeypatch.setattr(
        reporting, "submit_batch", lambda *args, **kwargs: calls.append(1) or {}
    )
    monkeypatch.setattr(config, "UBYPORT_MAX_BATCH", 1)
    reporting.release_sendable_claim(token)

    assert reporting._send_claimed_batches(
        {"id": 1}, claimed * 2, token, mode="auto", env=None
    ) == []

    assert calls == []
    assert db.query_one(
        "SELECT 1 AS n FROM submission_claim WHERE guest_id = ?", (gid,)
    ) is None


def test_refresh_does_not_touch_another_workers_claim_and_stale_ones_are_stolen(
    fresh_db,
):
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    assert len(claimed) == 1
    # Our claim ages past the TTL; another worker steals the guest.
    db.execute(
        "UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?",
        (time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS - 5, token),
    )
    other_token, stolen = reporting.claim_sendable(_pairs(gid, rid))
    assert len(stolen) == 1
    before = db.query_one(
        "SELECT claimed_at FROM submission_claim WHERE guest_id = ?", (gid,)
    )["claimed_at"]

    assert reporting.refresh_sendable_claim(token) is False

    row = db.query_one(
        "SELECT claim_token, claimed_at FROM submission_claim WHERE guest_id = ?", (gid,)
    )
    assert (row["claim_token"], row["claimed_at"]) == (other_token, before)
    assert reporting.refresh_sendable_claim(other_token) is True
    reporting.release_sendable_claim(other_token)
