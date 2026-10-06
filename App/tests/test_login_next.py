"""A deep link must survive the trip through the login e-mail.

The form read ``next`` from the query string but posted to plain ``/login``, so
after any error the page re-rendered with ``next=""`` and the host who followed
a link from an e-mail landed on the dashboard instead. Since task 0003 the
deep link also rides along in the login link, so the host lands where they
were going after opening the mail.
"""
from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

USERNAME = "login-next-host"
DEEP_LINK = "/reservations/123"


def _cleanup():
    """Logging in writes audit rows owned by the account, so they go first."""
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


@pytest.fixture
def host():
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Login Next", username=USERNAME)
    try:
        yield USERNAME
    finally:
        _cleanup()


def _body(response):
    return html.unescape(response.text)


def _hidden_next(response) -> str:
    """The login form's own ``next``; the language switch has one too."""
    text = _body(response)
    start = text.index('<form method="post" action="/login"')
    end = text.index("</form>", start)
    match = re.search(r'<input type="hidden" name="next" value="([^"]*)"', text[start:end])
    assert match, text[start:end]
    return match.group(1)


def _failed_attempt(next_value: str):
    """A login form that comes back with an error (an address that is not one)."""
    return TestClient(app).post(
        "/login", data={"email": "not-an-address", "next": next_value}, follow_redirects=False
    )


def _link_from_the_mail(client: TestClient, next_value: str) -> str:
    """Ask for a link the way the form does, and read it from the outbox."""
    from app import mail

    response = client.post(
        "/login",
        data={"email": f"{USERNAME}@example.test", "next": next_value},
        follow_redirects=False,
    )
    assert response.status_code == 200, response.text
    row = db.query_one(
        "SELECT payload FROM email_outbox WHERE kind = 'login_link' ORDER BY id DESC"
    )
    import json

    body = mail.delivery_body(json.loads(row["payload"]))
    return re.search(r"/login/link\?t=([A-Za-z0-9_-]+)", body).group(1)


def test_the_form_carries_the_deep_link_it_was_opened_with():
    page = TestClient(app).get(f"/login?next={DEEP_LINK}")
    assert page.status_code == 200
    assert _hidden_next(page) == DEEP_LINK


def test_an_error_keeps_the_deep_link_in_the_form(host):
    response = _failed_attempt(DEEP_LINK)
    assert response.status_code == 400, response.text
    assert _hidden_next(response) == DEEP_LINK


def test_the_login_link_lands_the_host_on_the_deep_link(host):
    client = TestClient(app)
    token = _link_from_the_mail(client, DEEP_LINK)
    response = client.post("/login/link", data={"t": token}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == DEEP_LINK


@pytest.mark.parametrize(
    "hostile",
    ("https://evil.example/steal", "//evil.example/steal", "/\\evil.example"),
)
def test_a_deep_link_off_this_site_is_dropped(host, hostile):
    response = _failed_attempt(hostile)
    assert response.status_code == 400
    assert _hidden_next(response) == "/"
    client = TestClient(app)
    token = _link_from_the_mail(client, hostile)
    landed = client.post("/login/link", data={"t": token}, follow_redirects=False)
    assert landed.headers["location"] == "/"
