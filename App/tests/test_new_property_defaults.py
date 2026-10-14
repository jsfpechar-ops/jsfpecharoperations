"""A brand-new property starts on Manual, and says what the choice means.

The new-property form pre-selected "Automatically after a set number of hours"
and its lede explained the operating rules instead of the setting. A first-time
host was therefore one "Save" away from records leaving for the police before
they had ever seen a single send.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "new-property-default-host"

LEDE_KEY = "apartment.form.automation.new_lede"
LEDE_EN = "Choose when UbyHost may send finished guest records to the police. You can change this any time."
LEDE_CS = "Zvolte, kdy smí UbyHost hotové záznamy hostů odeslat policii. Změnit to můžete kdykoli."
OLD_LEDE_EN = (
    "The operating rules let you pick how much the app does on its own, and require "
    "that the choice is yours. Whatever you choose, a rejected record is never "
    "silently retried."
)
OLD_LEDE_CS = (
    "Provozní pravidla určují, kolik aplikace udělá sama, a vyžadují váš výsledný "
    "souhlas. Odmítnutý záznam se nikdy tiše neopakuje."
)

SELECT_RE = re.compile(
    r'<select[^>]*id="automation_mode".*?</select>', re.DOTALL
)
OPTION_RE = re.compile(r"<option\s+value=\"([^\"]+)\"([^>]*)>", re.DOTALL)


def _selected_mode(html: str) -> str:
    """The value the browser will submit when the host touches nothing."""
    block = SELECT_RE.search(html)
    assert block, "the automation timing select is not on the page"
    selected = [
        value
        for value, attrs in OPTION_RE.findall(block.group(0))
        if "selected" in attrs
    ]
    assert len(selected) == 1, f"expected exactly one selected option, got {selected}"
    return selected[0]


def _cleanup():
    """Delete this module's properties but keep the account other rows point at."""
    db.execute(
        "DELETE FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        (USERNAME,),
    )
    db.execute(
        "DELETE FROM legal_entity WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        (USERNAME,),
    )


def _payload(**overrides):
    data = {
        "internal_name": "Default Flat",
        "addr_city": "Praha",
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "120 00",
        "uby_idub": "123456789012",
        "uby_mark": "abc",
        "uby_name": "Penzion Default",
        "uby_contact": "host@default.test",
        "uby_ws_user": "UBY-WSdefault",
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "active": "on",
    }
    # 0088: a property always has an operator; use this host's only one.
    entity = db.query_one(
        "SELECT id FROM legal_entity WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?) ORDER BY id LIMIT 1",
        (USERNAME,),
    )
    if entity:
        data["legal_entity_id"] = str(entity["id"])
    data.update(overrides)
    return data


def _mode_of(internal_name: str):
    row = db.query_one(
        "SELECT automation_mode FROM apartment WHERE internal_name = ? "
        "AND owner_user_id = (SELECT id FROM user_account WHERE username = ?)",
        (internal_name, USERNAME),
    )
    assert row is not None, f"property {internal_name!r} was not created"
    return row["automation_mode"]


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    existing = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )
    if not existing:
        auth.create_account(f"{USERNAME}@example.test", "Default Host", username=USERNAME)
    db.insert(
        "legal_entity",
        {
            "name": "Default Operator",
            "owner_user_id": db.query_one(
                "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
            )["id"],
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _create_and_open(host, name, **overrides):
    created = host.post("/apartments", data=_payload(internal_name=name, **overrides), follow_redirects=False)
    assert created.status_code == 303, created.text
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ? AND owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        (name, USERNAME),
    )["id"]
    return host.get(f"/apartments/{apartment_id}")


def test_a_new_property_starts_on_manual(host):
    """0092: the short create page carries no reporting choice at all, so a
    property can only start on Manual; its page then shows Manual selected."""
    page = host.get("/apartments/new")
    assert page.status_code == 200, page.text
    assert 'name="automation_mode"' not in page.text
    assert 'name="submit_after_hours"' not in page.text
    assert '<select id="default_purpose"' not in page.text
    detail = _create_and_open(host, "Starts Manual Flat")
    assert _selected_mode(detail.text) == "manual"


def test_the_timing_select_still_offers_every_mode(host):
    page = _create_and_open(host, "Every Mode Flat")
    values = [
        value
        for value, _ in OPTION_RE.findall(SELECT_RE.search(page.text).group(0))
    ]
    assert values == ["manual", "scheduled", "immediate"]


def test_the_new_property_form_leaves_the_choice_to_the_property_page(host):
    page = host.get("/apartments/new?lang=en")
    assert LEDE_EN not in page.text
    assert OLD_LEDE_EN not in page.text
    detail = _create_and_open(host, "Choice Later Flat")
    assert 'id="automation"' in detail.text
    assert host_i18n.STRINGS["en"]["automation.timing_help"] in detail.text


def test_the_czech_create_page_leaves_it_too(host):
    page = host.get("/apartments/new?lang=cs")
    assert LEDE_CS not in page.text
    assert OLD_LEDE_CS not in page.text
    assert 'name="automation_mode"' not in page.text


def test_the_lede_is_pinned_in_both_languages():
    assert host_i18n.STRINGS["en"][LEDE_KEY] == LEDE_EN
    assert host_i18n.STRINGS["cs"][LEDE_KEY] == LEDE_CS


def test_the_operating_rules_lede_is_gone():
    for lang in ("en", "cs"):
        assert host_i18n.STRINGS[lang][LEDE_KEY] not in (OLD_LEDE_EN, OLD_LEDE_CS)


def test_creating_a_property_without_a_mode_lands_on_manual(host):
    created = host.post(
        "/apartments",
        data=_payload(internal_name="No Mode Flat"),
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    assert _mode_of("No Mode Flat") == "manual"


def test_creating_a_property_honours_an_explicit_mode(host):
    created = host.post(
        "/apartments",
        data=_payload(internal_name="Delayed Flat", automation_mode="scheduled"),
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    assert _mode_of("Delayed Flat") == "scheduled"


def test_creating_a_property_with_a_nonsense_mode_lands_on_manual(host):
    created = host.post(
        "/apartments",
        data=_payload(internal_name="Bogus Flat", automation_mode="whenever"),
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    assert _mode_of("Bogus Flat") == "manual"


def test_the_edit_form_does_not_carry_a_mode_default(host):
    created = host.post(
        "/apartments",
        data=_payload(internal_name="Editable Flat", automation_mode="scheduled"),
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ? AND owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        ("Editable Flat", USERNAME),
    )["id"]

    page = host.get(f"/apartments/{apartment_id}")
    assert page.status_code == 200, page.text
    assert _selected_mode(page.text) == "scheduled"
    assert 'id="automation"' in page.text


def test_editing_a_property_can_change_its_mode(host):
    created = host.post(
        "/apartments",
        data=_payload(internal_name="Manual Flat"),
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ? AND owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        ("Manual Flat", USERNAME),
    )["id"]
    assert _mode_of("Manual Flat") == "manual"

    edited = host.post(
        f"/apartments/{apartment_id}",
        data=_payload(
            internal_name="Manual Flat", automation_mode="scheduled"
        ),
        follow_redirects=False,
    )
    assert edited.status_code == 303, edited.text
    assert _mode_of("Manual Flat") == "scheduled"
