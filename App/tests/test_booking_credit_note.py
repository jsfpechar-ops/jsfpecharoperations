"""0901: a partial refund of a site booking issues a credit note for the refunded amount."""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app import booking_cancel, booking_site, db, invoices, property_page
from app.main import app
from tests.test_booking_cancel import PRAGUE, _paid, refunds, site  # noqa: F401

PARTIAL_NOW = datetime(2027, 6, 8, 12, 0, tzinfo=PRAGUE)


def _rows(site):
    return db.query("SELECT * FROM invoice WHERE legal_entity_id = ? ORDER BY id", (site["entity"],))


def _corrections(site):
    return [r for r in _rows(site) if r["corrects_invoice_id"]]


def _items(invoice_id):
    return db.query("SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY position", (invoice_id,))


def test_partial_refund_issues_one_storno_for_the_refunded_amount(site, refunds):
    bid = _paid(site, "moderate")
    original = _rows(site)[0]
    before = dict(original)
    res = booking_cancel.cancel(bid, by_host=False, now=PARTIAL_NOW)
    refund = res["refund_czk"]
    assert res["error"] is None and 0 < refund < int(booking_site.get(bid)["total_czk"])
    (correction,) = _corrections(site)
    assert correction["kind"] == "storno"
    assert correction["corrects_invoice_id"] == original["id"]
    assert correction["total_haler"] == -refund * 100
    assert [i["gross_haler"] for i in _items(correction["id"])] == [-refund * 100]
    assert dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (original["id"],))) == before


def test_partial_refund_for_a_payer_is_a_corrective_document_with_vat(site, refunds):
    db.execute("UPDATE legal_entity SET vat_status = 'payer', dic = 'CZ04656679' WHERE id = ?", (site["entity"],))
    bid = _paid(site, "moderate")
    original = _rows(site)[0]
    res = booking_cancel.cancel(bid, by_host=False, now=PARTIAL_NOW)
    (correction,) = _corrections(site)
    assert correction["kind"] == "corrective"
    assert correction["total_base_haler"] + correction["total_vat_haler"] == correction["total_haler"]
    assert correction["total_haler"] == -res["refund_czk"] * 100
    assert _items(correction["id"])[0]["vat_rate"] == _items(original["id"])[0]["vat_rate"]


def test_full_refund_keeps_the_storno_of_every_item(site, refunds):
    bid = _paid(site, "moderate")
    original = _rows(site)[0]
    n_items = len(_items(original["id"]))
    assert booking_cancel.cancel(bid, by_host=True)["error"] is None
    (correction,) = _corrections(site)
    assert correction["total_haler"] == -original["total_haler"]
    assert len(_items(correction["id"])) == n_items


def test_second_correction_is_refused_and_creates_no_row(site, refunds):
    bid = _paid(site, "moderate")
    original = _rows(site)[0]
    booking_cancel.cancel(bid, by_host=False, now=PARTIAL_NOW)
    with pytest.raises(ValueError, match="already_corrected"):
        invoices.correct_partial(original["id"], 10, "Second partial refund", None,
                                 today=date(2027, 6, 8))
    assert len(_corrections(site)) == 1
    assert booking_cancel.cancel(bid, by_host=False, now=PARTIAL_NOW)["error"] == "not_cancellable"
    assert len(_corrections(site)) == 1


def test_failed_correction_never_blocks_the_refund(site, refunds, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(invoices, "correct_partial", boom)
    bid = _paid(site, "moderate")
    res = booking_cancel.cancel(bid, by_host=False, now=PARTIAL_NOW)
    assert res["error"] is None
    assert booking_site.get(bid)["status"] == "refunded"
    assert len(refunds.created) == 1
    assert any(m["kind"] == "site_booking_refunded" for m in site["sent"])
    assert db.query_one("SELECT id FROM audit WHERE action = ? AND owner_user_id = ?",
                        ("site_invoice_needs_correction", site["oid"])) is not None
    assert _corrections(site) == []


def test_correction_pdf_route(site, refunds):
    bid = _paid(site, "moderate")
    slug = property_page.ensure_slug(site["aid"])["slug"]
    token = booking_site.manage_token(bid)
    base = f"/p/{slug}/b/{bid}/{token}"
    client = TestClient(app)
    assert client.get(base + "/correction.pdf").status_code == 404
    booking_cancel.cancel(bid, by_host=False, now=PARTIAL_NOW)
    ok = client.get(base + "/correction.pdf")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "application/pdf"
    assert ok.content.startswith(b"%PDF")
    assert client.get(f"/p/{slug}/b/{bid}/{'0' * len(token)}/correction.pdf").status_code == 404
