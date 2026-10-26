"""Brief 0413: UbyHost's own invoices. Numbering, PDF, storno, payment, mail, purge."""
from __future__ import annotations

import json
import secrets
from datetime import date

import pytest

from app import billing, billing_invoices, config, db, mail, retention

# Tests issue in 2099 so their numbers never meet a real sequence.
DAY = date(2099, 3, 2)


def _user() -> int:
    return db.insert(
        "user_account",
        {"username": f"inv-{secrets.token_hex(4)}", "password_hash": "x", "created_at": db.utcnow()},
    )


def _cleanup(owner_id: int) -> None:
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM bank_payment WHERE vs LIKE '2099%' OR vs LIKE '2010%'")
    db.execute(
        "DELETE FROM platform_invoice WHERE owner_user_id = ? AND corrects_id IS NOT NULL", (owner_id,)
    )
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM platform_invoice_sequence WHERE year IN (2010, 2099)")
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def owner(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    monkeypatch.setattr(config, "BILLING_BANK_ACCOUNT", "123456789/0300")
    monkeypatch.setattr(config, "BILLING_VAT_STATUS", "non_payer")
    owner_id = _user()
    billing.ensure_account(owner_id)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 5, buyer_name = 'Penzion Test s.r.o.', buyer_street = 'Hlavní 1', "
        "buyer_city = 'Brno', buyer_zip = '60200', buyer_ico = '12345678', "
        "buyer_email = 'fakturace@example.cz' WHERE owner_user_id = ?",
        (owner_id,),
    )
    yield owner_id
    _cleanup(owner_id)


def test_number_and_vs_never_repeat_across_years():
    assert billing_invoices.number_for(2026, 42) == ("UBY-2026-0042", "20260042")
    assert billing_invoices.number_for(2027, 42)[1] != billing_invoices.number_for(2026, 42)[1]


def test_apartment_words_are_czech_plurals():
    assert [billing_invoices.apartments_cs(n) for n in (1, 3, 5)] == [
        "1 apartmán", "3 apartmány", "5 apartmánů",
    ]


def test_period_items_follow_the_price_list(owner):
    acc = billing.account(owner)
    acc.update(plan="max", addon_whitelabel=1, carry_czk=30)
    items = billing_invoices.period_items(acc)
    assert items[0] == ("Předplatné UbyHost Max, 5 apartmánů", 715 + 375)
    assert ("Doplněk vlastní značka", 590) in items
    assert ("Doplatek za změny v minulém období", 30) in items
    assert not any("TTLock" in d for d, _ in items)  # included in Max


def test_founder_line_on_an_annual_plan(owner):
    acc = billing.account(owner)
    acc.update(billing_interval="year", founder=1, apartments_billed=2)
    assert billing_invoices.period_items(acc) == [
        ("Předplatné UbyHost Standard, 2 apartmány, zakladatelská cena", 1780),
    ]


def test_period_invoice_is_numbered_stored_and_issued_once(owner):
    db.execute("UPDATE billing_account SET carry_czk = 20 WHERE owner_user_id = ?", (owner,))
    first = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    again = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    assert first == again
    row = billing_invoices.get(first)
    assert row["number"] == "UBY-2099-0001" and row["vs"] == "20990001"
    assert row["total_haler"] == (715 + 20) * 100
    assert row["due_date"] == "2099-03-16"
    assert billing_invoices.pdf_bytes(first).startswith(b"%PDF")
    snap = json.loads(row["snapshot_json"])
    assert snap["invoice"]["buyer_name"] == "Penzion Test s.r.o."
    assert snap["invoice"]["kind"] == "invoice"
    assert billing.account(owner)["carry_czk"] == 0


