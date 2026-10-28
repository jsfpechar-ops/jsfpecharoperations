"""Brief 0416: ordering, changing and cancelling a plan; the /predplatne page; /cenik numbers."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import ares, auth, billing, billing_invoices, billing_order, config, db
from app.main import app
from app.routes import legal
from tests.conftest import login_as

TODAY = date.today()
BUYER = {
    "plan": "standard", "billing_interval": "month", "buyer_name": "Penzion Test s.r.o.",
    "buyer_street": "Hlavní 1", "buyer_city": "Brno", "buyer_zip": "602 00", "buyer_ico": "",
    "buyer_dic": "", "buyer_email": "Fakturace@Example.cz",
}


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    username = f"ord{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Order host", username=username)
    for name in ("A", "B"):
        db.insert("apartment", {"internal_name": f"Order {name}", "owner_user_id": owner,
                                "created_at": db.utcnow()})
    billing.ensure_account(owner)
    yield {"owner": owner, "username": username}
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ? AND corrects_id IS NOT NULL", (owner,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM founder_slot WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))


def _set(owner: int, **fields) -> None:
    sets = ", ".join(f"{name} = ?" for name in fields)
    db.execute(f"UPDATE billing_account SET {sets} WHERE owner_user_id = ?", (*fields.values(), owner))


def _values(**extra):
    values, errors = billing_order.read_form({**BUYER, **extra})
    assert errors == {}
    return values


def test_read_form_normalises_and_checks():
    values, errors = billing_order.read_form(BUYER)
    assert errors == {} and values["buyer_zip"] == "60200" and values["buyer_email"] == "fakturace@example.cz"
    _values, errors = billing_order.read_form({**BUYER, "plan": "gold", "buyer_zip": "12", "buyer_ico": "123"})
    assert set(errors) == {"plan", "buyer_zip", "buyer_ico"}


def test_form_values_take_the_cenik_choice(host):
    values = billing_order.form_values(host["owner"], {"plan": "max", "interval": "month"})
    assert (values["plan"], values["billing_interval"]) == ("max", "month")
    assert values["buyer_email"].endswith("@example.test")


def test_ordering_in_the_trial_waits_for_its_end(host):
    _set(host["owner"], status="trialing", trial_ends_at=(TODAY + timedelta(days=10)).isoformat())
    result = billing_order.place(host["owner"], _values(billing_interval="year"))
    assert result["starts"] == "trial_end" and result["invoice_id"] is None
    acc = billing.account(host["owner"])
    assert (acc["status"], acc["plan"], acc["billing_interval"], acc["apartments_billed"]) == (
        "trialing", "standard", "year", 2)
    assert acc["founder"] == (1 if db.query_one(
        "SELECT 1 FROM founder_slot WHERE owner_user_id = ?", (host["owner"],)) else 0)
    assert acc["buyer_name"] == "Penzion Test s.r.o."


def test_ordering_when_paused_opens_the_account_and_invoices_at_once(host, monkeypatch):
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    _set(host["owner"], status="paused")
    result = billing_order.place(host["owner"], _values(), today=TODAY)
    assert result["starts"] == "now"
    acc = billing.account(host["owner"])
    assert acc["status"] == "active" and acc["period_start"] == TODAY.isoformat()
    invoice = billing_invoices.get(result["invoice_id"])
    assert invoice["total_haler"] == 2 * 149 * 100
    assert db.query_one("SELECT kind FROM email_outbox WHERE owner_user_id = ?", (host["owner"],))["kind"] == (
        "billing_invoice")


def test_no_second_order_and_no_order_for_og_hosts(host):
    _set(host["owner"], status="active", plan="standard", billing_interval="month")
    with pytest.raises(ValueError, match="already_ordered"):
        billing_order.place(host["owner"], _values())
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (host["owner"],))
    with pytest.raises(ValueError, match="og"):
        billing_order.place(host["owner"], _values())


def test_a_rise_mid_year_bills_the_rest_of_the_year(host):
    end = TODAY + timedelta(days=200)
    _set(host["owner"], status="active", plan="standard", billing_interval="year", apartments_billed=2,
         period_start=(TODAY - timedelta(days=165)).isoformat(), period_end=end.isoformat(),
         buyer_name="Penzion Test s.r.o.")
    preview = billing_order.change(host["owner"], "plan", "max", confirm=False, today=TODAY)
    assert preview["when"] == "now" and preview["invoice_id"] is None
    assert billing.account(host["owner"])["plan"] == "standard"
    done = billing_order.change(host["owner"], "plan", "max", confirm=True, today=TODAY)
    assert billing.account(host["owner"])["plan"] == "max"
    assert done["supplementary_czk"] >= 50
    assert billing_invoices.get(done["invoice_id"])["kind"] == "supplementary"


def test_cancel_and_take_it_back(host):
    _set(host["owner"], status="active", plan="standard", billing_interval="month")
    assert billing_order.cancel(host["owner"])
    assert billing.account(host["owner"])["status"] == "canceling"
    assert billing_order.resume(host["owner"])
    acc = billing.account(host["owner"])
    assert acc["status"] == "active" and acc["cancel_at_period_end"] == 0


def test_the_page_orders_without_javascript(host):
    client = TestClient(app)
    login_as(client, host["username"], url="/login?lang=cs")
    page = client.get("/predplatne?plan=max&interval=year")
    assert page.status_code == 200 and "Objednat" in page.text and "Platíte převodem" in page.text
    assert "Leon Lite" in page.text
    assert "AI concierge Leon pro vaše hosty" in page.text
    assert 'name="addon_whitelabel"' not in page.text
    assert "Skenování dokladů (OCR): připravujeme" in page.text
    assert "Zatím není dostupné, ani během zkušební doby." in page.text
    bad = client.post("/predplatne", data={**BUYER, "buyer_zip": "1"}, follow_redirects=False)
    assert bad.status_code == 400 and "PSČ má pět číslic." in bad.text
    ok = client.post("/predplatne", data=BUYER, follow_redirects=False)
    assert ok.status_code == 303
    assert billing.account(host["owner"])["plan"] == "standard"


def test_ares_fills_only_blank_fields(host, monkeypatch):
    monkeypatch.setattr(ares, "lookup", lambda ico: {"name": "ARES s.r.o.", "street": "Nová 2",
                                                     "city": "Praha", "zip": "11000", "dic": None})
    client = TestClient(app)
    login_as(client, host["username"], url="/login?lang=cs")
    page = client.post("/predplatne", data={**BUYER, "buyer_ico": "27074358", "buyer_name": "",
                                             "buyer_city": "Brno", "do": "ares"})
    assert page.status_code == 200
    assert 'value="ARES s.r.o."' in page.text and 'value="Brno"' in page.text


def test_the_page_is_off_while_billing_is_off(host, monkeypatch):
    client = TestClient(app)
    login_as(client, host["username"], url="/login?lang=cs")
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    response = client.get("/predplatne", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/settings"


def test_another_host_cannot_open_an_invoice(host):
    _set(host["owner"], status="active", plan="standard", billing_interval="month",
         buyer_name="Penzion Test s.r.o.")
    invoice_id = billing_invoices.issue_for_period(host["owner"], "2099-01-01", "2099-01-31", today=date(2099, 1, 1))
    username = f"oth{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Other", username=username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=cs")
    response = client.get(f"/predplatne/faktury/{invoice_id}.pdf", follow_redirects=False)
    assert response.status_code == 303
    db.execute("DELETE FROM platform_invoice_sequence WHERE year = 2099")


def test_cenik_uses_the_billing_price_list(monkeypatch):
    assert legal.PUBLIC_RATES["base"] == {k: list(v) for k, v in billing.BASE.items()}
    assert legal.PUBLIC_RATES["max"] == {k: list(v) for k, v in billing.MAX_EXTRA.items()}
    assert legal.PUBLIC_RATES["ttlock"] == dict(billing.TTLOCK)
    monkeypatch.setattr(config, "FOUNDER_SLOTS", 10_000)
    client = TestClient(app)
    for enabled in (True, False):
        monkeypatch.setattr(config, "BILLING_ENABLED", enabled)
        for lang in ("cs", "en"):
            page = client.get(f"/cenik?lang={lang}")
            assert page.status_code == 200
            assert "pricing-founder" not in page.text


@pytest.mark.parametrize("confirm", [False, True])
def test_white_label_cannot_be_purchased_through_change_api(host, confirm):
    _set(host["owner"], status="active", plan="standard", billing_interval="month")
    with pytest.raises(ValueError, match="whitelabel_unavailable"):
        billing_order.change(host["owner"], "addon_whitelabel", 1, confirm=confirm)
    assert billing.account(host["owner"])["addon_whitelabel"] == 0
    assert billing_invoices.for_owner(host["owner"]) == []


def test_forged_white_label_order_is_rejected_without_creating_a_contract(host):
    with pytest.raises(ValueError, match="whitelabel_unavailable"):
        billing_order.place(host["owner"], _values(addon_whitelabel="1"))
    acc = billing.account(host["owner"])
    assert acc["plan"] is None and acc["addon_whitelabel"] == 0
    assert billing_invoices.for_owner(host["owner"]) == []


def test_white_label_purchase_forms_are_rejected(host):
    client = TestClient(app)
    login_as(client, host["username"], url="/login?lang=en")
    response = client.post("/predplatne", data={**BUYER, "addon_whitelabel": "1"},
                           follow_redirects=False)
    assert response.status_code == 303
    assert billing.account(host["owner"])["plan"] is None
    _set(host["owner"], status="active", plan="standard", billing_interval="month")
    page = client.get("/predplatne").text
    assert "Add your own brand" not in page
    for confirm in ("0", "1"):
        response = client.post("/predplatne/zmena",
                               data={"field": "addon_whitelabel", "value": "1", "confirm": confirm},
                               follow_redirects=False)
        assert response.status_code == 303
    assert billing.account(host["owner"])["addon_whitelabel"] == 0
    assert billing_invoices.for_owner(host["owner"]) == []


def test_existing_white_label_contract_survives_reordering_and_plan_change(host):
    _set(host["owner"], status="paused", plan="standard", billing_interval="month",
         addon_whitelabel=1)
    # The removed checkbox is omitted from a legitimate order; the saved contract wins.
    assert billing_order.quote(host["owner"], _values())["whitelabel"] == billing.WHITELABEL["month"]
    result = billing_order.place(host["owner"], _values())
    invoice = billing_invoices.get(result["invoice_id"])
    assert invoice["total_haler"] == (2 * 149 + 590) * 100
    assert billing.account(host["owner"])["addon_whitelabel"] == 1
    assert billing.entitlements(host["owner"]).whitelabel
    billing_order.change(host["owner"], "plan", "max", confirm=True)
    assert billing.account(host["owner"])["addon_whitelabel"] == 1
    assert billing_invoices.get(result["invoice_id"])["total_haler"] == invoice["total_haler"]
