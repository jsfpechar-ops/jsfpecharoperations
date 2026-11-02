"""The "secure your account" pop-up waits 7 days after a self-signup (task 0491)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, mail
from app.main import app
from tests.conftest import login_as

BASE = "https://ubyhost.test"
EMAIL = "security-delay@example.test"


@pytest.fixture(autouse=True)
def https_site(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", BASE)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    _clean()
    yield
    _clean()


def _clean():
    row = db.query_one("SELECT id FROM user_account WHERE email = ?", (EMAIL,))
    if not row:
        return
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (row["id"],))
    db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _account_signed_up(days_ago: int):
    user_id = auth.create_account(EMAIL, "Security Delay", username="security-delay")
    started = (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(microsecond=0)
    db.execute("UPDATE user_account SET signup_at = ? WHERE id = ?", (started.isoformat(), user_id))
    return db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))


def _home_html(account) -> str:
    client = TestClient(app, base_url="https://testserver")
    login_as(client, account["username"], follow_redirects=False)
    response = client.get("/")
    assert response.status_code == 200
    return response.text


def _prompted_at(account):
    row = db.query_one("SELECT two_factor_prompted_at FROM user_account WHERE id = ?", (account["id"],))
    return row["two_factor_prompted_at"]


def test_no_security_pop_up_in_the_first_seven_days():
    account = _account_signed_up(days_ago=0)
    html = _home_html(account)
    assert 'id="security-prompt"' not in html
    assert _prompted_at(account) is None


def test_security_pop_up_appears_after_seven_days():
    account = _account_signed_up(days_ago=8)
    html = _home_html(account)
    assert 'id="security-prompt"' in html and "security-prompt-title" in html
    assert _prompted_at(account)
