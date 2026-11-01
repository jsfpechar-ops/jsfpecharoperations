"""0718: the Menu page (/menu) that the phone tab bar links to."""
import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.test_stay_fee_detail import login_as

MENU_LINKS = ('href="/cleaning"', 'href="/stay-fees"', 'href="/payments"',
              'href="/settings"', 'href="/guide"', 'action="/logout"')


def _signed_in(role):
    db.init_db()
    username = f"menu-{role}-{secrets.token_hex(4)}"
    auth.create_account(f"{username}@example.test", "Menu QA", role=role, username=username)
    client = TestClient(app)
    logged_in = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert logged_in.status_code == 303
    return client


def test_menu_page_links_every_destination_for_a_host():
    client = _signed_in("host")
    response = client.get("/menu?lang=en")
    assert response.status_code == 200
    for fragment in MENU_LINKS:
        assert fragment in response.text, fragment
    assert 'href="/admin"' not in response.text


def test_menu_page_shows_admin_link_to_admins():
    client = _signed_in("admin")
    response = client.get("/menu?lang=en")
    assert response.status_code == 200
    assert 'href="/admin"' in response.text


def test_menu_page_needs_a_signed_in_user():
    response = TestClient(app).get("/menu?lang=en", follow_redirects=False)
    assert response.status_code != 200
