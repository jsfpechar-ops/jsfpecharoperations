"""0239: the ISDS return pages work signed out, by GET and POST, and keep nothing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture()
def client():
    db.init_db()
    return TestClient(app)


@pytest.mark.parametrize("path,text", [
    ("/stay-fees/databox/done", "Back from your data box"),
    ("/stay-fees/databox/error", "did not take the message"),
])
@pytest.mark.parametrize("method", ["get", "post"])
def test_return_pages_signed_out(client, path, text, method):
    response = getattr(client, method)(path + "?lang=en", follow_redirects=False)
    assert response.status_code == 200
    assert text in response.text
    assert 'href="/stay-fees"' in response.text


def test_return_page_ignores_and_hides_input(client):
    response = client.post(
        "/stay-fees/databox/done?dmID=dm987654321&secret=x",
        data={"password": "hunter2", "username": "abc"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "hunter2" not in response.text
    assert "dm987654321" not in response.text
    assert "<input" not in response.text.split("auth-card", 1)[1]


def test_return_page_czech(client):
    response = client.get("/stay-fees/databox/error?lang=cs", follow_redirects=False)
    assert response.status_code == 200
    assert "Datová schránka zprávu nepřijala" in response.text
