"""UX-127 (audit B-23): auth copy polish.

Five loose ends: the 2FA field had a different name from its own title, the CS
change-password lede used the IT word "relace", "autentizátor" read stiffly,
"Start over" didn't say what it starts over, and a successful in-app password
change dumped the host on the dashboard instead of back in Settings.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
NEW_PASSWORD = "Another-Secure-Password-456"
LANGS = ("en", "cs")


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username LIKE 'ux127-%'")
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account("ux127-host", PASSWORD, "Ux 127", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": "ux127-host", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_the_2fa_field_has_the_same_name_as_its_title():
    for lang in LANGS:
        assert host_i18n.translate(lang, "account.2fa.code_label") == host_i18n.translate(
            lang, "account.2fa.code_title"
        )


def test_start_over_says_what_it_starts_over():
    assert host_i18n.translate("en", "account.2fa.start_over") == "Use a different account"
    assert host_i18n.translate("cs", "account.2fa.start_over") == "Přihlásit se jiným účtem"


def test_the_czech_change_password_lede_drops_the_it_jargon():
    lede = host_i18n.translate("cs", "account.password.change_lede")
    assert lede == "Změnou hesla se odhlásíte na ostatních zařízeních."
    assert "relace" not in lede


def test_no_stiff_authenticator_wording_survives():
    for lang in LANGS:
        for key in host_i18n.STRINGS[lang]:
            text = host_i18n.STRINGS[lang][key]
            if not isinstance(text, str):
                continue
            assert "autentizátor" not in text, (lang, key)


def test_changing_the_password_returns_to_settings(host):
    response = host.post(
        "/account/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/settings?")
    assert location.endswith("#settings-account")


def test_the_forced_first_login_still_carries_on(host):
    """The first-run branch must keep going, not bounce back to Settings."""
    _cleanup()
    auth.create_account("ux127-forced", PASSWORD, "Ux 127 Forced", must_change_password=True)
    client = TestClient(app)
    assert (
        client.post(
            "/login?lang=en",
            data={"username": "ux127-forced", "password": PASSWORD},
            follow_redirects=False,
        ).status_code
        == 303
    )
    response = client.post(
        "/account/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/?")
