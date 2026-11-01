"""UX-144: disabling a host asks first.

Disable was the only destructive control in the admin app that fired on a single
click -- every archive, purge and link regeneration elsewhere already confirms.
0480: the disable control lives on the customer page now (the Users page is gone),
so the confirm is asserted there. The lede went with the Users page.
"""
from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

ADMIN = "users-confirm-admin"
HOST = "users-confirm-host"
NAME = "Confirmable Host"

COPY = {
    "en": {
        "confirm": "Disable %(name)s? They can't sign in until you enable them again.",
    },
    "cs": {
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
    auth.create_account(f"{ADMIN}@example.test", "Confirm Admin", role="admin", username=ADMIN)
    auth.create_account(f"{HOST}@example.test", NAME, username=HOST)
    client = TestClient(app)
    response = login_as(client, ADMIN, url="/login?lang=en", follow_redirects=False)
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
        rf'<form method="post" action="/admin/customers/{user_id}/aktivovat"[^>]*>', page
    )
    assert match, "the toggle form is missing"
    return html.unescape(match.group(0))


def _host_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (HOST,))["id"]


# --- the copy --------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_confirm_message_is_in_both_dictionaries(lang):
    assert host_i18n.STRINGS[lang]["confirm.disable_user"] == COPY[lang]["confirm"]


# --- the confirm -----------------------------------------------------------------------


def test_disable_asks_before_it_fires(admin):
    form = _toggle_form(admin.get(f"/admin/customers/{_host_id()}?lang=en").text, _host_id())

    assert "data-confirm" in form
    assert "data-confirm-message" in form


def test_the_confirm_names_the_person(admin):
    form = _toggle_form(admin.get(f"/admin/customers/{_host_id()}?lang=en").text, _host_id())
    expected = COPY["en"]["confirm"] % {"name": NAME}

    assert expected in form


def test_the_confirm_is_translated(admin):
    form = _toggle_form(admin.get(f"/admin/customers/{_host_id()}?lang=cs").text, _host_id())

    assert COPY["cs"]["confirm"] % {"name": NAME} in form


def test_the_confirm_uses_the_username_when_there_is_no_name(admin):
    db.execute("UPDATE user_account SET display_name = '' WHERE id = ?", (_host_id(),))
    form = _toggle_form(admin.get(f"/admin/customers/{_host_id()}?lang=en").text, _host_id())

    assert COPY["en"]["confirm"] % {"name": HOST} in form


def test_enabling_does_not_ask(admin):
    """Turning an account back on destroys nothing, so it stays one click."""
    db.execute("UPDATE user_account SET active = 0 WHERE id = ?", (_host_id(),))
    form = _toggle_form(admin.get(f"/admin/customers/{_host_id()}?lang=en").text, _host_id())

    assert "data-confirm" not in form


def test_the_confirm_round_trips_through_the_route(admin):
    """The message is what the dialog shows; the action still works."""
    response = admin.post(
        f"/admin/customers/{_host_id()}/aktivovat", follow_redirects=False
    )
    assert response.status_code == 303
    assert db.query_one(
        "SELECT active FROM user_account WHERE username = ?", (HOST,)
    )["active"] == 0
