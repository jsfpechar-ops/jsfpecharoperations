"""A deep link must survive one mistyped password.

The form read ``next`` from the query string but posted to plain ``/login``, so
after any error the page re-rendered with ``next=""`` and the host who followed
a link from an e-mail landed on the dashboard instead. Focus also went back to
the username field, which was already filled in.
"""
from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
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
    auth.create_account(USERNAME, PASSWORD, "Login Next", must_change_password=False)
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
    return TestClient(app).post(
        "/login",
        data={"username": USERNAME, "password": "not-the-password", "next": next_value},
        follow_redirects=False,
    )


def test_the_form_carries_the_deep_link_it_was_opened_with():
    page = TestClient(app).get(f"/login?next={DEEP_LINK}")
    assert page.status_code == 200
    assert _hidden_next(page) == DEEP_LINK


def test_a_wrong_password_keeps_the_deep_link_in_the_form(host):
    response = _failed_attempt(DEEP_LINK)
    assert response.status_code == 401, response.text
    assert _hidden_next(response) == DEEP_LINK


def test_the_deep_link_still_lands_the_host_after_a_failed_attempt(host):
    assert _failed_attempt(DEEP_LINK).status_code == 401
    response = TestClient(app).post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD, "next": DEEP_LINK},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == DEEP_LINK


@pytest.mark.parametrize(
    "hostile",
    ("https://evil.example/steal", "//evil.example/steal", "/\\evil.example"),
)
def test_a_deep_link_off_this_site_is_dropped_on_an_error(host, hostile):
    response = _failed_attempt(hostile)
    assert response.status_code == 401
    assert _hidden_next(response) == "/"


def test_focus_lands_on_the_password_only_after_an_error(host):
    clean = TestClient(app).get("/login")
    assert clean.status_code == 200
    username_input = re.search(r'<input type="text" id="username"[^>]*>', clean.text)
    assert username_input, clean.text
    assert " autofocus" in username_input.group(0)

    failed = _failed_attempt(DEEP_LINK)
    username_input = re.search(r'<input type="text" id="username"[^>]*>', failed.text)
    password_input = re.search(r'<input type="password" id="password"[^>]*>', failed.text)
    assert username_input and password_input, failed.text
    assert " autofocus" not in username_input.group(0)
    assert " autofocus" in password_input.group(0)
