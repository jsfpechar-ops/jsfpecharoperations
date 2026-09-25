"""UX-130 (audit B-26): the password form names the account it belongs to.

A password manager identifies the entry it is updating by the username field in
the form. The choose/change-password form had three password inputs and no
username, so managers either offered to create a second entry or wrote the new
password against the wrong one. A hidden ``autocomplete="username"`` input fixes
that without adding a field the host has to fill in, and it has to be on both
branches -- the forced first-run screen and the in-app change screen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

TEMPLATE = (
    Path(__file__).resolve().parents[1] / "app" / "templates" / "account_password.html"
)
PASSWORD = "Secure-Password-123"
USERNAME = "ux130-host"

USERNAME_INPUT = re.compile(
    r'<input\b[^>]*\bname="username"[^>]*\bautocomplete="username"[^>]*>'
)


def _cleanup():
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


def _signed_in(*, must_change_password: bool) -> TestClient:
    db.init_db()
    _cleanup()
    auth.create_account(
        USERNAME, PASSWORD, "Ux 130", must_change_password=must_change_password
    )
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def forced_host():
    try:
        yield _signed_in(must_change_password=True)
    finally:
        _cleanup()


@pytest.fixture
def settled_host():
    try:
        yield _signed_in(must_change_password=False)
    finally:
        _cleanup()


def test_the_forced_first_run_form_names_the_account(forced_host):
    response = forced_host.get("/account/password?lang=en")
    assert response.status_code == 200
    inputs = USERNAME_INPUT.findall(response.text)
    assert inputs, "the first-run password form has no username field"
    assert f'value="{USERNAME}"' in inputs[0]


def test_the_in_app_change_form_names_the_account(settled_host):
    response = settled_host.get("/account/password?lang=en")
    assert response.status_code == 200
    inputs = USERNAME_INPUT.findall(response.text)
    assert inputs, "the change-password form has no username field"
    assert f'value="{USERNAME}"' in inputs[0]


def test_both_branches_of_the_template_carry_the_field():
    """The field cannot be added to one branch and forgotten in the other."""
    source = TEMPLATE.read_text(encoding="utf-8")
    forms = re.findall(r"<form\b[^>]*>(.*?)</form>", source, re.S)
    assert len(forms) == 2, "account_password.html should still have two branches"
    for body in forms:
        assert 'name="username"' in body
        assert 'autocomplete="username"' in body


def test_the_hidden_field_is_not_required_by_the_route():
    """A posted form without it must still change the password.

    The field exists for password managers, not for validation, so a manager
    that ignores hidden inputs cannot lock the host out of their own account.
    """
    client = _signed_in(must_change_password=False)
    try:
        response = client.post(
            "/account/password",
            data={
                "current_password": PASSWORD,
                "new_password": "Another-Secure-Password-456",
                "confirm_password": "Another-Secure-Password-456",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"].startswith("/settings")
    finally:
        _cleanup()
