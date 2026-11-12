"""1138: the claim drops a guest whose stay window moved after the list was built."""
from __future__ import annotations

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
