"""A temporary password must not travel in a URL.

Anything in a query string is kept by browser history, written to every proxy
and web-server access log on the way, and handed to the next site in the
Referer header. A live credential in there outlives the one-time handover it
was meant for.
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Tr0ub4dour-Test-Pass"


@pytest.fixture()
def admin():
    db.init_db()
    _purge()
    auth.create_account(
        "cred-admin", PASSWORD, "Credential admin", role="admin",
        must_change_password=False,
    )
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "cred-admin", "password": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303
        yield client
    _purge()


def _purge():
    for name in ("cred-admin", "cred-host"):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))
        if not row:
            continue
        for table in ("apartment", "legal_entity", "alert", "audit"):
            db.execute(
                f"UPDATE {table} SET owner_user_id = NULL WHERE owner_user_id = ?",
                (row["id"],),
            )
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def test_creating_a_host_shows_the_password_without_putting_it_in_the_url(admin):
    response = admin.post(
        "/admin/users",
        data={"username": "cred-host", "display_name": "New Host"},
        follow_redirects=False,
    )

    assert response.status_code == 200, "a redirect would carry the secret in Location"
    assert "Temporary password" in response.text
    location = response.headers.get("location", "")
    assert "password" not in location.lower()

    row = db.query_one("SELECT * FROM user_account WHERE username = 'cred-host'")
    assert row and row["must_change_password"]


def test_resetting_a_password_does_not_put_it_in_the_url(admin):
    admin.post(
        "/admin/users",
        data={"username": "cred-host", "display_name": "New Host"},
        follow_redirects=False,
    )
    row = db.query_one("SELECT * FROM user_account WHERE username = 'cred-host'")

    response = admin.post(
        f"/admin/users/{row['id']}/password", data={}, follow_redirects=False
    )

    assert response.status_code == 200
    assert "location" not in {key.lower() for key in response.headers}
    assert "credential-secret" in response.text, "the new password was never shown"
    assert "no longer works" in response.text


def test_the_shown_password_is_the_one_that_actually_works(admin):
    """A panel showing a password the host cannot log in with is worse than none."""
    import re

    response = admin.post(
        "/admin/users",
        data={"username": "cred-host", "display_name": "New Host"},
        follow_redirects=False,
    )
    shown = re.search(
        r'credential-secret">([^<]+)<', response.text
    )
    assert shown, response.text[:400]

    with TestClient(app) as fresh:
        login = fresh.post(
            "/login",
            data={"username": "cred-host", "password": shown.group(1).strip()},
            follow_redirects=False,
        )
        assert login.status_code == 303, "the displayed password did not work"
