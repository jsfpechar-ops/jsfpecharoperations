"""0461: every admin page shows the one admin tab strip, and each tab opens for an admin."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as

PREFIX = "wp0461-tabs-"
STRIP = re.compile(r'<nav class="ui-tabs".*?</nav>', re.S)
TAB = re.compile(r'<a class="ui-tab" href="([^"]+)"( aria-current="page")?>')
HREFS = [
    "/admin",
    "/admin/customers",
    "/admin/fakturace",
    "/admin/users",
    "/admin/incidents",
    "/admin/operations",
    "/admin/funnel",
]


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        demo.clear(row["id"])
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))
    db.execute("DELETE FROM email_outbox WHERE idempotency_key LIKE ?", (PREFIX + "%",))


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _account(name: str, role: str) -> int:
    return auth.create_account(str(PREFIX + name) + "@example.test", name.title(), role=role, username=PREFIX + name)


def _login(name: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, PREFIX + name, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def _strip(html: str) -> str:
    match = STRIP.search(html)
    assert match, "no admin tab strip on the page"
    return match.group(0)


@pytest.mark.parametrize("path", HREFS)
def test_every_admin_page_shows_the_same_strip_with_its_own_tab_current(path):
    _account("admin", "admin")
    client = _login("admin")
    response = client.get(path + "?lang=en")
    assert response.status_code == 200, path
    tabs = TAB.findall(_strip(response.text))
    assert [href for href, _ in tabs] == HREFS
    assert [href for href, current in tabs if current] == [path]


def test_customer_page_shows_the_strip_with_customers_current():
    _account("admin", "admin")
    guest = _account("guest", "host")
    client = _login("admin")
    response = client.get(f"/admin/customers/{guest}?lang=en")
    assert response.status_code == 200
    tabs = TAB.findall(_strip(response.text))
    assert [href for href, _ in tabs] == HREFS
    assert [href for href, current in tabs if current] == ["/admin/customers"]


def test_every_tab_link_opens_for_an_admin():
    _account("admin", "admin")
    client = _login("admin")
    for href in HREFS:
        assert client.get(href + "?lang=en").status_code == 200, href


def test_a_host_gets_no_admin_tab_strip():
    _account("host", "host")
    client = _login("host")
    for href in HREFS:
        response = client.get(href + "?lang=en", follow_redirects=False)
        assert response.status_code != 200, href
        assert 'class="ui-tabs"' not in response.text, href
