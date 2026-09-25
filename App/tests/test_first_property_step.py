"""Two screens say "Property", and the empty one names the step that comes first.

The Stays list called the same object an "Apartment" in its filter, its column
and its empty state, while the nav, the page header and the property form all
called it a "Property" -- one concept with two names on two adjacent screens.

The Properties list had the opposite problem: its empty state said "add the
operator first" and then offered a coral "Add your first property" next to a
coral "Add a property" in the header, so a new host saw three coral buttons
naming two different first steps.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "first-property-step-host"

ENTITY_NAME = "First Step s.r.o."

# (key, EN) — the stays keys the audit renamed. Pinned one by one so a partial
# revert cannot slip through.
STAYS_EN = [
    ("stays.add_panel.apartment", "Property"),
    ("stays.filter.apartment", "Property"),
    ("stays.table.apartment", "Property"),
    (
        "stays.empty.none",
        "No stays yet. Connect a calendar to a property, or use Add stay above.",
    ),
    ("stays.empty.go_apartments", "Go to properties"),
    (
        "stays.empty.no_apartments",
        "There are no properties yet, so there is nothing to show.",
    ),
    ("stays.empty.add_first", "Add your first property"),
]

# Czech already called it "Ubytování" everywhere, so it must not move.
STAYS_CS = [
    ("stays.add_panel.apartment", "Ubytování"),
    ("stays.filter.apartment", "Ubytování"),
    ("stays.table.apartment", "Ubytování"),
    (
        "stays.empty.none",
        "Zatím žádné pobyty. Připojte kalendář k ubytování nebo použijte Přidat pobyt.",
    ),
    ("stays.empty.go_apartments", "Přejít na ubytování"),
    (
        "stays.empty.no_apartments",
        "Zatím nemáte ubytování, takže není co zobrazit.",
    ),
    ("stays.empty.add_first", "Přidat první ubytování"),
]

# (key, EN, CS) — the empty state, in both languages.
EMPTY_COPY = [
    (
        "apartments.empty.lede",
        "First add who operates the property. Then you can add the property itself.",
        "Nejdřív přidejte, kdo ubytování provozuje. Potom přidáte samotné ubytování.",
    ),
    ("apartments.empty.lede_ready", "No properties yet.", "Zatím žádná ubytování."),
    ("apartments.empty.entity", "Add operator", "Přidat provozovatele"),
    (
        "apartments.empty.add",
        "Add your first property",
        "Přidat první ubytování",
    ),
]

EMPTY_PANEL_RE = re.compile(
    r'<div class="panel empty">\n(.*?)\n</div>', re.DOTALL
)
PRIMARY_LINK_RE = re.compile(
    r'<a class="btn primary" href="([^"]+)">([^<]+)</a>'
)


def _cleanup():
    """Delete this module's rows but keep the account other tables point at."""
    owner = "(SELECT id FROM user_account WHERE username = ?)"
    db.execute(
        "DELETE FROM reservation WHERE apartment_id IN "
        f"(SELECT id FROM apartment WHERE owner_user_id = {owner})",
        (USERNAME,),
    )
    db.execute(f"DELETE FROM apartment WHERE owner_user_id = {owner}", (USERNAME,))
    db.execute(f"DELETE FROM legal_entity WHERE owner_user_id = {owner}", (USERNAME,))


def _add_operator() -> int:
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    return db.insert(
        "legal_entity",
        {
            "name": ENTITY_NAME,
            "seat": "Testovací 1, Praha",
            "ico": "12345678",
            "contact_email": "operator@first-step.test",
            "owner_user_id": owner["id"],
            "created_at": db.utcnow(),
        },
    )


def _add_property(entity_id: int) -> int:
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    return db.insert(
        "apartment",
        {
            "internal_name": "First Step Flat",
            "legal_entity_id": entity_id,
            "owner_user_id": owner["id"],
            "created_at": db.utcnow(),
        },
    )


def _add_stay(apartment_id: int) -> int:
    today = date.today()
    now = db.utcnow()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "first-step-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )


@pytest.fixture
def host():
    """A signed-in host with no operator and no property."""
    db.init_db()
    _cleanup()
    existing = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )
    if not existing:
        auth.create_account(
            USERNAME, PASSWORD, "First Step Host", must_change_password=False
        )
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def host_with_operator(host):
    _add_operator()
    return host


