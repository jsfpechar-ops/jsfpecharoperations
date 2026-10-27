"""Admin customer access, literal search, status filtering and bounded pagination."""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import admin_customers, auth, billing, config, db
from app.main import app
from tests.conftest import login_as


@pytest.fixture
def accounts(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    prefix = "customers-" + secrets.token_hex(5)
    ids = []

    def create(name="", role="host", **fields):
        number = len(ids)
        username = f"{prefix}-{number}"
        owner = auth.create_account(
            f"{username}@example.test", name or username, role=role, username=username,
        )
        ids.append(owner)
        if fields:
            db.update("user_account", owner, fields)
        return owner, username

    yield create, prefix
    for owner in reversed(ids):
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ? OR actor_user_id = ?", (owner, owner))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (owner,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


def test_both_pages_require_admin_before_reading_customer_data(accounts):
    create, _prefix = accounts
    owner, username = create()
    client = TestClient(app)
    for path in ("/admin/customers", f"/admin/customers/{owner}"):
        assert client.get(path, follow_redirects=False).status_code == 303
    login_as(client, username, url="/login?lang=en")
    for path in ("/admin/customers", f"/admin/customers/{owner}"):
        assert client.get(path, follow_redirects=False).status_code == 403


def test_keyset_pagination_has_no_missing_or_duplicate_accounts(accounts, monkeypatch):
    create, prefix = accounts
    expected = [create()[0] for _ in range(31)]
    values = admin_customers.filters(prefix)
    queries = []
    original = db.query

    def record(sql, params=()):
        queries.append(sql)
        return original(sql, params)

    monkeypatch.setattr(db, "query", record)
    first = admin_customers.customers(values, today=date.today())
    assert len(queries) == 2  # one customer query and one batched property count
    first_ids = [r["id"] for r in first["customers"]]
    assert len(first_ids) == 25 and first["older"] and not first["newer"]
    second = admin_customers.customers(values, after=first_ids[-1], today=date.today())
    second_ids = [r["id"] for r in second["customers"]]
    assert first_ids + second_ids == list(reversed(expected))
    assert not second["older"] and second["newer"]
    back = admin_customers.customers(values, before=second_ids[0], today=date.today())
    assert [r["id"] for r in back["customers"]] == first_ids


def test_search_wildcards_are_literal_and_status_filter_precedes_pagination(accounts):
    create, prefix = accounts
    wanted, _ = create(prefix + " 100%_match")
    create(prefix + " 100XXmatch")
    literal = admin_customers.customers(
        admin_customers.filters("100%_match"), today=date.today(),
    )
    assert [r["id"] for r in literal["customers"]] == [wanted]
    billing.ensure_account(wanted)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'max', billing_interval = 'year' "
        "WHERE owner_user_id = ?", (wanted,),
    )
    for _ in range(26):
        create()
    selected = admin_customers.customers(
        admin_customers.filters(prefix, "active", "max"), today=date.today(),
    )
    assert [r["id"] for r in selected["customers"]] == [wanted]
    assert selected["customers"][0]["customer_state"] == "active"


def test_legacy_unverified_disabled_and_trial_ending_are_distinct(accounts):
    create, prefix = accounts
    legacy, _ = create()
    pending, _ = create(active=0, signup_at=db.utcnow(), email_verified_at=None)
    disabled, _ = create(active=0)
    trial, _ = create()
    billing.ensure_account(trial)
    db.execute(
        "UPDATE billing_account SET status = 'trialing', trial_ends_at = ? WHERE owner_user_id = ?",
        ((date.today() + timedelta(days=7)).isoformat(), trial),
    )
    for state, owner in (("legacy", legacy), ("unverified", pending),
                         ("disabled", disabled), ("ending", trial)):
        result = admin_customers.customers(admin_customers.filters(prefix, state), today=date.today())
        assert [r["id"] for r in result["customers"]] == [owner]
    assert billing.account(legacy) is None  # reads do not provision legacy billing


def test_admin_views_escape_workspace_names_and_offer_existing_links(accounts, monkeypatch):
    create, prefix = accounts
    owner, _ = create(prefix + " <script>alert(1)</script>")
    _admin, username = create(role="admin")
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en")
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    for lang, label in (("en", "Customers"), ("cs", "Zákazníci")):
        listing = client.get(f"/admin/customers?q={prefix}&lang={lang}")
        assert listing.status_code == 200 and label in listing.text
        assert "<script>alert(1)</script>" not in listing.text
        assert f"/admin/customers/{owner}" in listing.text
    page = client.get(f"/admin/customers/{owner}?lang=en")
    assert page.status_code == 200
    assert "<script>alert(1)</script>" not in page.text
    assert "Legacy free" in page.text and "Billing is switched off" in page.text
    assert f"/admin/users?manage={owner}#user-manage" in page.text
    assert "/admin/fakturace" in page.text
    assert "password_hash" not in page.text and "signup_verify_nonce" not in page.text
    assert client.get(f"/admin/customers/{_admin}").status_code == 404


def test_bad_filters_and_cursors_do_not_change_the_query_contract(accounts):
    create, prefix = accounts
    create()
    values = admin_customers.filters(prefix + "x" * 200, "bogus", "gold")
    assert len(values["q"]) == 120 and values["state"] == values["plan"] == ""
    _admin, username = create(role="admin")
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en")
    assert client.get("/admin/customers?after=999999999999999999999999&before=-1").status_code == 200
