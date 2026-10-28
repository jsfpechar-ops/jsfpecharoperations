"""Brief 0440/0441/0446: the revenue cockpit queries and the bulk CSV export."""
from __future__ import annotations

import csv
import io
import secrets
import zipfile
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, billing, billing_analytics, billing_invoices, config, db
from app.main import app
from tests.conftest import login_as

TODAY = date.today()

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
    db.insert("apartment", {"internal_name": "Analytics 1", "owner_user_id": host, "created_at": db.utcnow()})
    billing.ensure_account(host)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 1, period_start = ?, period_end = ?, buyer_name = 'Penzion \u00da\u010detn\u00ed', "
        "buyer_street = 'Hlavn\u00ed 3', buyer_city = 'Brno', buyer_zip = '60200', buyer_ico = '27074358' "
        "WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), host),
    )
    invoice_id = billing_invoices.issue_for_period(host, TODAY.isoformat(),
                                                   (TODAY + timedelta(days=29)).isoformat(), today=TODAY)
    yield {"admin": f"adm{suffix}", "host": f"hst{suffix}", "host_id": host,
           "invoice": dict(billing_invoices.get(invoice_id))}
    db.execute("DELETE FROM bank_payment WHERE matched_invoice_id IN "
               "(SELECT id FROM platform_invoice WHERE owner_user_id = ?)", (host,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host,))



def test_portfolio_prices_come_from_the_engine(setup):
    data = billing_analytics.portfolio()
    row = next(c for c in data["customers"] if c["owner_user_id"] == setup["host_id"])
    q = billing.quote(1, "standard", "month")
    assert row["net_czk"] == q["total"] and row["monthly_czk"] == q["total"]
    assert data["mrr_czk"] == q["total"] and data["arr_czk"] == q["total"] * 12
    assert data["by_status"] == {"active": 1}


def test_watchlists_flag_the_overdue_invoice(setup):
    db.execute("UPDATE platform_invoice SET due_date = ? WHERE id = ?",
               ((TODAY - timedelta(days=3)).isoformat(), setup["invoice"]["id"]))
    db.execute("UPDATE billing_account SET status = 'overdue' WHERE owner_user_id = ?",
               (setup["host_id"],))
    watch = billing_analytics.watchlists()
    assert [o["number"] for o in watch["overdue"]] == [setup["invoice"]["number"]]
    assert watch["overdue"][0]["days_late"] == 3
    assert billing_analytics.aging() == {"0-7": setup["invoice"]["total_haler"] // 100,
                                        "8-30": 0, "31-90": 0, "90+": 0}


def test_revenue_totals_separate_billed_from_collected(setup):
    totals = billing_analytics.revenue_totals()
    assert totals["billed_czk"] == setup["invoice"]["total_haler"] // 100
    assert totals["collected_czk"] == 0


def test_forecast_counts_open_invoices_within_30_days(setup):
    assert billing_analytics.forecast()["next_30_days_czk"] == setup["invoice"]["total_haler"] // 100


def test_the_bulk_zip_has_three_csvs_and_is_excel_friendly(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    response = client.get("/admin/fakturace/export-vse")
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(zf.namelist()) == ["faktury.csv", "platby.csv", "zakaznici.csv"]

    def rows_of(name):
        text = zf.read(name).decode("utf-8-sig")
        return list(csv.reader(io.StringIO(text), delimiter=";"))

    customers = rows_of("zakaznici.csv")
    assert customers[0] == list(billing_analytics.CUSTOMERS_CSV_HEADER)
    assert customers[1][3] == "standard" and customers[1][12] == "149"

    invoices = rows_of("faktury.csv")
    assert invoices[0] == list(billing_analytics.INVOICES_CSV_HEADER)
    mine = [r for r in invoices[1:] if r[0] == setup["invoice"]["number"]]
    assert mine and mine[0][8] == f"{setup['invoice']['total_haler'] / 100:.2f}".replace(".", ",")

    payments = rows_of("platby.csv")
    assert payments[0] == list(billing_analytics.PAYMENTS_CSV_HEADER)
    assert payments[1:] == []


def test_a_host_cannot_download_the_bulk_export(setup):
    client = TestClient(app)
    login_as(client, setup["host"], url="/login?lang=cs")
    assert client.get("/admin/fakturace/export-vse").status_code == 403


def test_the_page_shows_the_cockpit(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    page = client.get("/admin/fakturace").text
    assert "data-billing-admin-portfolio=" in page
    assert "data-billing-admin-portfolio-filter" in page
    assert "data-billing-admin-watch" in page
