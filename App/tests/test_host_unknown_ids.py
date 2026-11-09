"""An unknown or foreign id in a host page URL is a 404 page, not a redirect."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USER = "unknownidshost"


@pytest.fixture
def client():
    db.init_db()
    auth.create_account(f"{USER}@example.test", "Unknown Ids", username=USER)
    c = TestClient(app)
    assert login_as(c, USER, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield c
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (USER,))
    if row:
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


@pytest.mark.parametrize(
    "path",
    ["/apartments/999999", "/reservations/999999", "/guests/999999", "/stay-fees/999999"],
)
def test_unknown_id_is_a_404_page(client, path):
    page = client.get(path, headers={"accept": "text/html"}, follow_redirects=False)
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
