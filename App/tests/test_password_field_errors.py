"""Where the password screen puts its error, and what it calls the first field.

The two password screens used to answer a rejected submission with one alert
above the form. Three fields look identical on screen and read identically to a
screen reader, so "the passwords do not match" named nothing the host could act
on. Each message now sits under the field that caused it, that field is marked
`aria-invalid`, and the rules hint is linked to the new-password field so it is
read out with it.

The forced first run also has a field that is not a "current" password at all --
it holds the temporary one the host was handed -- and now says so.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from app.routes.admin_accounts import _password_error

PASSWORD = "Secure-Password-123"
TEMP_PASSWORD = "Temporary-Password-123"
USERNAME = "password-field-host"


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


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


def _sign_in(*, must_change_password: bool, lang: str = "en") -> TestClient:
    _cleanup()
    password = TEMP_PASSWORD if must_change_password else PASSWORD
    auth.create_account(
        USERNAME, password, "Field Errors", must_change_password=must_change_password
    )
    client = TestClient(app)
    response = client.post(
        "/login?lang={}".format(lang),
        data={"username": USERNAME, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return client


@pytest.fixture
def host():
    client = _sign_in(must_change_password=False)
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def first_run_host():
    client = _sign_in(must_change_password=True)
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def czech_first_run_host():
    client = _sign_in(must_change_password=True, lang="cs")
    try:
        yield client
    finally:
        _cleanup()


def _body(response) -> str:
    """The page as the host reads it: Jinja escapes apostrophes as &#39;."""
    return html.unescape(response.text)


def _text(key: str, lang: str = "en") -> str:
    return host_i18n.STRINGS[lang][key]


def _input(body: str, field: str) -> str:
    match = re.search(r'<input[^>]*id="%s"[^>]*>' % field, body)
    assert match, body
    return match.group(0)


def _invalid_fields(body: str) -> set:
    return {
        field
        for field in ("current_password", "new_password", "confirm_password")
        if 'aria-invalid="true"' in _input(body, field)
    }


def _reject(client, *, current: str, new: str, confirm: str):
    response = client.post(
        "/account/password",
        data={"current_password": current, "new_password": new, "confirm_password": confirm},
        follow_redirects=False,
    )
    assert response.status_code == 400, response.text
    return _body(response)


# --- the message lands under the field that caused it ----------------------


def test_a_wrong_current_password_marks_the_current_field(first_run_host):
    body = _reject(first_run_host, current="not-the-temporary-one", new=PASSWORD, confirm=PASSWORD)

    assert _text("auth.error.temp_password_wrong") in body
    assert _invalid_fields(body) == {"current_password"}


def test_the_message_sits_below_the_field_it_names(first_run_host):
    body = _reject(first_run_host, current="not-the-temporary-one", new=PASSWORD, confirm=PASSWORD)

    field = body.index('id="current_password"')
    next_field = body.index('id="new_password"')
    message = body.index(_text("auth.error.temp_password_wrong"))
    assert field < message < next_field


def test_the_message_is_tied_to_the_field_for_a_screen_reader(first_run_host):
    body = _reject(first_run_host, current="not-the-temporary-one", new=PASSWORD, confirm=PASSWORD)

    assert 'aria-describedby="current_password-error"' in _input(body, "current_password")
    assert re.search(
        r'<p[^>]*id="current_password-error"[^>]*role="alert"[^>]*>'
        + re.escape(_text("auth.error.temp_password_wrong")),
        body,
    ), body


def test_a_mismatch_lands_on_the_repeat_field(first_run_host):
    body = _reject(first_run_host, current=TEMP_PASSWORD, new=PASSWORD, confirm=PASSWORD + "x")

    assert _text("auth.error.passwords_mismatch") in body
    assert _invalid_fields(body) == {"confirm_password"}
    assert 'aria-describedby="confirm_password-error"' in _input(body, "confirm_password")


def test_a_weak_new_password_lands_on_the_new_field(first_run_host):
    body = _reject(first_run_host, current=TEMP_PASSWORD, new="short", confirm="short")

    assert _text("auth.password.too_short") in body
    assert _invalid_fields(body) == {"new_password"}
    assert 'aria-describedby="new_password-hint new_password-error"' in _input(
        body, "new_password"
    )


