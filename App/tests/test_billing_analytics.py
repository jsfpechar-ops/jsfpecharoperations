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


def test_a_discount_reissues_the_unpaid_invoice(setup):
    """D1: storno + reissue with the discount; the host pays only the new number."""
    from app import billing_invoices as bi
    host = setup["host_id"]
    old = setup["invoice"]
    result = billing.apply_discount(host, 20, reason="Verno věrným", actor="operator:adm")
    assert result["reissued_invoice_ids"] and result["period_total_after"] < result["period_total_before"]
    assert bi.get(old["id"])["voided"] == 1
    rows = [r for r in db.query(
        "SELECT * FROM platform_invoice WHERE owner_user_id = ? AND kind = 'invoice' AND voided = 0", (host,))]
    expected = billing.quote(1, "standard", "month", discount_percent=20)["total"] * 100
    assert len(rows) == 1 and rows[0]["total_haler"] == expected
    stornos = [r for r in db.query(
        "SELECT * FROM platform_invoice WHERE owner_user_id = ? AND kind = 'storno'", (host,))]
    assert len(stornos) == 1 and stornos[0]["corrects_id"] == old["id"]


def test_a_discount_reason_is_required(setup):
    import pytest as _pytest
    with _pytest.raises(ValueError, match="reason_missing"):
        billing.apply_discount(setup["host_id"], 10, reason="", actor="operator:adm")


def test_the_discounted_invoice_prints_the_discount_line(setup):
    import json as _json
    host = setup["host_id"]
    billing.apply_discount(host, 10, reason="Stálý zákazník", actor="operator:adm")
    fresh = db.query_one(
        "SELECT snapshot_json FROM platform_invoice WHERE owner_user_id = ? AND voided = 0 AND kind = 'invoice'",
        (host,))
    items = _json.loads(fresh["snapshot_json"])["items"]
    assert any("Sleva" in it["description"] for it in items)
    assert any(it["gross_haler"] < 0 for it in items)


def test_operator_can_change_the_plan_through_the_engine(setup):
    host = setup["host_id"]
    result = billing.apply_change(host, {"plan": "max"}, today=TODAY, confirm=True,
                                  actor="operator:adm")
    assert result["period_total_after"] > result["period_total_before"]
    assert billing.account(host)["plan"] == "max"


def test_month_snapshot_and_movement(setup):
    host = setup["host_id"]
    assert billing_analytics.write_month_snapshot() == 1
    month = f"{TODAY:%Y-%m}"
    row = db.query_one("SELECT * FROM billing_month_snapshot WHERE owner_user_id = ?", (host,))
    assert row["month"] == month and row["net_czk"] == 149 and row["monthly_czk"] == 149
    move = billing_analytics.movement(month)
    assert move["current_mrr"] == 149
    assert move["parts"]["new"] == 149  # first month: everything is new business


def test_funnel_counts_the_setup(setup):
    counts = billing_analytics.funnel()
    assert counts["hosts"] >= 1 and counts["converted"] >= 1


def test_discount_overview_after_a_discount(setup):
    billing.apply_discount(setup["host_id"], 25, reason="Založení", actor="operator:adm")
    overview = billing_analytics.discount_overview()
    assert overview["list_mrr_czk"] > overview["net_mrr_czk"]
    assert overview["giveaway_mrr_czk"] > 0
    assert [c["owner_user_id"] for c in overview["customers"]] == [setup["host_id"]]


def test_trend_lists_months(setup):
    rows = billing_analytics.trend()
    assert rows and rows[-1]["billed_czk"] == setup["invoice"]["total_haler"] // 100
    assert rows[-1]["collected_czk"] == 0


