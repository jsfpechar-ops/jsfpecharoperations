"""0221: the host's switch for the monthly stay-fee email."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_auto
from app.main import app
from tests.conftest import login_as


def _cleanup():
    for user in db.query(
        "SELECT id FROM user_account WHERE username LIKE 'stay-fee-emails-%'"
    ):
        owner_id = user["id"]
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    owner_id = auth.create_account(
        "stay-fee-emails-owner@example.test", "Email Demo", role="host",
        username="stay-fee-emails-owner",
    )
    client = TestClient(app)
    logged_in = login_as(
        client, "stay-fee-emails-owner", url="/login?lang=en", follow_redirects=False
    )
    assert logged_in.status_code == 303
    try:
        yield client, owner_id
    finally:
        _cleanup()


def _add_fee_property(owner_id, rate=50):
    entity_id = db.insert("legal_entity", {
        "name": "Email Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    return db.insert("apartment", {
        "internal_name": "Email demo flat",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "addr_obec": "Praha 3",
        "stay_fee_rate_czk": rate,
        "stay_fee_cadence": "monthly",
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "created_at": db.utcnow(),
    })


def test_the_switch_is_on_by_default(host):
    _client, owner_id = host
    assert stay_fee_auto.emails_enabled(owner_id) is True
    row = db.query_one(
        "SELECT stay_fee_emails_opt_out, stay_fee_emails_opt_out_at "
        "FROM user_account WHERE id = ?",
        (owner_id,),
    )
    assert row["stay_fee_emails_opt_out"] == 0
    assert row["stay_fee_emails_opt_out_at"] is None


def test_posting_without_enabled_turns_the_emails_off(host):
    client, owner_id = host
    response = client.post("/account/stay-fee-emails", data={}, follow_redirects=False)
    assert response.status_code == 303
    assert stay_fee_auto.emails_enabled(owner_id) is False
    row = db.query_one(
        "SELECT stay_fee_emails_opt_out_at FROM user_account WHERE id = ?", (owner_id,)
    )
    assert row["stay_fee_emails_opt_out_at"]


def test_posting_enabled_turns_the_emails_back_on(host):
    client, owner_id = host
    client.post("/account/stay-fee-emails", data={}, follow_redirects=False)
    response = client.post(
        "/account/stay-fee-emails", data={"enabled": "1"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert stay_fee_auto.emails_enabled(owner_id) is True
    row = db.query_one(
        "SELECT stay_fee_emails_opt_out_at FROM user_account WHERE id = ?", (owner_id,)
    )
    assert row["stay_fee_emails_opt_out_at"] is None


def test_the_settings_row_is_hidden_without_a_fee_property_and_shown_with_one(host):
    client, owner_id = host
    hidden = client.get("/settings?lang=en")
    assert hidden.status_code == 200
    assert 'id="settings-stay-fee-emails"' not in hidden.text
    _add_fee_property(owner_id)
    shown = client.get("/settings?lang=en")
    assert shown.status_code == 200
    assert 'id="settings-stay-fee-emails"' in shown.text
    assert 'action="/account/stay-fee-emails"' in shown.text


def test_the_list_line_matches_the_switch(host):
    client, owner_id = host
    _add_fee_property(owner_id)
    on = client.get("/stay-fees?lang=en")
    assert on.status_code == 200
    assert "Complete reports are emailed to you on the 2nd day after each period." in on.text
    client.post("/account/stay-fee-emails", data={}, follow_redirects=False)
    off = client.get("/stay-fees?lang=en")
    assert off.status_code == 200
    assert "Stay fee emails are off." in off.text
    assert "Complete reports are emailed" not in off.text