def test_supplementary_prints_as_an_invoice_and_needs_50_kc(owner):
    with pytest.raises(ValueError):
        billing_invoices.issue_supplementary(
            owner, amount_czk=49, description="x", period_from="2099-03-02",
            period_to="2100-03-01", today=DAY,
        )
    new_id = billing_invoices.issue_supplementary(
        owner, amount_czk=120, description="Doplatek: Max od 2. 3. 2099",
        period_from="2099-03-02", period_to="2100-03-01", today=DAY,
    )
    row = billing_invoices.get(new_id)
    assert row["kind"] == "supplementary"
    assert json.loads(row["snapshot_json"])["invoice"]["kind"] == "invoice"


def test_missing_buyer_stops_issuing(owner):
    db.execute("UPDATE billing_account SET buyer_name = NULL WHERE owner_user_id = ?", (owner,))
    with pytest.raises(ValueError, match="buyer_missing"):
        billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)


def test_storno_voids_and_frees_the_period(owner):
    first = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    cancel = billing_invoices.storno(first, reason="Chybný počet apartmánů", today=DAY)
    assert billing_invoices.get(first)["voided"] == 1
    st = billing_invoices.get(cancel)
    assert st["kind"] == "storno" and st["total_haler"] == -71500 and st["corrects_id"] == first
    second = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    assert second not in (first, cancel)
    with pytest.raises(ValueError):
        billing_invoices.storno(first, reason="again", today=DAY)


def test_mark_paid_once_and_never_a_paid_storno(owner):
    first = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    assert billing_invoices.mark_paid(first, paid_on="2099-03-05", via="bank_manual", actor="admin")
    assert not billing_invoices.mark_paid(first, paid_on="2099-03-06", via="bank_auto")
    assert billing_invoices.get(first)["paid_on"] == "2099-03-05"
    with pytest.raises(ValueError, match="paid"):
        billing_invoices.storno(first, reason="x", today=DAY)


def test_send_queues_one_service_mail_with_the_pdf(owner, monkeypatch):
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    first = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    billing_invoices.send(first)
    billing_invoices.send(first)
    rows = db.query("SELECT * FROM email_outbox WHERE owner_user_id = ?", (owner,))
    assert len(rows) == 1
    assert rows[0]["kind"] == "billing_invoice"
    assert rows[0]["to_email"] == "fakturace@example.cz"
    assert "UBY-2099-0001" in rows[0]["subject"]
    parts = mail.attachments(json.loads(rows[0]["payload"]))
    assert parts[0]["filename"] == "UBY-2099-0001.pdf"
    assert parts[0]["data"].startswith(b"%PDF")


def test_billing_invoice_is_host_service_mail():
    assert "billing_invoice" in mail.HOST_KINDS
    assert "billing_invoice" not in mail.LIFECYCLE_KINDS


def test_purge_keeps_ten_full_years(owner):
    old = billing_invoices.issue(
        owner, kind="invoice", period_from="2010-05-01", period_to="2010-05-31",
        items=[("x", 100)], issue_date=date(2010, 5, 1),
    )
    db.execute(
        "INSERT INTO bank_payment (bank_tx_id, received_on, amount_haler, vs, status) "
        "VALUES ('test-0413-old', '2010-05-03', 10000, '20100001', 'unmatched')"
    )
    kept = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    assert billing_invoices.expired_ids(date(2020, 12, 31)) == []
    assert billing_invoices.expired_ids(date(2021, 1, 1)) == [old]
    assert retention.STEPS and "platform_invoices" in [name for name, _ in retention.STEPS]
    assert billing_invoices.purge_expired(date(2021, 1, 1)) == 2
    assert billing_invoices.get(old) is None
    assert billing_invoices.get(kept) is not None


def test_workspace_deletion_keeps_the_invoice(owner):
    first = billing_invoices.issue_for_period(owner, "2099-03-02", "2099-04-01", today=DAY)
    retention._delete_workspace(owner)
    row = billing_invoices.get(first)
    assert row["owner_user_id"] is None
    assert billing_invoices.pdf_bytes(first).startswith(b"%PDF")
    db.execute("DELETE FROM platform_invoice WHERE id = ?", (first,))
