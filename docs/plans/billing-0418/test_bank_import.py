"""Brief 0418: ČSOB statement import. GPC and CSV parsing, matching by VS and amount, repeats, settling."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest

from app import bank_import, billing, billing_invoices, config, db

TODAY = date.today()


def _user() -> int:
    return db.insert("user_account", {"username": f"bank-{secrets.token_hex(4)}", "password_hash": "x",
                                      "created_at": db.utcnow(), "email": "bank@example.cz"})


@pytest.fixture
def invoice(monkeypatch):
    """One host on a monthly plan with this period's invoice issued: (owner, invoice row)."""
    db.init_db()
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    owner = _user()
    db.insert("apartment", {"internal_name": "Bank 1", "owner_user_id": owner, "created_at": db.utcnow()})
    billing.ensure_account(owner)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 1, period_start = ?, period_end = ?, buyer_name = 'Penzion Banka', "
        "buyer_street = 'Hlavní 2', buyer_city = 'Brno', buyer_zip = '60200', buyer_email = 'bank@example.cz' "
        "WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), owner),
    )
    invoice_id = billing_invoices.issue_for_period(owner, TODAY.isoformat(),
                                                   (TODAY + timedelta(days=29)).isoformat(), today=TODAY)
    yield owner, dict(billing_invoices.get(invoice_id))
    db.execute("DELETE FROM bank_payment WHERE matched_invoice_id IN "
               "(SELECT id FROM platform_invoice WHERE owner_user_id = ?)", (owner,))
    db.execute("DELETE FROM bank_payment WHERE message = 'TEST 0418'")
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


def _tx() -> int:
    return 10**9 + secrets.randbelow(10**9)


def _gpc(*lines: str) -> bytes:
    header = ("074" + "0000000123456789" + "UBYHOST S.R.O.".ljust(20)).ljust(128)
    return "\r\n".join([header, *lines]).encode("cp1250")


def _gpc_line(tx: int, amount_haler: int, vs: str, *, code: str = "2", day: date = TODAY) -> str:
    d = day.strftime("%d%m%y")
    line = ("075" + "0000000123456789" + "0000001234567890" + f"{tx:013d}" + f"{amount_haler:012d}" + code
            + f"{int(vs or 0):010d}" + "0000000308" + "0000000000" + d + "TEST 0418".ljust(20)
            + "0" + "0203" + d)
    assert len(line) == 128
    return line


def _csv(rows: list) -> bytes:
    lines = ["Pohyby na účtu 123456789/0300", "",
             "Datum zaúčtování;Částka;Měna;Protiúčet;Variabilní symbol;Zpráva pro příjemce;ID pohybu"]
    lines += [";".join(row) for row in rows]
    return "\n".join(lines).encode("cp1250")


def test_gpc_reads_credits_only():
    rows = bank_import.parse(_gpc(_gpc_line(42, 14900, "20260001"),
                                  _gpc_line(43, 5000, "77", code="1")))
    assert rows == [{
        "bank_tx_id": "gpc-42", "received_on": TODAY.isoformat(), "amount_haler": 14900,
        "vs": "20260001", "counter_account": "1234567890", "message": "TEST 0418",
    }]


def test_csv_reads_a_czech_header_in_cp1250():
    rows = bank_import.parse(_csv([
        ["26.10.2026", "1 490,00", "CZK", "123/0800", "0020260001", "TEST 0418", "A1"],
        ["26.10.2026", "-500,00", "CZK", "123/0800", "", "TEST 0418", "A2"],
    ]))
    assert rows == [{
        "bank_tx_id": "csv-A1", "received_on": "2026-10-26", "amount_haler": 149000,
        "vs": "20260001", "counter_account": "123/0800", "message": "TEST 0418",
    }]


def test_an_unknown_file_is_refused():
    with pytest.raises(bank_import.StatementError):
        bank_import.parse(b"hello\nworld\n")


def test_an_exact_payment_marks_the_invoice_paid_and_a_repeat_is_only_seen(invoice):
    _owner, inv = invoice
    data = _gpc(_gpc_line(_tx(), inv["total_haler"], inv["vs"]))
    counts = bank_import.import_statement(data, actor="test")
    assert counts["matched"] == 1 and counts["seen"] == 0
    paid = billing_invoices.get(inv["id"])
    assert paid["paid_on"] == TODAY.isoformat() and paid["paid_via"] == "bank_auto"
    again = bank_import.import_statement(data, actor="test")
    assert again["seen"] == 1 and again["matched"] == 0


def test_too_little_too_much_and_unknown_wait_for_the_operator(invoice):
    _owner, inv = invoice
    short = _gpc_line(_tx(), inv["total_haler"] - 100, inv["vs"])
    unknown = _gpc_line(_tx(), 9900, "123")
    counts = bank_import.import_statement(_gpc(short, unknown), actor="test")
    assert counts["partial"] == 1 and counts["unmatched"] == 1
    assert billing_invoices.get(inv["id"])["paid_on"] is None
    waiting = {r["status"] for r in bank_import.unmatched() if r["message"] == "TEST 0418"}
    assert waiting == {"partial", "unmatched"}
    over = _gpc_line(_tx(), inv["total_haler"] + 100, inv["vs"])
    assert bank_import.import_statement(_gpc(over), actor="test")["overpaid"] == 1
    assert billing_invoices.get(inv["id"])["paid_via"] == "bank_auto"


def test_a_payment_reopens_a_paused_account(invoice):
    owner, inv = invoice
    db.execute("UPDATE platform_invoice SET due_date = ? WHERE id = ?",
               ((TODAY - timedelta(days=15)).isoformat(), inv["id"]))
    db.execute("UPDATE billing_account SET status = 'paused' WHERE owner_user_id = ?", (owner,))
    bank_import.import_statement(_gpc(_gpc_line(_tx(), inv["total_haler"], inv["vs"])), actor="test")
    assert billing.account(owner)["status"] == "active"


def test_the_operator_marks_an_invoice_paid_by_hand(invoice):
    owner, inv = invoice
    db.execute("UPDATE billing_account SET status = 'overdue' WHERE owner_user_id = ?", (owner,))
    assert bank_import.mark_paid_manually(inv["id"], paid_on=TODAY.isoformat(), actor="test") is True
    assert billing_invoices.get(inv["id"])["paid_via"] == "bank_manual"
    assert billing.account(owner)["status"] == "active"
    assert bank_import.mark_paid_manually(inv["id"], paid_on=TODAY.isoformat(), actor="test") is False


def test_no_outbound_request():
    source = (bank_import.__file__ and open(bank_import.__file__, encoding="utf-8").read())
    for name in ("requests", "httpx", "urllib", "socket"):
        assert f"import {name}" not in source