def test_the_error_no_longer_sits_in_a_top_alert(first_run_host):
    body = _reject(first_run_host, current="not-the-temporary-one", new=PASSWORD, confirm=PASSWORD)

    assert 'class="auth-alert"' not in body


def test_the_same_field_marking_applies_on_the_settings_screen(host):
    body = _reject(host, current="not-the-real-one", new=PASSWORD, confirm=PASSWORD)

    assert _text("auth.error.current_password_wrong") in body
    assert _invalid_fields(body) == {"current_password"}
    assert 'class="banner err"' not in body


def test_a_mismatch_lands_on_the_repeat_field_on_the_settings_screen(host):
    body = _reject(host, current=PASSWORD, new=PASSWORD, confirm=PASSWORD + "x")

    assert _text("auth.error.passwords_mismatch") in body
    assert _invalid_fields(body) == {"confirm_password"}


# --- the rules hint is part of the field -----------------------------------


def test_the_rules_hint_is_linked_to_the_new_password(first_run_host):
    body = _body(first_run_host.get("/account/password"))

    assert 'aria-describedby="new_password-hint"' in _input(body, "new_password")
    assert re.search(
        r'id="new_password-hint"[^>]*>' + re.escape(_text("account.password.rules")), body
    ), body


def test_the_settings_screen_links_the_hint_too(host):
    body = _body(host.get("/account/password"))

    assert 'aria-describedby="new_password-hint"' in _input(body, "new_password")
    assert re.search(
        r'id="new_password-hint"[^>]*>' + re.escape(_text("account.password.rules")), body
    ), body


def test_the_hint_keeps_its_own_id_when_the_field_fails(first_run_host):
    body = _reject(first_run_host, current=TEMP_PASSWORD, new="short", confirm="short")

    assert body.count('id="new_password-hint"') == 1
    assert body.count('id="new_password-error"') == 1


# --- the message is the host's language ------------------------------------


def test_the_message_is_shown_in_czech(czech_first_run_host):
    body = _reject(
        czech_first_run_host, current="not-the-temporary-one", new=PASSWORD, confirm=PASSWORD
    )

    assert _text("auth.error.temp_password_wrong", "cs") in body
    assert _text("auth.error.temp_password_wrong") not in body
    assert _invalid_fields(body) == {"current_password"}


# --- the first field of the forced run says what it holds -------------------


def test_the_first_run_calls_the_first_field_temporary(first_run_host):
    body = _body(first_run_host.get("/account/password"))

    assert '<label for="current_password">' + _text("account.password.temporary") in body


def test_the_first_run_says_it_in_czech(czech_first_run_host):
    body = _body(czech_first_run_host.get("/account/password"))

    assert '<label for="current_password">' + _text("account.password.temporary", "cs") in body


def test_the_settings_screen_still_calls_it_current(host):
    body = _body(host.get("/account/password"))

    assert '<label for="current_password">' + _text("account.password.current") in body
    assert _text("account.password.temporary") not in body


def test_the_new_label_is_translated_in_both_languages():
    assert _text("account.password.temporary") == "Temporary password"
    assert _text("account.password.temporary", "cs") == "Dočasné heslo"


# --- the mapping itself ----------------------------------------------------


def test_each_error_knows_its_field():
    assert _password_error("auth.error.temp_password_wrong")["error_field"] == "current_password"
    assert _password_error("auth.error.current_password_wrong")["error_field"] == "current_password"
    assert _password_error("auth.error.passwords_mismatch")["error_field"] == "confirm_password"
    assert _password_error("auth.password.too_short")["error_field"] == "new_password"
    assert _password_error("auth.password.digit")["error_field"] == "new_password"


def test_every_field_an_error_can_name_exists_on_the_form(first_run_host):
    body = _body(first_run_host.get("/account/password"))

    for key in (
        "auth.error.temp_password_wrong",
        "auth.error.current_password_wrong",
        "auth.error.passwords_mismatch",
        "auth.password.too_short",
    ):
        assert 'id="%s"' % _password_error(key)["error_field"] in body


def test_the_field_error_is_not_left_grey():
    """`.auth-hint` sets a colour and comes after `.err-text` in app.css, so an
    equal-weight pairing would render the message as an ordinary hint."""
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text(
        encoding="utf-8"
    )
    rule = css.split(".auth-hint.err-text {", 1)[1].split("}", 1)[0]

    assert "color: var(--bad)" in rule
