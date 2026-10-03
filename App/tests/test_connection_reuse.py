"""WP14: one database connection per thread, with unchanged transaction semantics.

Every test here runs on its own temporary database, so the shared test
database and its fixtures are never touched.
"""
from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import config, db, invoices, reporting


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db.close_connections()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "wp14.sqlite3")
    db.init_db()
    db.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, n INTEGER NOT NULL)")
    db.execute("INSERT INTO counter (id, n) VALUES (1, 0)")
    yield tmp_path
    db.close_connections()


def _thread_conn():
    return db._thread_conn()


# --- reuse and keying ---------------------------------------------------------


def test_helpers_reuse_one_connection_per_thread(fresh_db, monkeypatch):
    opened = []
    real_open = db._open

    def counting_open(*args, **kwargs):
        conn = real_open(*args, **kwargs)
        opened.append(threading.get_ident())
        return conn

    db.close_connections()
    monkeypatch.setattr(db, "_open", counting_open)
    for _ in range(20):
        db.query("SELECT 1 AS x")
        db.execute("UPDATE counter SET n = n + 1 WHERE id = 1")
    assert opened == [threading.get_ident()]

    def other_thread():
        db.query_one("SELECT n FROM counter WHERE id = 1")
        return _thread_conn()

    with ThreadPoolExecutor(max_workers=1) as pool:
        theirs = pool.submit(other_thread).result()
    assert theirs is not _thread_conn()
    assert len(opened) == 2
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 20


def test_changing_db_path_switches_connection(fresh_db, monkeypatch):
    first = _thread_conn()
    db.insert("settings", {"key": "where", "value": "first"})

    monkeypatch.setattr(config, "DB_PATH", fresh_db / "second.sqlite3")
    db.init_db()
    assert db.get_setting("where") is None
    assert _thread_conn() is not first
    db.set_setting("where", "second")

    monkeypatch.setattr(config, "DB_PATH", fresh_db / "wp14.sqlite3")
    assert db.get_setting("where") == "first"


def test_a_replaced_database_file_is_reopened(fresh_db):
    db.set_setting("marker", "old")
    path = config.DB_PATH
    replacement = fresh_db / "replacement.sqlite3"
    conn = sqlite3.connect(replacement)
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO settings VALUES ('marker', 'new')")
    conn.commit()
    conn.close()
    replacement.replace(path)
    for suffix in ("-wal", "-shm"):
        stale = path.with_name(path.name + suffix)
        if stale.exists():
            stale.unlink()
    assert db.get_setting("marker") == "new"


def test_close_connections_reopens_on_next_use(fresh_db):
    conn = _thread_conn()
    db.close_connections()
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 0


# --- transaction semantics ----------------------------------------------------


def test_no_transaction_is_left_open(fresh_db):
    conn = _thread_conn()
    db.query("SELECT * FROM counter")
    assert not conn.in_transaction
    db.update("counter", 1, {"n": 5})
    assert not conn.in_transaction
    with db.immediate() as cur:
        cur.execute("UPDATE counter SET n = n + 1 WHERE id = 1")
        assert conn.in_transaction
    assert not conn.in_transaction
    with db.cursor() as cur:
        cur.execute("UPDATE counter SET n = n + 1 WHERE id = 1")
    assert not conn.in_transaction
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 7


def test_an_error_inside_immediate_rolls_back_and_keeps_the_connection(fresh_db):
    conn = _thread_conn()
    with pytest.raises(RuntimeError):
        with db.immediate() as cur:
            cur.execute("UPDATE counter SET n = 99 WHERE id = 1")
            raise RuntimeError("boom")
    assert not conn.in_transaction
    assert _thread_conn() is conn
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 0
    with pytest.raises(sqlite3.IntegrityError):
        with db.immediate() as cur:
            cur.execute("UPDATE counter SET n = 1 WHERE id = 1")
            cur.execute("INSERT INTO counter (id, n) VALUES (1, 1)")
    assert not conn.in_transaction
    db.execute("UPDATE counter SET n = 3 WHERE id = 1")
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 3


def test_a_helper_that_opens_a_transaction_is_rolled_back(fresh_db):
    conn = _thread_conn()
    with pytest.raises(RuntimeError, match="left a transaction open"):
        db.execute("BEGIN")
    assert not conn.in_transaction
    db.execute("UPDATE counter SET n = 4 WHERE id = 1")
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 4


def test_a_helper_inside_a_block_does_not_join_its_transaction(fresh_db):
    """As before sharing: a helper inside a block has a connection of its own."""
    with db.immediate() as cur:
        cur.execute("UPDATE counter SET n = 42 WHERE id = 1")
        # A separate connection still reads the committed value.
        assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 0
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 42


def test_a_nested_read_block_uses_its_own_connection(fresh_db):
    with db.immediate() as outer:
        outer.execute("UPDATE counter SET n = 8 WHERE id = 1")
        with db.cursor() as inner:
            inner.execute("SELECT n FROM counter WHERE id = 1")
            assert inner.fetchone()["n"] == 0
    assert not _thread_conn().in_transaction
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 8


