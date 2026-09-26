"""The invoice PDF renders (invoice step 4)."""
from __future__ import annotations

from app import invoice_pdf

ACCOM = {
    "description": "Ubytování – Byt, 2026-09-10 – 2026-09-14, 4 nocí, 2 os.",
    "quantity": 1,
    "vat_rate": 12,
    "base_haler": 357143,
    "vat_haler": 42857,
    "gross_haler": 400000,
}


def _inv(**over):
    row = {
        "number": "2026-0001", "vs": "20260001", "kind": "invoice",
        "vat_status": "non_payer", "issue_date": "2026-09-26",
        "seller_name": "Seller s.r.o.", "seller_seat": "Korunní 1, Praha",
        "seller_ico": "04656679", "seller_dic": "", "seller_registry": "ŽR",
        "seller_bank_account": "123/0600", "seller_iban": "CZ9106000000000000000123",
        "seller_bic": "", "seller_email": "s@x.test", "seller_phone": "",
        "buyer_name": "Buyer", "buyer_street": "Baker 1", "buyer_city": "London",
        "buyer_zip": "SW1", "buyer_country": "GBR", "buyer_ico": "", "buyer_dic": "",
        "total_haler": 400000, "stay_label": "Byt", "paid_on": None,
        "due_date": "2026-10-10", "duzp": None,
        "buyer_country_name": "Velká Británie", "paid_via_label": None,
        "corrects_number": None, "correction_reason": None, "correction_date": None,
    }
    row.update(over)
    return row


def test_non_payer_renders_a_pdf_with_the_ubyhost_credit():
    data = invoice_pdf.render(_inv(), [dict(ACCOM, vat_rate=None, base_haler=None, vat_haler=None)], "cs")
    assert data.startswith(b"%PDF")
    assert b"ubyhost.com/?utm_source=invoice" in data


def test_payer_renders_with_the_vat_recap():
    data = invoice_pdf.render(_inv(vat_status="payer", seller_dic="CZ04656679"), [dict(ACCOM)], "en")
    assert data.startswith(b"%PDF")


def test_preview_renders_a_pdf():
    data = invoice_pdf.render(_inv(), [dict(ACCOM, vat_rate=None)], "cs", preview=True)
    assert data.startswith(b"%PDF")


def test_storno_and_corrective_render():
    for kind in ("storno", "corrective"):
        data = invoice_pdf.render(
            _inv(kind=kind, correction_reason="Chyba", corrects_number="2026-0001",
                 correction_date="2026-09-27", total_haler=-400000),
            [dict(ACCOM, gross_haler=-400000)],
            "cs",
        )
        assert data.startswith(b"%PDF")
