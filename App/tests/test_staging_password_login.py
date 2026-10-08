"""Render staging: break-glass username/password login (rigorous coverage)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, mail
from app.main import app

import secrets

_SUFFIX = secrets.token_hex(4)
EMAIL = f"staging-pw-{_SUFFIX}@example.test"
PASSWORD = "staging-only-secret"
USERNAME = f"staging-pw-{_SUFFIX}"


@pytest.fixture
def staging_env(monkeypatch):
    db.init_db()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    monkeypatch.delenv("UBYHOST_STAGING_LOGIN_PASSWORD", raising=False)


def _remove_user(user_id: int) -> None:
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def staging_with_password(staging_env, monkeypatch):
    monkeypatch.setenv("UBYHOST_STAGING_LOGIN_PASSWORD", PASSWORD)
    for row in db.query(
        "SELECT id FROM user_account WHERE username = ? OR email = ?",
        (USERNAME, EMAIL),
    ):
        _remove_user(int(row["id"]))
    user_id = auth.create_account(EMAIL, "Staging Admin", role="admin", username=USERNAME)
    yield user_id
    _remove_user(user_id)


def test_login_page_shows_username_form_when_password_configured(staging_with_password):
    page = TestClient(app).get("/login?lang=en")
    assert page.status_code == 200
    assert 'name="username"' in page.text
    assert 'name="staging_password"' in page.text
    # Hint uses the first admin by id (may be from another test module).
    assert auth.staging_admin_username() in page.text
    assert "SECRET_KEY" in page.text
    assert "Poslat přihlašovací odkaz" not in page.text


def test_login_page_warns_when_password_missing(staging_env):
    page = TestClient(app).get("/login?lang=en")
    assert page.status_code == 200
    assert "UBYHOST_STAGING_LOGIN_PASSWORD" in page.text


def test_staging_password_logs_in_with_username(staging_with_password):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "staging_password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert client.get("/").status_code == 200


def test_staging_password_trims_whitespace_on_paste(staging_with_password):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "staging_password": f"  {PASSWORD}  "},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_staging_password_logs_in_with_email_field(staging_with_password):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"email": EMAIL, "staging_password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_staging_password_ignores_surrounding_quotes_in_env(staging_with_password, monkeypatch):
    monkeypatch.setenv("UBYHOST_STAGING_LOGIN_PASSWORD", f'"{PASSWORD}"')
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "staging_password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_staging_password_accepts_wrong_username_when_admin_exists(staging_with_password):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": "not-the-handle", "staging_password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_wrong_staging_password_is_rejected(staging_with_password):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "staging_password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert "staging_password" in response.text or "auth.error" in response.text


def test_empty_password_does_not_send_login_email_when_env_set(staging_with_password):
    client = TestClient(app)
    before = db.query_one("SELECT COUNT(*) AS n FROM email_outbox")["n"]
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "staging_password": ""},
        follow_redirects=False,
    )
    assert response.status_code == 403
    after = db.query_one("SELECT COUNT(*) AS n FROM email_outbox")["n"]
    assert after == before


def test_email_link_flow_blocked_when_staging_password_configured(staging_with_password):
    response = TestClient(app).post(
        "/login?lang=en",
        data={"email": EMAIL},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_login_sent_warns_on_staging_console_mail(staging_env, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    monkeypatch.delenv("UBYHOST_STAGING_LOGIN_PASSWORD", raising=False)
    db.execute("DELETE FROM user_account WHERE email = ?", (EMAIL,))
    auth.create_account(EMAIL, "Host", username="staging-mail-host")
    response = TestClient(app).post("/login?lang=en", data={"email": EMAIL})
    assert response.status_code == 200
    assert "Render" in response.text or "render" in response.text.lower()


def test_healthz_includes_staging_login_metadata(staging_with_password, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    body = TestClient(app).get("/healthz").json()
    assert body["staging_login"]["password_configured"] is True
    assert body["staging_login"]["password_length"] == len(PASSWORD)
    assert body["staging_login"]["admin_username"] == auth.staging_admin_username()


def test_healthz_omits_staging_login_when_database_down(staging_with_password, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")

    def boom(*args, **kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr(db, "query_one", boom)
    body = TestClient(app).get("/healthz").json()
    assert body["database_ok"] is False
    assert "staging_login" not in body


def test_staging_password_ignored_on_local_even_with_env(staging_with_password, monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "local")
    response = TestClient(app).post(
        "/login?lang=en",
        data={"username": USERNAME, "staging_password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_production_refuses_staging_password_env(monkeypatch):
    from app import env_guard

    env = {**os.environ, "UBYHOST_STAGING_LOGIN_PASSWORD": "nope", "UBYHOST_GUEST_PIN": "1"}
    with pytest.raises(env_guard.EnvGuardError, match="staging"):
        env_guard.validate_runtime_env(
            deployment="production",
            guest_pin_required=True,
            environ=env,
        )


def test_staging_admin_username_falls_back_to_config(staging_env, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_USERNAME", "configured-admin")
    real_query_one = db.query_one

    def query_one(sql, params=()):
        if "FROM user_account WHERE role = 'admin'" in sql:
            return None
        return real_query_one(sql, params)

    monkeypatch.setattr(db, "query_one", query_one)
    assert auth.staging_admin_username() == "configured-admin"


def test_staging_expected_password_empty_off_staging(monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setenv("UBYHOST_STAGING_LOGIN_PASSWORD", PASSWORD)
    assert auth.staging_expected_password() == ""
