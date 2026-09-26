"""Invoice numbering: per entity, gap-free, concurrent-safe (invoice step 5)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from app import db, invoices

NAMES = ("Num Test s.r.o.", "Prefix Test s.r.o.", "Year Test s.r.o.", "Boom Test s.r.o.")


@pytest.fixture(autouse=True)
def _clean():
    db.init_db()
    yield
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    for name in NAMES:
        ids = [r["id"] for r in db.query("SELECT id FROM legal_entity WHERE name = ?", (name,))]
        for entity_id in ids:
            db.execute(
                "DELETE FROM invoice_item WHERE invoice_id IN "
                "(SELECT id FROM invoice WHERE legal_entity_id = ?)",
                (entity_id,),
            )
            db.execute("DELETE FROM invoice WHERE legal_entity_id = ?", (entity_id,))
            db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))
            db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )


def _entity(name, **over):
    values = {
        "name": name,
        "seat": "Praha",
        "ico": "04656679",
        "registry_entry": "ŽR",
        "vat_status": "non_payer",
        "invoice_due_days": 14,
        "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def _draft(entity_id, **over):
    draft = {
        "legal_entity_id": entity_id,
        "apartment_id": None,
        "reservation_id": None,
        "kind": "invoice",
        "lang": "cs",
        "vat_status": "non_payer",
        "issue_date": "2026-09-26",
        "duzp": None,
        "due_date": None,
        "paid_on": None,
        "paid_via": None,
        "seller": {
            "name": "Seller", "seat": "Praha", "ico": "04656679", "dic": "", "registry": "ŽR",
            "bank_account": "", "iban": "", "bic": "", "email": "", "phone": "",
        },
        "buyer": {
            "name": "Buyer", "street": "", "city": "", "zip": "", "country": "CZE",
            "ico": "", "dic": "", "email": "",
        },
        "stay_from": "2026-09-10", "stay_to": "2026-09-14", "stay_label": "Flat",
        "items": [
            {
                "kind": "accommodation", "description": "Ubytování", "quantity": 1, "unit": "pobyt",
                "vat_rate": None, "base_haler": None, "vat_haler": None, "gross_haler": 10000,
            }
        ],
        "total_base_haler": None, "total_vat_haler": None, "total_haler": 10000,
    }
    draft.update(over)
    return draft


def test_first_invoice_is_2026_0001():
    entity_id = _entity(NAMES[0])
    invoice_id = invoices.issue(_draft(entity_id), actor_user_id=None)
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    assert row["number"] == "2026-0001"
    assert row["vs"] == "20260001"
    assert row["pdf_blob"]


def test_prefix_is_prepended():
    entity_id = _entity(NAMES[1], invoice_prefix="UB")
    invoice_id = invoices.issue(_draft(entity_id), actor_user_id=None)
    assert db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"] == "UB2026-0001"


def test_the_series_restarts_each_year():
    entity_id = _entity(NAMES[2])
    first = invoices.issue(_draft(entity_id), actor_user_id=None)
    second = invoices.issue(_draft(entity_id, issue_date="2027-01-05"), actor_user_id=None)
    assert db.query_one("SELECT number FROM invoice WHERE id = ?", (first,))["number"] == "2026-0001"
    assert db.query_one("SELECT number FROM invoice WHERE id = ?", (second,))["number"] == "2027-0001"


def test_one_time_continuation_is_used_and_cleared():
    entity_id = _entity(NAMES[0], invoice_next_number=8, invoice_next_number_year=2026)
    invoice_id = invoices.issue(_draft(entity_id), actor_user_id=None)
    assert db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"] == "2026-0008"
    row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["invoice_next_number"] is None
    assert row["invoice_next_number_year"] is None


def test_twenty_concurrent_issues_get_consecutive_numbers():
    entity_id = _entity(NAMES[0])

    def one(_):
        return invoices.issue(_draft(entity_id), actor_user_id=None)

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(one, range(20)))
    numbers = [
        db.query_one("SELECT seq_no FROM invoice WHERE id = ?", (i,))["seq_no"] for i in ids
    ]
    assert sorted(numbers) == list(range(1, 21))


def test_a_pdf_failure_does_not_consume_the_number(monkeypatch):
    entity_id = _entity(NAMES[3])

    def boom(*_args, **_kwargs):
        raise RuntimeError("render exploded")

    monkeypatch.setattr(invoices.invoice_pdf, "render", boom)
    with pytest.raises(RuntimeError):
        invoices.issue(_draft(entity_id), actor_user_id=None)

    monkeypatch.undo()
    invoice_id = invoices.issue(_draft(entity_id), actor_user_id=None)
    assert db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"] == "2026-0001"
