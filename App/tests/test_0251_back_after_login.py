"""Task 0251: Back after login must not look like a logout.

A signed-in host who presses Back from the first page after logging in lands on
the spent e-mail link. That link must send them to the app, not say "expired".
A logged-out visitor still sees the expired page.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

EMAIL = "back-after-login@example.test"
USERNAME = "back-after-login-host"


@pytest.fixture
def host():
    db.init_db()
    db.execute("DELETE FROM user_account WHERE email = ?", (EMAIL,))
    user_id = auth.create_account(EMAIL, "Back Host", username=USERNAME)
    yield user_id
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_signed_in_host_on_a_spent_link_goes_to_the_app(host):
    client = TestClient(app)
    login_as(client, USERNAME)
    response = client.get("/login/link?t=bogus", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logged_out_visitor_still_sees_the_expired_link(host):
    response = TestClient(app).get("/login/link?t=bogus", follow_redirects=False)
    assert response.status_code == 410
