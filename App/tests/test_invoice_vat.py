"""Invoice VAT arithmetic and the free-form draft (standalone model)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app import db, invoices


@pytest.fixture(autouse=True)
def _schema():
    db.init_db()


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


def _form(**over):
    form = {
        "buyer_name": "Buyer",
        "buyer_country": "CZE",
        "already_paid": "1",
        "lang": "cs",
        "item_description": ["Consulting"],
        "item_quantity": ["2"],
        "item_unit": ["h"],
        "item_unit_price": ["1000"],
        "item_vat_rate": ["21"],
    }
    form.update(over)
    return form


def test_vat_is_added_on_top_of_the_net_unit_price():
    base, vat, gross = invoices.vat_parts(2, Decimal("1000"), 21)
    assert base == 200000
    assert vat == 42000
    assert gross == 242000
    assert base + vat == gross


def test_zero_rate_is_allowed():
    base, vat, gross = invoices.vat_parts(1, Decimal("500"), 0)
    assert vat == 0
    assert gross == base == 50000


def test_draft_for_a_payer_has_base_and_vat_per_line():
    draft = invoices.build_draft(_entity(), _form(), "cs", today=date(2026, 9, 26))
    assert draft["total_haler"] == 242000
    assert draft["total_vat_haler"] == 42000
    assert draft["total_base_haler"] == 200000
    assert draft["items"][0]["vat_rate"] == 21
    assert draft["paid_on"] == "2026-09-26"


def test_draft_for_a_non_payer_has_no_vat_columns():
    draft = invoices.build_draft(
        _entity(vat_status="non_payer"), _form(), "cs", today=date(2026, 9, 26)
    )
    assert draft["vat_status"] == "non_payer"
    assert draft["total_base_haler"] is None
    assert draft["total_vat_haler"] is None
    assert draft["total_haler"] == 200000
    assert draft["items"][0]["vat_rate"] is None


def test_unlimited_line_items_are_collected():
    form = _form(
        item_description=["A", "B", "C", "D"],
        item_quantity=["1", "2", "3", "4"],
        item_unit_price=["100", "100", "100", "100"],
        item_vat_rate=["0", "0", "0", "0"],
    )
    draft = invoices.build_draft(
        _entity(vat_status="non_payer"), form, "cs", today=date(2026, 9, 26)
    )
    assert len(draft["items"]) == 4
    assert draft["total_haler"] == (1 + 2 + 3 + 4) * 100 * 100


def test_validate_flags_the_legal_minimum_and_missing_items():
    draft = {
        "seller": {"name": "", "seat": "", "registry": "", "dic": ""},
        "buyer": {"name": ""},
        "vat_status": "payer",
        "items": [],
        "total_haler": 0,
    }
    fields = {issue.field for issue in invoices.validate_for_issue(draft)}
    assert {"seller_name", "seller_seat", "seller_registry", "seller_dic", "buyer_name", "items", "price_czk"} <= fields


def test_a_valid_draft_has_no_issue_blockers():
    draft = {
        "seller": {"name": "S", "seat": "Praha", "registry": "ŽR", "dic": "CZ1"},
        "buyer": {"name": "B"},
        "vat_status": "payer",
        "items": [{"kind": "other", "gross_haler": 100}],
        "total_haler": 100,
    }
    assert invoices.validate_for_issue(draft) == []
