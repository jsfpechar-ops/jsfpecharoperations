"""UX-143: the Properties table stopped colouring a fact, and the CTA got its icon.

Automation mode is a fact about a property, not a status, so it no longer wears
a blue pill next to the red/amber/green Setup pill -- DESIGN.md asks for one
coloured chip column, not two. The page-header CTA for the frequent action
("Add a property") was also the only coral button in the app without the leading
icon DESIGN.md asks for, while the secondary "Update calendars" had one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "properties-table-host"

_COMPONENTS = Path(__file__).resolve().parents[1] / "app" / "templates" / "_components.html"

MODES = [
    ("immediate", "apartments.automation.immediate", None),
    ("scheduled", "apartments.automation.scheduled", 24),
    ("manual", "apartments.automation.manual", None),
]


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


def _seed_properties() -> None:
    """One account, one operator and one property per automation mode."""
    auth.create_account(f"{USERNAME}@example.test", "Properties Host", username=USERNAME)
    owner_id = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Properties s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@properties.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    for index, (mode, _key, hours) in enumerate(MODES):
        db.insert(
            "apartment",
            {
                "legal_entity_id": entity_id,
                "owner_user_id": owner_id,
                "internal_name": f"Flat {mode}",
                "addr_obec": "Praha",
                "addr_house_no": str(index + 1),
                "addr_zip": "12000",
                "permalink_token": f"properties{mode}",
                "permalink_pin": "123456",
                "automation_mode": mode,
                "submit_after_hours": hours if hours is not None else 24,
                "active": 1,
                "created_at": db.utcnow(),
            },
        )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    _seed_properties()
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def empty_host():
    """An account with nothing in it, so the properties list shows its empty state."""
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Properties Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _cell(page: str, lang: str, column_key: str) -> str:
    """The <td> for one column, so an assertion cannot match another cell."""
    label = host_i18n.STRINGS[lang][column_key]
    match = re.search(
        r'<td class="([^"]*)" data-label="' + re.escape(label) + r'">(.*?)</td>',
        page,
        re.S,
    )
    assert match, f"no cell for {column_key}"
    return match.group(0)


# --- the automation column -------------------------------------------------------------


def test_technical_automation_column_is_not_on_property_landing(host):
    page = host.get("/apartments?lang=en").text
    assert '<th>Automation</th>' not in page
    assert 'href="/automation"' in page  # Property tools still reaches overview.


@pytest.mark.parametrize("mode,key,hours", MODES)
def test_every_automation_mode_remains_accessible_in_context(host, mode, key, hours):
    apartment = db.query_one("SELECT id FROM apartment WHERE internal_name = ?", (f"Flat {mode}",))
    page = host.get(f"/apartments/{apartment['id']}?lang=en").text
    assert 'id="automation"' in page
    assert f"/automation#apartment-{apartment['id']}" in page


def test_property_tools_translates(host):
    page = host.get("/apartments?lang=cs").text
    assert host_i18n.translate('cs', 'host.property_tools') in page
    assert 'href="/automation"' in page


def test_the_setup_pill_survives(host):
    """One coloured chip column stays: the one that is a status."""
    page = host.get("/apartments?lang=en").text

    assert re.search(r'<span class="pill (amber|green|red)">', page)


# --- the add-property CTA --------------------------------------------------------------


def _add_cta(page: str) -> str:
    match = re.search(r"<a[^>]*href=\"/apartments/new\"[^>]*>.*?</a>", page, re.S)
    assert match, "the Add a property CTA is missing"
    return match.group(0)


def test_the_add_property_cta_carries_the_property_icon(host):
    cta = _add_cta(host.get("/apartments?lang=en").text)

    assert 'class="btn primary sync-btn"' in cta
    assert 'class="sync-btn-icon" aria-hidden="true"' in cta
    assert 'class="nav-icon"' in cta
    assert host_i18n.STRINGS["en"]["apartments.add"] in cta


def test_the_add_property_cta_icon_is_the_property_mark(host):
    """The house mark, not whatever icon happened to be next in the macro."""
    cta = _add_cta(host.get("/apartments?lang=en").text)

    assert _nav_icon_svg("property") in cta
    assert _nav_icon_svg("calendar") not in cta


def _nav_icon_svg(name: str) -> str:
    lines = _COMPONENTS.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if f"{{% elif name == '{name}' %}}" in line:
            return lines[index + 1].strip()
    raise AssertionError(f"no icon named {name}")


def test_the_add_property_cta_translates(host):
    cta = _add_cta(host.get("/apartments?lang=cs").text)

    assert host_i18n.STRINGS["cs"]["apartments.add"] in cta


# --- the empty state ------------------------------------------------------------------


def test_the_empty_state_still_shows_one_primary_button(empty_host):
    page = empty_host.get("/apartments?lang=en").text
    panel = re.search(r'<div class="panel empty">(.*?)</div>', page, re.S)

    assert panel, "the empty state disappeared"
    assert panel.group(1).count('class="btn primary') == 1
    assert host_i18n.STRINGS["en"]["apartments.empty.entity"] in panel.group(1)


def test_the_header_cta_is_hidden_while_the_list_is_empty(empty_host):
    """The empty state already names the one first step, so the header stays quiet."""
    assert 'href="/apartments/new"' not in empty_host.get("/apartments?lang=en").text


def test_the_header_cta_is_back_once_there_is_a_property(host):
    page = host.get("/apartments?lang=en").text

    assert page.count('href="/apartments/new"') == 1
