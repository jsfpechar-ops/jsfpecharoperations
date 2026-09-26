"""Invoice immutability: an issued document never changes (invoice step 1)."""
from __future__ import annotations

import pytest

from app import db


@pytest.fixture(autouse=True)
def _schema():
    db.init_db()


def _entity(name="Inv Test") -> int:
    return db.insert("legal_entity", {"name": name, "created_at": db.utcnow()})


def _invoice(entity_id: int, n: int = 1) -> int:
    now = db.utcnow()
    return db.insert(
        "invoice",
        {
            "legal_entity_id": entity_id,
            "kind": "invoice",
            "seq_year": 2026,
            "seq_no": n,
            "number": f"2026-{n:04d}",
            "vs": f"2026{n:04d}",
            "lang": "cs",
            "vat_status": "non_payer",
            "issue_date": "2026-09-26",
            "seller_name": "E",
            "seller_seat": "Praha",
            "buyer_name": "B",
            "total_haler": 100,
            "created_at": now,
            "issued_at": now,
        },
    )


def test_issued_rows_reject_content_updates():
    invoice_id = _invoice(_entity("Imm Update"))
    for column in ("buyer_name", "total_haler", "pdf_blob"):
        with pytest.raises(Exception):
            db.execute(f"UPDATE invoice SET {column} = ? WHERE id = ?", ("X", invoice_id))


def test_bookkeeping_updates_are_allowed():
    invoice_id = _invoice(_entity("Imm Bookkeeping"))
    db.execute("UPDATE invoice SET marked_paid_at = ? WHERE id = ?", (db.utcnow(), invoice_id))
    assert db.query_one(
        "SELECT marked_paid_at FROM invoice WHERE id = ?", (invoice_id,)
    )["marked_paid_at"]


def test_items_of_an_issued_invoice_are_frozen():
    invoice_id = _invoice(_entity("Imm Items"))
    with pytest.raises(Exception):
        db.execute(
            "INSERT INTO invoice_item (invoice_id, position, kind, description, gross_haler) "
            "VALUES (?, 1, 'other', 'x', 10)",
            (invoice_id,),
        )


def test_deleting_an_issued_invoice_is_refused_without_the_unlock():
    invoice_id = _invoice(_entity("Imm Delete"))
    with pytest.raises(Exception):
        db.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))


def test_immediate_commits_and_rolls_back():
    with db.immediate() as cur:
        cur.execute(
            "INSERT INTO legal_entity (name, created_at) VALUES ('Immediate', ?)",
            (db.utcnow(),),
        )
    assert db.query_one("SELECT 1 AS x FROM legal_entity WHERE name = 'Immediate'")

    with pytest.raises(RuntimeError):
        with db.immediate() as cur:
            cur.execute(
                "INSERT INTO legal_entity (name, created_at) VALUES ('RolledBack', ?)",
                (db.utcnow(),),
            )
            raise RuntimeError("boom")
    assert db.query_one("SELECT 1 AS x FROM legal_entity WHERE name = 'RolledBack'") is None
