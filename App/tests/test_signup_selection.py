"""Pricing preferences survive verification without becoming a paid order."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import billing, billing_order, config, db, mail, signup, signup_selection
from app.main import app

CHOICES = {"plan": "max", "interval": "month", "apartments": "12", "ttlock": "1"}


@pytest.fixture
def client(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "SIGNUP_ENABLED", True)
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    db.execute("DELETE FROM rate_limit_event WHERE scope IN ('signup_ip', 'signup_email')")
    yield TestClient(app)
    owners = db.query("SELECT id FROM user_account WHERE email LIKE '%@selection.test'")
    for row in owners:
        owner = row["id"]
        for table, column in (("login_token", "user_account_id"),
                              ("legal_acceptance", "user_account_id"), ("ad_click", "user_account_id"),
                              ("email_outbox", "owner_user_id"), ("audit", "owner_user_id"),
                              ("billing_account", "owner_user_id")):
            db.execute(f"DELETE FROM {table} WHERE {column} = ?", (owner,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


def register(client, local="host", **extra):
    email = f"{local}@selection.test"
    response = client.post("/signup?lang=en",
                           data={"email": email, "workspace": "Selection", "accept": "1",
                                 **CHOICES, **extra}, follow_redirects=False)
    assert response.status_code == 200
    row = db.query_one("SELECT * FROM user_account WHERE email = ?", (email,))
    return row


def token(row):
    return signup.issue_token(row["id"], row["signup_verify_nonce"])


def test_choices_and_language_link_are_allowlisted():
    params = {**CHOICES, "price": "1", "return_to": "//evil.test", "founder": "1"}
    query = parse_qs(urlsplit(signup.signup_href("cs", params)).query)
    assert all(query[k] == [v] for k, v in CHOICES.items())
    assert not {"price", "return_to", "founder"} & query.keys()
    assert signup_selection.clean({"plan": "evil", "interval": "annual", "apartments": "-1",
                                   "ttlock": "true"}) == {}
    for count in ("0", "51", "10000", "1.5", "1e3", "0002", "9" * 10000):
        assert "apartments" not in signup_selection.clean({"apartments": count})


def test_no_js_form_and_errors_keep_preferences(client):
    page = client.get("/signup", params=CHOICES)
    for key, value in CHOICES.items():
        assert f'name="{key}" value="{value}"' in page.text
    failed = client.post("/signup", data={**CHOICES, "email": "bad", "workspace": "Selection"})
    assert failed.status_code == 400
    for key, value in CHOICES.items():
        assert f'name="{key}" value="{value}"' in failed.text


def test_cross_device_verification_preserves_choices_without_ordering(client):
    row = register(client)
    assert signup_selection.for_owner(row["id"]) == CHOICES
    assert billing.account(row["id"]) is None
    other_device = TestClient(app)
    assert other_device.get("/signup/verify", params={"t": token(row)}).status_code == 200
    assert db.query_one("SELECT active FROM user_account WHERE id = ?", (row["id"],))["active"] == 0
    response = other_device.post("/signup/verify", data={"t": token(row)}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/onboarding"
    account = billing.account(row["id"])
    assert account["plan"] is None  # Trial creation is not an order.
    values = billing_order.form_values(row["id"])
    assert values["plan"] == "max" and values["billing_interval"] == "month"
    assert values["addon_ttlock"]
    assert billing_order.apartments(row["id"]) == 1  # Forecast is never billable.
    assert db.query_one("SELECT 1 FROM platform_invoice WHERE owner_user_id = ?",
                        (row["id"],)) is None
    assert other_device.post("/signup/verify", data={"t": token(row)},
                             follow_redirects=False).status_code == 410


def test_repeated_signup_replaces_pending_choices_but_never_verified_account(client):
    row = register(client, "repeat")
    old = token(row)
    fresh = register(client, "repeat", plan="standard", apartments="3")
    assert signup.pending_account(old) is None
    assert signup_selection.for_owner(fresh["id"])["apartments"] == "3"
    assert signup.activate(fresh)
    before = signup_selection.for_owner(fresh["id"])
    register(client, "repeat", apartments="999")
    assert signup_selection.for_owner(fresh["id"]) == before


def test_saved_order_wins_and_preferences_are_owner_scoped(client):
    row = register(client, "ordered")
    assert signup.activate(row)
    db.execute("UPDATE billing_account SET plan = 'standard', billing_interval = 'year', "
               "addon_ttlock = 0 WHERE owner_user_id = ?", (row["id"],))
    values = billing_order.form_values(row["id"])
    assert values["plan"] == "standard" and values["billing_interval"] == "year"
    assert not values["addon_ttlock"]
    second = register(client, "second", plan="standard", ttlock="0")
    assert signup_selection.for_owner(second["id"])["plan"] == "standard"
    assert signup_selection.for_owner(row["id"])["plan"] == "max"
    db.update("user_account", second["id"], {"signup_selection_json": json.dumps(["invalid"])})
    assert signup_selection.for_owner(second["id"]) == {}
