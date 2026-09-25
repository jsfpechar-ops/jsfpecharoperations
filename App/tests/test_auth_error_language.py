"""Auth errors reach the host in the language they are reading.

A signed-out visitor gets Czech by default, so an English error literal on a
Czech login form is the one message a stuck host cannot read -- and being
stuck is exactly when they read it. The routes now pass catalogue keys and
the templates translate them, so the language is decided where the page is
rendered rather than where the error was raised.
"""
from __future__ import annotations

import ast
import html
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app

APP = Path(__file__).resolve().parent.parent / "app"
PASSWORD = "Secure-Password-123"
USERNAME = "autherrhost"


def _cleanup() -> None:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not row:
        return
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
    db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


def _account(must_change: bool = True) -> int:
    db.init_db()
    _cleanup()
    return auth.create_account(
        USERNAME, PASSWORD, "Auth Error Host", must_change_password=must_change
    )


def _text(key: str, lang: str) -> str:
    return host_i18n.STRINGS[lang][key]


def _body(response) -> str:
    """The page as the host reads it: Jinja escapes apostrophes as &#39;."""
    return html.unescape(response.text)


# --- the two screens a stuck host actually lands on --------------------------


def test_a_wrong_password_is_explained_in_the_page_language():
    _account(must_change=False)
    try:
        for lang in ("en", "cs"):
            response = TestClient(app).post(
                f"/login?lang={lang}",
                data={"username": USERNAME, "password": "not-the-password"},
                follow_redirects=False,
            )
            assert response.status_code == 401
            assert _text("auth.error.bad_credentials", lang) in _body(response)
            # A template that forgot t() would print the key instead.
            assert "auth.error.bad_credentials" not in _body(response)
    finally:
        _cleanup()


def test_a_weak_new_password_is_explained_in_the_page_language():
    _account(must_change=False)
    try:
        client = TestClient(app)
        client.post(
            "/login", data={"username": USERNAME, "password": PASSWORD},
            follow_redirects=False,
        )
        for lang in ("en", "cs"):
            response = client.post(
                f"/account/password?lang={lang}",
                data={
                    "current_password": PASSWORD,
                    "new_password": "alllowercase123",
                    "confirm_password": "alllowercase123",
                },
                follow_redirects=False,
            )
            assert response.status_code == 400
            assert _text("auth.password.mixed_case", lang) in _body(response)
            assert "auth.password.mixed_case" not in _body(response)
    finally:
        _cleanup()


def test_a_wrong_temporary_password_is_explained_in_czech():
    """The forced first-login screen, which is where a new host starts."""
    _account(must_change=True)
    try:
        client = TestClient(app)
        client.post(
            "/login", data={"username": USERNAME, "password": PASSWORD},
            follow_redirects=False,
        )
        response = client.post(
            "/account/password?lang=cs",
            data={
                "current_password": "not-the-temporary-one",
                "new_password": PASSWORD,
                "confirm_password": PASSWORD,
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert _text("auth.error.temp_password_wrong", "cs") in _body(response)
        assert "auth.error.temp_password_wrong" not in _body(response)
    finally:
        _cleanup()


def test_mismatched_new_passwords_are_explained_in_czech():
    _account(must_change=True)
    try:
        client = TestClient(app)
        client.post(
            "/login", data={"username": USERNAME, "password": PASSWORD},
            follow_redirects=False,
        )
        response = client.post(
            "/account/password?lang=cs",
            data={
                "current_password": PASSWORD,
                "new_password": PASSWORD,
                "confirm_password": PASSWORD + "x",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert _text("auth.error.passwords_mismatch", "cs") in _body(response)
    finally:
        _cleanup()


# --- the guards that keep the literals from creeping back --------------------


def _placeholder_names(text: str) -> set:
    return {part.split(")")[0] for part in text.split("%(")[1:] if ")" in part}


def test_every_auth_error_key_exists_in_both_languages():
    keys = [
        key
        for key in host_i18n.STRINGS["en"]
        if key.startswith(("auth.error.", "auth.password."))
    ]
    assert len(keys) >= 18, f"the auth error catalogue lost keys: {sorted(keys)}"
    for key in keys:
        for lang in ("en", "cs"):
            text = host_i18n.STRINGS[lang].get(key)
            assert text, (key, lang)
            # An interpolating message must interpolate the same names in both.
            assert _placeholder_names(text) == _placeholder_names(
                host_i18n.STRINGS["en"][key]
            ), (key, lang)


def test_password_error_returns_a_key_that_exists():
    cases = {
        "auth.password.too_short": "Ab1",
        "auth.password.mixed_case": "alllowercase123",
        "auth.password.digit": "NoDigitsHereAtAll",
        "auth.password.too_long": "A1" + "a" * 255,
    }
    for key, password in cases.items():
        assert auth.password_error(password) == key, password
        for lang in ("en", "cs"):
            assert host_i18n.STRINGS[lang][key]
    assert auth.password_error(PASSWORD) == ""


def test_no_auth_route_still_carries_an_english_error_literal():
    """Every error the auth routes hand out is a key, never a sentence.

    The routes reach a template through three doors -- a ``{"error": ...}``
    context value, a plain ``Response``, and ``back(err=...)`` -- and all
    three must carry a key so the template can translate it.
    """
    source = (APP / "routes" / "admin_accounts.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="routes/admin_accounts.py")

    def call_name(node) -> str:
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return ""

    literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "error":
                    literals.append((node.lineno, value))
        if isinstance(node, ast.Call) and call_name(node) == "Response" and node.args:
            literals.append((node.lineno, node.args[0]))
        if isinstance(node, ast.Call) and call_name(node) == "_back":
            for keyword in node.keywords:
                if keyword.arg == "err":
                    literals.append((node.lineno, keyword.value))

    assert literals, "the auth route scan found nothing to check"
    offenders = [
        (line, node.value)
        for line, node in literals
        # Anything that is not a bare string is a call (``_flash(...)``,
        # ``str(exc)``) or a branch between two keys, so it resolves to a key.
        if isinstance(node, ast.Constant)
        and not (isinstance(node.value, str) and node.value.startswith("auth."))
    ]
    assert offenders == [], f"routes/admin_accounts.py still hardcodes English: {offenders}"
