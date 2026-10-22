"""0239: the ISDS return pages work signed out, by GET and POST, and keep nothing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
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


def _drop_return_host():
    for table in ("legal_acceptance", "ad_click", "audit"):
        db.execute(
            f"DELETE FROM {table} WHERE user_account_id = (SELECT id FROM user_account WHERE username = ?)"
            if table != "audit" else
            "DELETE FROM audit WHERE owner_user_id = (SELECT id FROM user_account WHERE username = ?)",
            ("databox-return-host",),
        )
    db.execute("DELETE FROM user_account WHERE username = ?", ("databox-return-host",))


def test_signed_in_without_a_pending_send_goes_to_stay_fees(client):
    from tests.conftest import login_as

    _drop_return_host()
    auth.create_account(
        "databox-return-host@example.test", "Return Demo", role="host", username="databox-return-host",
    )
    try:
        assert login_as(client, "databox-return-host", url="/login?lang=en", follow_redirects=False).status_code == 303
        response = client.get("/stay-fees/databox/done?lang=en", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/stay-fees?msg=")
        response = client.get("/stay-fees/databox/error", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/stay-fees?err=")
    finally:
        _drop_return_host()
