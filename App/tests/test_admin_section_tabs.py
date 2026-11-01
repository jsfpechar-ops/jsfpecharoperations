"""0472: every admin page shows the same admin tab strip, with its own tab current.

The strip is the section's tab nav (plain links, no JavaScript).
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as

PREFIX = "wp0472-tabs-"

ADMIN_HREFS = [
    "/admin",
    "/admin/customers",
    "/admin/fakturace",
    "/admin/incidents",
    "/admin/operations",
    "/admin/funnel",
]

ADMIN_PAGES = {
    "/admin": "/admin",
    "/admin/customers": "/admin/customers",
    "/admin/fakturace": "/admin/fakturace",
    "/admin/incidents": "/admin/incidents",
    "/admin/operations": "/admin/operations",
    "/admin/funnel": "/admin/funnel",
}


def _cleanup() -> None:
    for row in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        demo.clear(row["id"])
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _account(name: str, role: str) -> None:
    auth.create_account(
        str(PREFIX + name) + "@example.test", name.title(), role=role, username=PREFIX + name
    )


def _login(name: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, PREFIX + name, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def _tabs(html: str) -> list[tuple[str, bool]]:
    """The (href, is_current) pairs of the first tab nav on the page (ui-tabs or sub-tabs)."""
    nav = re.search(r'<nav class="(?:ui-tabs|sub-tabs)[ "].*?</nav>', html, re.S)
    assert nav, "no ui-tabs nav on the page"
    return [
        (href, 'aria-current="page"' in attrs)
        for href, attrs in re.findall(r'<a class="(?:ui-tab|sub-tab)" href="([^"]+)"([^>]*)>', nav.group(0))
    ]


def test_admin_pages_share_one_admin_strip_with_the_current_tab_marked():
    _account("admin", "admin")
    client = _login("admin")
    for path, current in ADMIN_PAGES.items():
        response = client.get(path + "?lang=en", follow_redirects=False)
        assert response.status_code == 200, (path, response.status_code)
        tabs = _tabs(response.text)
        assert [href for href, _ in tabs] == ADMIN_HREFS, path
        assert [href for href, is_current in tabs if is_current] == [current], path


def test_a_host_cannot_open_the_admin_only_pages():
    _account("host", "host")
    client = _login("host")
    for path in ("/admin/users", "/admin/operations"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (302, 303, 403, 404), (path, response.status_code)