@pytest.fixture
def host_with_property(host):
    _add_property(_add_operator())
    return host


@pytest.fixture
def host_with_stay(host):
    _add_stay(_add_property(_add_operator()))
    return host


def _empty_panel(page: str) -> str:
    match = EMPTY_PANEL_RE.search(page)
    assert match, "the properties list rendered no empty state"
    return match.group(1)


def _primary_links(block: str):
    return PRIMARY_LINK_RE.findall(block)


# --- the copy --------------------------------------------------------------


@pytest.mark.parametrize("key,en", STAYS_EN)
def test_the_stays_screen_calls_it_a_property(key, en):
    assert host_i18n.STRINGS["en"][key] == en


@pytest.mark.parametrize("key,cs", STAYS_CS)
def test_the_stays_screen_still_calls_it_ubytovani_in_czech(key, cs):
    assert host_i18n.STRINGS["cs"][key] == cs


@pytest.mark.parametrize("key,en,cs", EMPTY_COPY)
def test_the_empty_state_copy_is_in_both_dictionaries(key, en, cs):
    assert host_i18n.STRINGS["en"][key] == en
    assert host_i18n.STRINGS["cs"][key] == cs


def test_no_stays_string_still_says_apartment_in_english():
    leftovers = {
        key: text
        for key, text in host_i18n.STRINGS["en"].items()
        if key.startswith("stays.") and "apartment" in text.lower()
    }
    assert leftovers == {}


# --- the stays list --------------------------------------------------------


def test_the_stays_list_renders_the_word_property(host_with_stay):
    page = host_with_stay.get("/reservations?lang=en")
    assert page.status_code == 200, page.text
    assert '<label for="apartment">Property</label>' in page.text
    assert "<th>Property</th>" in page.text
    assert "Apartment" not in page.text


def test_the_stays_list_renders_it_in_czech_too(host_with_property):
    page = host_with_property.get("/reservations?lang=cs")
    assert page.status_code == 200, page.text
    assert '<label for="apartment">Ubytování</label>' in page.text


def test_the_empty_stays_list_offers_the_first_property(host):
    page = host.get("/reservations?lang=en")
    assert page.status_code == 200, page.text
    assert "There are no properties yet, so there is nothing to show." in page.text
    assert "Add your first property" in page.text


# --- the properties list ---------------------------------------------------


def test_a_host_with_no_operator_is_sent_to_add_one_first(host):
    page = host.get("/apartments")
    assert page.status_code == 200, page.text
    panel = _empty_panel(page.text)
    assert (
        "First add who operates the property. Then you can add the property itself."
        in panel
    )
    assert _primary_links(panel) == [("/entities", "Add operator")]


def test_a_host_with_an_operator_is_offered_the_first_property(host_with_operator):
    page = host_with_operator.get("/apartments")
    assert page.status_code == 200, page.text
    panel = _empty_panel(page.text)
    assert "No properties yet." in panel
    assert "First add who operates the property" not in panel
    assert _primary_links(panel) == [("/apartments/new", "Add your first property")]


def test_the_empty_state_names_exactly_one_first_step(host_with_operator):
    panel = _empty_panel(host_with_operator.get("/apartments").text)
    assert len(_primary_links(panel)) == 1, panel


def test_the_czech_empty_state_says_the_same(host):
    page = host.get("/apartments?lang=cs")
    assert page.status_code == 200, page.text
    panel = _empty_panel(page.text)
    assert (
        "Nejdřív přidejte, kdo ubytování provozuje. Potom přidáte samotné ubytování."
        in panel
    )
    assert _primary_links(panel) == [("/entities", "Přidat provozovatele")]


def test_the_czech_empty_state_with_an_operator_says_the_same(host_with_operator):
    page = host_with_operator.get("/apartments?lang=cs")
    assert page.status_code == 200, page.text
    panel = _empty_panel(page.text)
    assert "Zatím žádná ubytování." in panel
    assert _primary_links(panel) == [("/apartments/new", "Přidat první ubytování")]


def test_the_header_does_not_compete_with_the_empty_state(host):
    page = host.get("/apartments")
    assert page.status_code == 200, page.text
    assert 'href="/apartments/new">Add a property' not in page.text


def test_the_header_add_button_returns_once_a_property_exists(host_with_property):
    page = host_with_property.get("/apartments")
    assert page.status_code == 200, page.text
    assert 'href="/apartments/new">Add a property' in page.text
