"""Render staging: break-glass password login when mail is not delivered."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, mail
from app.main import app

EMAIL = "staging-pw@example.test"
PASSWORD = "staging-only-secret"


@pytest.fixture
def account(monkeypatch):
    db.init_db()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    monkeypatch.setattr(config, "STAGING_LOGIN_PASSWORD", PASSWORD)
    db.execute("DELETE FROM user_account WHERE email = ?", (EMAIL,))
    user_id = auth.create_account(EMAIL, "Staging Admin", role="admin", username="staging-pw-admin")
    yield user_id
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_staging_password_logs_in(account):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"email": EMAIL, "staging_password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert client.get("/").status_code == 200


def test_wrong_staging_password_is_rejected(account):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"email": EMAIL, "staging_password": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_staging_password_ok_rejects_wrong_deployment_or_empty(monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "STAGING_LOGIN_PASSWORD", PASSWORD)
    assert auth.staging_password_ok(PASSWORD) is False
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    assert auth.staging_password_ok("") is False
    assert auth.staging_password_ok(PASSWORD) is True


def test_production_refuses_staging_password_env(monkeypatch):
    import os

    from app import env_guard

    env = {**os.environ, "UBYHOST_STAGING_LOGIN_PASSWORD": "nope", "UBYHOST_GUEST_PIN": "1"}
    with pytest.raises(env_guard.EnvGuardError, match="staging"):
        env_guard.validate_runtime_env(
            deployment="production",
            guest_pin_required=True,
            environ=env,
        )
