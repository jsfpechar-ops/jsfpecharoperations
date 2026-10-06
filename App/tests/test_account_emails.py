"""Task 0002: every account gets a login e-mail that only an admin can change."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Account-Email-Pass-1"


def _clean() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'acctmail-%'"):
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _admin_client() -> tuple[TestClient, int]:
    admin_id = auth.create_account(
        "acctmail-admin", PASSWORD, "Admin", role="admin", must_change_password=False
    )
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": "acctmail-admin", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client, admin_id


def test_admin_sets_a_first_login_email_without_a_reason_and_no_mail():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    host_id = auth.create_account("acctmail-host", PASSWORD, "Host", must_change_password=False)
    page = client.get("/admin/users")
    assert "users-missing-email" in page.text
    response = client.post(
        f"/admin/users/{host_id}/email",
        data={"email": "Host@Example.COM"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one("SELECT email, email_verified_at FROM user_account WHERE id = ?", (host_id,))
    assert row["email"] == "host@example.com"
    assert row["email_verified_at"] is None
    audit = db.query_one(
        "SELECT action, detail FROM audit WHERE owner_user_id = ? ORDER BY id DESC", (host_id,)
    )
    assert audit["action"] == "email_set"
    assert "host@example.com" not in audit["detail"]
    assert not db.query("SELECT id FROM email_outbox WHERE owner_user_id = ?", (host_id,))


def test_changing_an_email_needs_a_reason_notifies_both_and_ends_sessions():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    host_id = auth.create_account(
        "acctmail-host", PASSWORD, "Host", must_change_password=False, email="old@example.com"
    )
    before = db.query_one("SELECT session_version FROM user_account WHERE id = ?", (host_id,))
    refused = client.post(
        f"/admin/users/{host_id}/email",
        data={"email": "new@example.com", "reason": ""},
        follow_redirects=False,
    )
    assert "err=" in refused.headers["location"]
    assert db.query_one("SELECT email FROM user_account WHERE id = ?", (host_id,))["email"] == "old@example.com"
    response = client.post(
        f"/admin/users/{host_id}/email",
        data={"email": "new@example.com", "reason": "Lost mailbox, verified by IČO"},
        follow_redirects=False,
    )
    assert "msg=" in response.headers["location"]
    after = db.query_one("SELECT email, session_version FROM user_account WHERE id = ?", (host_id,))
    assert after["email"] == "new@example.com"
    assert after["session_version"] == before["session_version"] + 1
    sent_to = {
        row["to_email"]
        for row in db.query(
            "SELECT to_email FROM email_outbox WHERE owner_user_id = ? AND kind = 'email_changed'",
            (host_id,),
        )
    }
    assert sent_to == {"old@example.com", "new@example.com"}
    audit = db.query_one(
        "SELECT action, detail FROM audit WHERE owner_user_id = ? ORDER BY id DESC", (host_id,)
    )
    assert audit["action"] == "email_changed"
    assert "reason=Lost mailbox" in audit["detail"]
    assert "new@example.com" not in audit["detail"]


def test_an_email_already_used_by_another_account_is_refused():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    auth.create_account(
        "acctmail-one", PASSWORD, "One", must_change_password=False, email="taken@example.com"
    )
    other = auth.create_account("acctmail-two", PASSWORD, "Two", must_change_password=False)
    response = client.post(
        f"/admin/users/{other}/email",
        data={"email": "taken@example.com"},
        follow_redirects=False,
    )
    assert "err=" in response.headers["location"]
    assert db.query_one("SELECT email FROM user_account WHERE id = ?", (other,))["email"] is None


def test_a_host_cannot_change_login_emails():
    db.init_db()
    _clean()
    host_id = auth.create_account("acctmail-host", PASSWORD, "Host", must_change_password=False)
    client = TestClient(app)
    client.post(
        "/login?lang=en",
        data={"username": "acctmail-host", "password": PASSWORD},
        follow_redirects=False,
    )
    response = client.post(
        f"/admin/users/{host_id}/email",
        data={"email": "mine@example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert db.query_one("SELECT email FROM user_account WHERE id = ?", (host_id,))["email"] is None


def test_admin_can_create_a_host_with_a_login_email():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    response = client.post(
        "/admin/users",
        data={
            "display_name": "New",
            "username": "acctmail-new",
            "email": "New@Example.com",
            "password": "Temporary-Pass-123",
        },
    )
    assert response.status_code == 200
    row = db.query_one("SELECT email FROM user_account WHERE username = 'acctmail-new'")
    assert row["email"] == "new@example.com"
