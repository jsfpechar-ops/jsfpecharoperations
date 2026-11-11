"""1120b: the guest-details mail switch on Settings > Account."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, guest_mail_pref
from app.main import app
from tests.conftest import login_as

USERNAME = "guest-mail-pref-page"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (user["id"],))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        "guest-mail-pref-page@example.test", "Pref Page", role="host", username=USERNAME
    )
    client = TestClient(app)
    logged_in = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert logged_in.status_code == 303
    try:
        yield client, owner_id
    finally:
        _cleanup()


def test_the_row_is_shown_and_checked_by_default(host):
    client, _owner_id = host
    page = client.get("/settings/account?lang=en")
    assert page.status_code == 200
    assert 'id="settings-guest-details-mail"' in page.text
    form = page.text.split('id="settings-guest-details-mail"', 1)[1].split("</form>", 1)[0]
    assert "Guest details in the confirmation e-mail" in form
    assert " checked" in form
    assert "<noscript><button" in form


def test_the_row_is_in_czech(host):
    client, _owner_id = host
    page = client.get("/settings/account?lang=cs")
    assert "Údaje o hostech v potvrzovacím e-mailu" in page.text


def test_posting_without_enabled_turns_it_off_and_back_on(host):
    client, owner_id = host
    response = client.post("/account/guest-details-mail", data={}, follow_redirects=False)
    assert response.status_code == 303
    assert guest_mail_pref.switch_on(owner_id) is False
    response = client.post(
        "/account/guest-details-mail", data={"enabled": "1"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert guest_mail_pref.switch_on(owner_id) is True
    page = client.get("/settings/account?lang=en")
    form = page.text.split('id="settings-guest-details-mail"', 1)[1].split("</form>", 1)[0]
    assert " checked" in form
