"""FE-3: the Settings "Data protection" panel, and backup internals stay admin-only."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from tests.conftest import login_as



def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'settings-%'"):
        user_id = row["id"]
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def test_the_panel_renders_for_a_host_without_backup_internals():
    auth.create_account("settings-host@example.test", "Host", username="settings-host")
    page = _login("settings-host").get("/settings?lang=en")
    assert page.status_code == 200, page.text
    assert "Data protection" in page.text
    assert "Open data requests" in page.text
    assert "Last backup" not in page.text


def test_a_platform_admin_sees_the_backup_marker():
    auth.create_account("settings-admin@example.test", "Admin", role="admin", username="settings-admin")
    marker = config.DATA_DIR / "backups" / ".last_success.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {"at": "2026-09-28T03:30:00+00:00", "encrypted": True, "bytes": 123, "retention_days": 30}
        ),
        encoding="utf-8",
    )
    try:
        page = _login("settings-admin").get("/settings?lang=en")
        assert "Last backup" in page.text
        assert "encrypted" in page.text
    finally:
        marker.unlink()
