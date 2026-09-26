"""Invoice corrections: storno for non-payers, ODD for payers (invoice step 7)."""
from __future__ import annotations

from datetime import date

import pytest

from app import db, invoices

NAMES = ("Corr Non s.r.o.", "Corr Payer s.r.o.")


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
                "DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE legal_entity_id = ?)",
                (entity_id,),
            )
            db.execute("DELETE FROM invoice WHERE legal_entity_id = ?", (entity_id,))
            db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))
            db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )


def _entity(name, vat="non_payer"):
    return db.insert(
        "legal_entity",
        {"name": name, "seat": "Praha", "ico": "04656679", "registry_entry": "ŽR",
         "vat_status": vat, "invoice_due_days": 14, "created_at": db.utcnow()},
    )


def _draft(entity_id, vat="non_payer"):
    return {
        "legal_entity_id": entity_id, "apartment_id": None, "reservation_id": None,
        "kind": "invoice", "lang": "cs", "vat_status": vat,
        "issue_date": "2026-09-26", "duzp": None, "due_date": None, "paid_on": None, "paid_via": None,
        "seller": {"name": "S", "seat": "Praha", "ico": "04656679", "dic": "CZ1" if vat == "payer" else "",
                   "registry": "ŽR", "bank_account": "", "iban": "", "bic": "", "email": "", "phone": ""},
        "buyer": {"name": "B", "street": "", "city": "", "zip": "", "country": "CZE",
                  "ico": "", "dic": "", "email": ""},
        "stay_from": "2026-09-10", "stay_to": "2026-09-14", "stay_label": "Flat",
        "items": [{"kind": "accommodation", "description": "Ubytování", "quantity": 1, "unit": "pobyt",
                   "vat_rate": 12 if vat == "payer" else None,
                   "base_haler": 357143 if vat == "payer" else None,
                   "vat_haler": 42857 if vat == "payer" else None, "gross_haler": 400000}],
        "total_base_haler": 357143 if vat == "payer" else None,
        "total_vat_haler": 42857 if vat == "payer" else None, "total_haler": 400000,
    }


def test_non_payer_gets_a_storno_with_negative_lines():
    entity_id = _entity(NAMES[0])
    original = invoices.issue(_draft(entity_id), actor_user_id=None)
    new_id = invoices.cancel(original, "Zákazník odstoupil", None, None, today=date(2026, 9, 27))
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (new_id,))
    assert row["kind"] == "storno"
    assert row["number"] == "2026-0002"
    assert row["corrects_invoice_id"] == original
    assert row["total_haler"] == -400000
    item = db.query_one("SELECT * FROM invoice_item WHERE invoice_id = ?", (new_id,))
    assert item["gross_haler"] == -400000


def test_payer_gets_an_odd_with_the_correction_facts():
    entity_id = _entity(NAMES[1], vat="payer")
    original = invoices.issue(_draft(entity_id, vat="payer"), actor_user_id=None)
    new_id = invoices.cancel(
        original, "Oprava ceny", "2026-09-27", None, today=date(2026, 9, 28)
    )
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (new_id,))
    assert row["kind"] == "corrective"
    assert row["correction_reason"] == "Oprava ceny"
    assert row["correction_date"] == "2026-09-27"
    assert row["total_vat_haler"] == -42857


def test_a_second_correction_is_refused():
    entity_id = _entity(NAMES[0])
    original = invoices.issue(_draft(entity_id), actor_user_id=None)
    invoices.cancel(original, "První oprava", None, None, today=date(2026, 9, 27))
    with pytest.raises(Exception):
        invoices.cancel(original, "Druhá oprava", None, None, today=date(2026, 9, 28))


def test_a_short_reason_is_refused():
    entity_id = _entity(NAMES[0])
    original = invoices.issue(_draft(entity_id), actor_user_id=None)
    with pytest.raises(ValueError):
        invoices.cancel(original, "x", None, None, today=date(2026, 9, 27))
