"""Task 0002: every account gets a login e-mail that only an admin can change."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

def _clean() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'acctmail-%'"):
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _admin_client() -> tuple[TestClient, int]:
    admin_id = auth.create_account("acctmail-admin@example.test", "Admin", role="admin", username="acctmail-admin")
    client = TestClient(app)
    response = login_as(client, "acctmail-admin", url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client, admin_id


def _without_email(user_id: int) -> None:
    """An account from before task 0002, which had no login e-mail."""
    db.execute("UPDATE user_account SET email = NULL WHERE id = ?", (user_id,))


def test_admin_sets_a_first_login_email_without_a_reason_and_no_mail():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    host_id = auth.create_account("acctmail-host@example.test", "Host", username="acctmail-host")
    _without_email(host_id)
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
    host_id = auth.create_account("old@example.com", "Host", username="acctmail-host")
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
    auth.create_account("taken@example.com", "One", username="acctmail-one")
    other = auth.create_account("acctmail-two@example.test", "Two", username="acctmail-two")
    _without_email(other)
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
    host_id = auth.create_account("acctmail-host@example.test", "Host", username="acctmail-host")
    client = TestClient(app)
    login_as(client, "acctmail-host", url="/login?lang=en", follow_redirects=False)
    _without_email(host_id)
    response = client.post(
        f"/admin/users/{host_id}/email",
        data={"email": "mine@example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert db.query_one("SELECT email FROM user_account WHERE id = ?", (host_id,))["email"] is None


def test_admin_creates_a_host_by_email_and_an_invitation_goes_out():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    response = client.post(
        "/admin/users",
        data={"display_name": "New", "email": "Acctmail-New@Example.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "msg=" in response.headers["location"]
    row = db.query_one(
        "SELECT id, email, username, password_hash FROM user_account WHERE email = ?",
        ("acctmail-new@example.com",),
    )
    assert row["username"].startswith("acctmail-new-")
    assert row["password_hash"] == ""
    invite = db.query_one(
        "SELECT kind, payload FROM email_outbox WHERE owner_user_id = ? AND kind = 'account_invite'",
        (row["id"],),
    )
    assert invite is not None
    token_row = db.query_one(
        "SELECT purpose FROM login_token WHERE user_account_id = ? AND used_at IS NULL", (row["id"],)
    )
    assert token_row["purpose"] == "invite"


def test_creating_a_host_needs_a_valid_unused_email():
    db.init_db()
    _clean()
    client, _admin = _admin_client()
    bad = client.post("/admin/users", data={"email": "not-an-address"}, follow_redirects=False)
    assert "err=" in bad.headers["location"]
    taken = client.post(
        "/admin/users", data={"email": "acctmail-admin@example.test"}, follow_redirects=False
    )
    assert "err=" in taken.headers["location"]


def test_the_invitation_secret_is_never_shown_redirected_or_stored_in_clear():
    """What test_credential_handling guarded for temporary passwords (task 0003).

    The admin never sees the host's secret: it is not in the page, not in the
    redirect URL, and the stored mail body carries the marker instead of it.
    """
    from app import login_link, mail

    db.init_db()
    _clean()
    client, _admin = _admin_client()
    issued = []
    original = login_link.issue

    def spy(*args, **kwargs):
        token = original(*args, **kwargs)
        issued.append(token)
        return token

    login_link.issue = spy
    try:
        response = client.post(
            "/admin/users",
            data={"email": "acctmail-secret@example.com"},
            follow_redirects=False,
        )
    finally:
        login_link.issue = original
    assert len(issued) == 1
    token = issued[0]
    assert token not in response.headers["location"]
    page = client.get(response.headers["location"])
    assert token not in page.text
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE kind = 'account_invite' ORDER BY id DESC"
    )
    assert token not in row["payload"]
    assert mail.CLAIM_SECRET_MARKER in row["payload"]
