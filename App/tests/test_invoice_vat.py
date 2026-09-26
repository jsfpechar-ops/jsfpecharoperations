"""Invoice VAT arithmetic and draft (invoice step 3)."""
from __future__ import annotations

from datetime import date

import pytest

from app import db, invoices


@pytest.fixture(autouse=True)
def _schema():
    db.init_db()


def _reservation():
    return {
        "id": 1,
        "date_from": "2026-09-10",
        "date_to": "2026-09-14",
        "internal_name": "Flat",
        "declared_guests": None,
        "expected_guests_override": 2,
    }


def _entity(**over):
    row = {
        "id": 1,
        "name": "Seller s.r.o.",
        "seat": "Praha 1",
        "ico": "04656679",
        "dic": "CZ04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "bank_account": "123/0600",
        "iban": "CZ9106000000000000000123",
        "bic": "",
        "contact_email": "s@x.test",
        "contact_phone": "",
        "vat_status": "payer",
        "invoice_due_days": 14,
    }
    row.update(over)
    return row


def test_vat_is_computed_top_down_from_the_gross():
    # 4 000 Kč gross at 12 % -> tax 428.57, base 3 571.43
    base, vat = invoices.vat_split(400000, 12)
    assert vat == 42857
    assert base == 357143
    assert base + vat == 400000


def test_vat_split_returns_none_without_a_rate():
    assert invoices.vat_split(400000, None) == (None, None)


def test_draft_for_a_payer_has_base_and_vat():
    form = {
        "price_czk": "4000",
        "buyer_name": "Buyer",
        "buyer_country": "CZE",
        "already_paid": "1",
        "lang": "cs",
    }
    draft = invoices.build_draft(_reservation(), _entity(), form, "cs", today=date(2026, 9, 26))
    assert draft["total_haler"] == 400000
    assert draft["total_vat_haler"] == 42857
    assert draft["total_base_haler"] == 357143
    assert draft["items"][0]["vat_rate"] == 12
    assert draft["paid_on"] == "2026-09-14"


def test_draft_for_a_non_payer_has_no_vat_columns():
    form = {"price_czk": "4000", "buyer_name": "Buyer", "lang": "cs"}
    draft = invoices.build_draft(
        _reservation(), _entity(vat_status="non_payer"), form, "cs", today=date(2026, 9, 26)
    )
    assert draft["vat_status"] == "non_payer"
    assert draft["total_base_haler"] is None
    assert draft["total_vat_haler"] is None
    assert draft["items"][0]["vat_rate"] is None


def test_validate_for_issue_flags_the_missing_legal_minimum():
    draft = {
        "seller": {"seat": "", "registry": "", "dic": ""},
        "buyer": {"name": ""},
        "vat_status": "payer",
        "total_haler": 0,
    }
    fields = {issue.field for issue in invoices.validate_for_issue(draft)}
    assert {"seller_seat", "seller_registry", "seller_dic", "buyer_name", "price_czk"} <= fields


def test_a_valid_draft_has_no_issue_blockers():
    draft = {
        "seller": {"seat": "Praha", "registry": "ŽR", "dic": "CZ1"},
        "buyer": {"name": "B"},
        "vat_status": "payer",
        "total_haler": 100,
    }
    assert invoices.validate_for_issue(draft) == []
