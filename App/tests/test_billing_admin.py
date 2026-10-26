"""Brief 0419: /admin/fakturace. Admins only, statement upload, mark paid, storno, the accountant's ZIP."""
from __future__ import annotations

import csv
import io
import secrets
import zipfile
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, billing, billing_admin, billing_invoices, config, db
from app.main import app
from tests.conftest import login_as

TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")


@pytest.fixture
def setup(monkeypatch):
    """An admin, and a host on a monthly plan with this period's invoice issued."""
    db.init_db()
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    suffix = secrets.token_hex(4)
    auth.create_account(f"adm{suffix}@example.test", "Admin", role="admin", username=f"adm{suffix}")
    host = auth.create_account(f"hst{suffix}@example.test", "Host", username=f"hst{suffix}")
    db.insert("apartment", {"internal_name": "Admin 1", "owner_user_id": host, "created_at": db.utcnow()})
    billing.ensure_account(host)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 1, period_start = ?, period_end = ?, buyer_name = 'Penzion Účetní', "
        "buyer_street = 'Hlavní 3', buyer_city = 'Brno', buyer_zip = '60200', buyer_ico = '27074358' "
        "WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), host),
    )
    invoice_id = billing_invoices.issue_for_period(host, TODAY.isoformat(),
                                                   (TODAY + timedelta(days=29)).isoformat(), today=TODAY)
    yield {"admin": f"adm{suffix}", "host": f"hst{suffix}", "host_id": host,
           "invoice": dict(billing_invoices.get(invoice_id))}
    db.execute("DELETE FROM bank_payment WHERE matched_invoice_id IN "
               "(SELECT id FROM platform_invoice WHERE owner_user_id = ?)", (host,))
    db.execute("DELETE FROM bank_payment WHERE message = 'TEST 0419'")
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ? AND corrects_id IS NOT NULL", (host,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host,))


def _admin(setup) -> TestClient:
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    return client


def _gpc(tx: int, amount_haler: int, vs: str) -> bytes:
    d = TODAY.strftime("%d%m%y")
    header = ("074" + "0000000123456789" + "UBYHOST S.R.O.".ljust(20)).ljust(128)
    line = ("075" + "0000000123456789" + "0000001234567890" + f"{tx:013d}" + f"{amount_haler:012d}" + "2"
            + f"{int(vs):010d}" + "0000000308" + "0000000000" + d + "TEST 0419".ljust(20) + "0" + "0203" + d)
    return f"{header}\r\n{line}".encode("cp1250")


def test_a_host_cannot_open_the_page(setup):
    client = TestClient(app)
    login_as(client, setup["host"], url="/login?lang=cs")
    assert client.get("/admin/fakturace", follow_redirects=False).status_code == 403
    assert client.get(f"/admin/fakturace/export?mesic={MONTH}", follow_redirects=False).status_code == 403
    response = client.post(f"/admin/fakturace/{setup['invoice']['id']}/zaplaceno",
                           data={"paid_on": TODAY.isoformat()}, follow_redirects=False)
    assert response.status_code == 403
    assert billing_invoices.get(setup["invoice"]["id"])["paid_on"] is None


def test_the_page_lists_the_unpaid_invoice(setup):
    page = _admin(setup).get("/admin/fakturace")
    assert page.status_code == 200
    assert setup["invoice"]["number"] in page.text and "Penzion Účetní" in page.text
    assert "Nahrát výpis" in page.text


def test_an_uploaded_statement_marks_the_invoice_paid(setup):
    inv = setup["invoice"]
    client = _admin(setup)
    response = client.post("/admin/fakturace/vypis", data={},
                           files={"statement": ("vypis.gpc", _gpc(10**9 + secrets.randbelow(10**9),
                                                                  inv["total_haler"], inv["vs"]))},
                           follow_redirects=False)
    assert response.status_code == 303
    assert billing_invoices.get(inv["id"])["paid_via"] == "bank_auto"
    bad = client.post("/admin/fakturace/vypis", data={}, files={"statement": ("x.txt", b"hello")},
                      follow_redirects=False)
    assert bad.status_code == 303 and "err=" in bad.headers["location"]


def test_mark_paid_by_hand_then_storno_is_refused(setup):
    inv = setup["invoice"]
    client = _admin(setup)
    client.post(f"/admin/fakturace/{inv['id']}/zaplaceno", data={"paid_on": TODAY.isoformat()})
    assert billing_invoices.get(inv["id"])["paid_via"] == "bank_manual"
    response = client.post(f"/admin/fakturace/{inv['id']}/storno", data={"reason": "Chyba"},
                           follow_redirects=False)
    assert "err=" in response.headers["location"]
    assert billing_invoices.get(inv["id"])["voided"] == 0


def test_storno_of_an_unpaid_invoice(setup):
    inv = setup["invoice"]
    client = _admin(setup)
    missing = client.post(f"/admin/fakturace/{inv['id']}/storno", data={"reason": ""}, follow_redirects=False)
    assert "err=" in missing.headers["location"]
    client.post(f"/admin/fakturace/{inv['id']}/storno", data={"reason": "Chybná adresa"})
    assert billing_invoices.get(inv["id"])["voided"] == 1
    kinds = [r["kind"] for r in billing_admin.invoices(MONTH) if r["corrects_id"] == inv["id"]]
    assert kinds == ["storno"]


def test_the_accountant_zip_has_the_csv_and_every_pdf(setup):
    inv = setup["invoice"]
    response = _admin(setup).get(f"/admin/fakturace/export?mesic={MONTH}")
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    assert f"pdf/{inv['number']}.pdf" in zf.namelist()
    assert zf.read(f"pdf/{inv['number']}.pdf") == billing_invoices.pdf_bytes(inv["id"])
    text = zf.read(f"faktury-{MONTH}.csv").decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert rows[0] == list(billing_admin.CSV_HEADER)
    mine = [r for r in rows[1:] if r[0] == inv["number"]]
    assert mine and mine[0][7] == "Penzion Účetní" and mine[0][8] == "27074358"
    assert mine[0][10] == f"{inv['total_haler'] // 100},00"


def test_a_bad_month_falls_back_to_the_current_one():
    assert billing_admin.month_or_current("2026-13", date(2026, 10, 26)) == "2026-10"
    assert billing_admin.month_or_current("2026-02", date(2026, 10, 26)) == "2026-02"