def test_execute_reports_an_id_only_for_a_row_it_inserted(fresh_db):
    new_id = db.execute("INSERT INTO counter (n) VALUES (1)")
    assert new_id > 1
    # A fresh connection reported 0 here; the shared one must too.
    assert db.execute("INSERT OR IGNORE INTO counter (id, n) VALUES (1, 0)") == 0
    assert db.execute("UPDATE counter SET n = n + 1 WHERE id = 1") == 0
    assert db.execute("DELETE FROM counter WHERE id = ?", (new_id,)) == 0
    assert db.execute_rowcount("UPDATE counter SET n = 0") == 1


# --- concurrency ----------------------------------------------------------------


def _run_threads(target, count):
    barrier = threading.Barrier(count)
    errors = []
    results = [None] * count

    def run(index):
        try:
            barrier.wait()
            results[index] = target(index)
        except Exception as exc:  # collected for the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors, errors
    return results


def test_concurrent_read_modify_write_blocks_lose_no_update(fresh_db):
    per_thread = 25

    def work(_index):
        for _ in range(per_thread):
            with db.immediate() as cur:
                cur.execute("SELECT n FROM counter WHERE id = 1")
                value = cur.fetchone()["n"]
                cur.execute("UPDATE counter SET n = ? WHERE id = 1", (value + 1,))
            # Autocommit writes from the same threads, interleaved.
            db.insert("audit", {"at": db.utcnow(), "actor": "t", "action": "wp14", "detail": ""})
            assert not _thread_conn().in_transaction

    _run_threads(work, 8)
    assert db.query_one("SELECT n FROM counter WHERE id = 1")["n"] == 8 * per_thread
    assert db.query_one("SELECT COUNT(*) AS n FROM audit WHERE action = 'wp14'")["n"] == 8 * per_thread
    assert all(not conn.in_transaction for conn in list(db._registry))


def _draft(entity_id):
    return {
        "legal_entity_id": entity_id, "apartment_id": None, "reservation_id": None,
        "kind": "invoice", "lang": "cs", "vat_status": "non_payer",
        "issue_date": "2026-09-26", "duzp": None, "due_date": None,
        "paid_on": None, "paid_via": None,
        "seller": {
            "name": "Seller", "seat": "Praha", "ico": "04656679", "dic": "", "registry": "ŽR",
            "bank_account": "", "iban": "", "bic": "", "email": "", "phone": "",
        },
        "buyer": {
            "name": "Buyer", "street": "", "city": "", "zip": "", "country": "CZE",
            "ico": "", "dic": "", "email": "",
        },
        "stay_from": "2026-09-10", "stay_to": "2026-09-14", "stay_label": "Flat",
        "items": [{
            "kind": "accommodation", "description": "Ubytování", "quantity": 1, "unit": "pobyt",
            "vat_rate": None, "base_haler": None, "vat_haler": None, "gross_haler": 10000,
        }],
        "total_base_haler": None, "total_vat_haler": None, "total_haler": 10000,
    }


def test_concurrent_invoice_numbering_has_no_gaps_or_duplicates(fresh_db):
    entity_id = db.insert("legal_entity", {
        "name": "WP14 Test s.r.o.", "seat": "Praha", "ico": "04656679",
        "registry_entry": "ŽR", "vat_status": "non_payer", "invoice_due_days": 14,
        "created_at": db.utcnow(),
    })

    def work(_index):
        return [invoices.issue(_draft(entity_id), actor_user_id=None) for _ in range(4)]

    ids = [invoice_id for batch in _run_threads(work, 8) for invoice_id in batch]
    numbers = sorted(
        row["seq_no"] for row in db.query(
            "SELECT seq_no FROM invoice WHERE legal_entity_id = ?", (entity_id,)
        )
    )
    assert len(set(ids)) == 32
    assert numbers == list(range(1, 33))


def test_concurrent_claim_sendable_leases_each_guest_once(fresh_db):
    now = db.utcnow()
    apartment_id = db.insert("apartment", {"internal_name": "WP14 flat", "created_at": now})
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "wp14", "date_from": "2026-09-10",
        "date_to": "2026-09-12", "created_at": now, "updated_at": now,
    })
    for _ in range(30):
        db.insert("guest", {"reservation_id": reservation_id, "created_at": now, "updated_at": now})
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    pairs = [
        (guest, reservation)
        for guest in db.query("SELECT * FROM guest WHERE reservation_id = ?", (reservation_id,))
    ]

    def work(_index):
        _token, claimed = reporting.claim_sendable(pairs)
        return [guest["id"] for guest, _reservation in claimed]

    claimed = [guest_id for batch in _run_threads(work, 8) for guest_id in batch]
    assert sorted(claimed) == sorted(guest["id"] for guest, _r in pairs)
    assert len(claimed) == len(set(claimed)) == 30
