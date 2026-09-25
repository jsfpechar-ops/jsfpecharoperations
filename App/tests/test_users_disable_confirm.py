"""UX-144: disabling a host asks first, and the lede drops the jargon.

Disable was the only destructive control in the admin app that fired on a single
click -- every archive, purge and link regeneration elsewhere already confirms.
The lede also explained password hashing to a host admin who only needs to know
the password cannot be read back.
"""
from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
ADMIN = "users-confirm-admin"
HOST = "users-confirm-host"
NAME = "Confirmable Host"

COPY = {
    "en": {
        "lede": "Create a private workspace for each host. Passwords are stored "
        "securely and can only be reset, never viewed.",
        "confirm": "Disable %(name)s? They can't sign in until you enable them again.",
    },
    "cs": {
        "lede": "Vytvořte soukromý pracovní prostor pro každého hostitele. Hesla jsou "
        "bezpečně uložená — lze je jen resetovat, nikdy zobrazit.",
        "confirm": "Vypnout účet %(name)s? Nebude se moci přihlásit, dokud ho znovu nezapnete.",
    },
}


def _cleanup():
    ids = [
        row["id"]
        for row in db.query(
            "SELECT id FROM user_account WHERE username IN (?, ?)", (ADMIN, HOST)
        )
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def admin():
    db.init_db()
    _cleanup()
    auth.create_account(
        ADMIN, PASSWORD, "Confirm Admin", role="admin", must_change_password=False
    )
    auth.create_account(HOST, PASSWORD, NAME, must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": ADMIN, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _toggle_form(page: str, user_id: int) -> str:
    """The Disable/Enable form for one specific row. The page lists every
    account in the database, so matching the first form would pick up rows
    other test files left behind. Jinja escapes the attribute, so unescape."""
    match = re.search(
        rf'<form method="post" action="/admin/users/{user_id}/toggle"[^>]*>', page
    )
    assert match, "the toggle form is missing"
    return html.unescape(match.group(0))


def _host_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (HOST,))["id"]


# --- the copy --------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_lede_is_in_both_dictionaries(lang):
    assert host_i18n.STRINGS[lang]["users.lede"] == COPY[lang]["lede"]


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_confirm_message_is_in_both_dictionaries(lang):
    assert host_i18n.STRINGS[lang]["confirm.disable_user"] == COPY[lang]["confirm"]


def test_the_lede_stopped_explaining_hashing():
    for lang in ("en", "cs"):
        assert "hash" not in host_i18n.STRINGS[lang]["users.lede"].lower()


# --- the confirm -----------------------------------------------------------------------


def test_disable_asks_before_it_fires(admin):
    form = _toggle_form(admin.get("/admin/users?lang=en").text, _host_id())

    assert "data-confirm" in form
    assert "data-confirm-message" in form


def test_the_confirm_names_the_person(admin):
    form = _toggle_form(admin.get("/admin/users?lang=en").text, _host_id())
    expected = COPY["en"]["confirm"] % {"name": NAME}

    assert expected in form


def test_the_confirm_is_translated(admin):
    form = _toggle_form(admin.get("/admin/users?lang=cs").text, _host_id())

    assert COPY["cs"]["confirm"] % {"name": NAME} in form


def test_the_confirm_uses_the_username_when_there_is_no_name(admin):
    db.execute("UPDATE user_account SET display_name = '' WHERE id = ?", (_host_id(),))
    form = _toggle_form(admin.get("/admin/users?lang=en").text, _host_id())

    assert COPY["en"]["confirm"] % {"name": HOST} in form


def test_enabling_does_not_ask(admin):
    """Turning an account back on destroys nothing, so it stays one click."""
    db.execute("UPDATE user_account SET active = 0 WHERE id = ?", (_host_id(),))
    form = _toggle_form(admin.get("/admin/users?lang=en").text, _host_id())

    assert "data-confirm" not in form


def test_the_confirm_round_trips_through_the_route(admin):
    """The message is what the dialog shows; the action still works."""
    response = admin.post(
        f"/admin/users/{_host_id()}/toggle", follow_redirects=False
    )
    assert response.status_code == 303
    assert db.query_one(
        "SELECT active FROM user_account WHERE username = ?", (HOST,)
    )["active"] == 0