def test_the_page_shows_the_new_sections(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    page = client.get("/admin/fakturace").text
    assert "data-billing-admin-trend=" in page
    assert "data-billing-admin-discount=" in page or "Peníze se slevou" in page
    detail = client.get(f"/admin/customers/{setup['host_id']}").text
    assert "data-customer-discount" in detail
    assert "data-customer-plan" in detail
    assert "data-customer-status" in detail


def test_operator_forms_work_end_to_end(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    host = setup["host_id"]

    r = client.post(f"/admin/customers/{host}/sleva", data={"percent": "15", "reason": "Loajalita"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(host)["discount_percent"] == 15

    r = client.post(f"/admin/customers/{host}/plan",
                    data={"field": "apartments", "value": "2"}, follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(host)["apartments_billed"] == 2

    r = client.post(f"/admin/customers/{host}/stav", data={"status": "canceling"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(host)["status"] == "canceling"
    r = client.post(f"/admin/customers/{host}/stav", data={"status": "active"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(host)["status"] == "active"


def test_operator_form_refuses_bad_values(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    host = setup["host_id"]
    client.post(f"/admin/customers/{host}/sleva", data={"percent": "150", "reason": "x"})
    assert billing.account(host)["discount_percent"] == 0
    client.post(f"/admin/customers/{host}/plan", data={"field": "plan", "value": "gold"})
    assert billing.account(host)["plan"] == "standard"


def test_a_host_cannot_use_the_operator_forms(setup):
    client = TestClient(app)
    login_as(client, setup["host"], url="/login?lang=cs")
    host = setup["host_id"]
    assert client.post(f"/admin/customers/{host}/sleva", data={"percent": "50", "reason": "x"}).status_code == 403
    assert client.post(f"/admin/customers/{host}/stav", data={"status": "paused"}).status_code == 403


def _legacy_host(setup):
    """A second host with no billing row: the 'Legacy free' case."""
    suffix = secrets.token_hex(4)
    host = auth.create_account(f"leg{suffix}@example.test", "Legacy Host", username=f"leg{suffix}")
    db.insert("apartment", {"internal_name": "Legacy 1", "owner_user_id": host,
                            "created_at": db.utcnow()})
    return host


def test_the_operator_assigns_a_plan_to_a_legacy_host(setup):
    host = _legacy_host(setup)
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    detail = client.get(f"/admin/customers/{host}").text
    assert "data-customer-assign" in detail

    r = client.post(f"/admin/customers/{host}/priradit", data={
        "plan": "standard", "billing_interval": "month", "addon_ttlock": "0",
        "buyer_name": "Legacy Host s.r.o.", "buyer_street": "Hlavní 1",
        "buyer_city": "Brno", "buyer_zip": "60200", "buyer_ico": "27074358",
        "buyer_dic": "", "buyer_email": "legacy@example.test",
    }, follow_redirects=False)
    assert r.status_code == 303
    acc = billing.account(host)
    assert acc["plan"] == "standard" and acc["status"] == "active"
    assert acc["period_start"] == TODAY.isoformat()
    invoices = [dict(x) for x in db.query(
        "SELECT * FROM platform_invoice WHERE owner_user_id = ? AND kind = 'invoice' AND voided = 0",
        (host,))]
    assert len(invoices) == 1  # the first invoice, issued now
    audit = db.query_one("SELECT * FROM audit WHERE owner_user_id = ? AND action = 'billing_order' "
                         "ORDER BY id DESC", (host,))
    assert "operator:" in audit["actor"]
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host,))


def test_the_assign_form_prefills_the_operators_known_details(setup):
    host = _legacy_host(setup)
    db.insert("legal_entity", {
        "owner_user_id": host, "name": "Legacy Host s.r.o.", "seat": "Hlavni 1, 60200 Brno",
        "ico": "27074358", "dic": "CZ27074358", "contact_email": "book@legacy.test",
        "vat_status": "non_payer", "created_at": db.utcnow(),
    })
    db.execute(
        "UPDATE apartment SET addr_street = 'Hlavni', addr_house_no = '1', "
        "addr_obec = 'Brno', addr_zip = '60200' WHERE owner_user_id = ?", (host,))
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    page = client.get(f"/admin/customers/{host}").text
    assert "data-customer-assign" in page
    assert 'value="Legacy Host s.r.o."' in page
    assert 'value="Hlavni 1"' in page
    assert 'value="Brno"' in page
    assert 'value="60200"' in page
    assert 'value="27074358"' in page
    assert 'value="CZ27074358"' in page
    assert 'value="book@legacy.test"' in page
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host,))


def test_assign_refuses_a_host_who_already_has_a_plan(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    r = client.post(f"/admin/customers/{setup['host_id']}/priradit", data={
        "plan": "standard", "billing_interval": "month", "addon_ttlock": "0",
        "buyer_name": "X", "buyer_street": "Y", "buyer_city": "Z",
        "buyer_zip": "60200", "buyer_email": "x@example.test",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(setup["host_id"])["plan"] == "standard"


def test_the_operator_extends_a_running_trial(setup):
    host = _legacy_host(setup)
    billing.ensure_account(host)
    db.execute(
        "UPDATE billing_account SET status = 'trialing', trial_started_at = ?, trial_ends_at = ? "
        "WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=3)).isoformat(), host))
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    detail = client.get(f"/admin/customers/{host}").text
    assert "data-customer-extend" in detail
    r = client.post(f"/admin/customers/{host}/prodlouzit", data={"days": "7"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(host)["trial_ends_at"][:10] == (TODAY + timedelta(days=10)).isoformat()
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (host,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host,))


def test_extend_refuses_a_non_trialing_account(setup):
    client = TestClient(app)
    login_as(client, setup["admin"], url="/login?lang=cs")
    r = client.post(f"/admin/customers/{setup['host_id']}/prodlouzit", data={"days": "7"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert billing.account(setup["host_id"])["trial_ends_at"] is None


def test_a_host_cannot_assign_plans(setup):
    client = TestClient(app)
    login_as(client, setup["host"], url="/login?lang=cs")
    assert client.post(f"/admin/customers/{setup['host_id']}/priradit", data={
        "plan": "standard", "billing_interval": "month", "addon_ttlock": "0",
        "buyer_name": "X", "buyer_street": "Y", "buyer_city": "Z",
        "buyer_zip": "60200", "buyer_email": "x@example.test",
    }).status_code == 403
