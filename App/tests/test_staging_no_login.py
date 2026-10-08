"""Render staging with UBYHOST_STAGING_NO_LOGIN: every visitor is the first admin."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app


@pytest.fixture
def client_for(monkeypatch):
    db.init_db()

    def make(deployment: str, no_login: bool) -> TestClient:
        monkeypatch.setattr(config, "DEPLOYMENT", deployment)
        monkeypatch.setattr(config, "STAGING_NO_LOGIN", no_login)
        if not db.query_one("SELECT id FROM user_account WHERE role = 'admin' AND active = 1"):
            auth.create_account("no-login@example.test", "No Login", role="admin", username="no-login")
        return TestClient(app, follow_redirects=False)

    return make


def test_staging_no_login_skips_login_and_acceptance(client_for):
    client = client_for("staging", True)
    page = client.get("/login")
    assert page.status_code == 303
    assert page.headers["location"] == "/"
    guide = client.get("/guide")
    assert guide.status_code == 200


def test_flag_is_ignored_outside_staging(client_for):
    client = client_for("production", True)
    response = client.get("/guide")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_staging_without_flag_still_needs_login(client_for):
    client = client_for("staging", False)
    response = client.get("/guide")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
