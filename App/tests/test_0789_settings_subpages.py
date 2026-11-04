"""0789a: /settings is an index; each group has its own server-rendered sub-page.

The index lists nine rows in order. Each /settings/<group> returns 200 and
renders its own section ids; the three pages that keep their own route
(archive, entities, privacy requests) still return 200.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "settings-subpages-host"

INDEX_HREFS = [
    "/settings/account",
    "/settings/security",
    "/settings/phone",
    "/settings/data",
    "/entities",
    "/privacy-requests",
    "/settings/archived",
    "/settings/technical",
    "/settings/help",
]

GROUP_SECTIONS = {
    "account": ["settings-account"],
    "security": ["settings-security"],
    "phone": ["settings-phone"],
    # settings-privacy renders only when the host has ad consents, so a fresh host lacks it.
    "data": ["settings-archive", "settings-retention", "settings-data"],
    "technical": ["settings-technical", "settings-ubyport", "settings-audit"],
    # settings-version sits in the existing help group in settings.html.
    "help": ["settings-guide", "settings-legal", "settings-version"],
}


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        for table in ("alert", "audit", "apartment", "legal_entity"):
            db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (row["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (row["id"],))


@pytest.fixture()
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Settings Host", role="admin", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_settings_index_lists_nine_rows_in_order(host):
    response = host.get("/settings?lang=en")
    assert response.status_code == 200
    hrefs = re.findall(r'<a class="airbnb-index-row" href="([^"]+)"', response.text)
    assert hrefs == INDEX_HREFS
    assert 'id="settings-privacy-requests"' not in response.text


@pytest.mark.parametrize("group", sorted(GROUP_SECTIONS))
def test_settings_group_subpage_renders_its_sections(host, group):
    response = host.get(f"/settings/{group}?lang=en")
    assert response.status_code == 200
    for section_id in GROUP_SECTIONS[group]:
        assert f'id="{section_id}"' in response.text, section_id


@pytest.mark.parametrize("path", ["/settings/archived", "/entities", "/privacy-requests"])
def test_index_targets_still_load(host, path):
    assert host.get(f"{path}?lang=en").status_code == 200
