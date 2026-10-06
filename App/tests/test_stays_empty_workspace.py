"""An empty workspace should not open the Stays page with a full toolbar.

The page used to render the range chips, the List/Timeline switch, the whole
filter panel with CSV export and a disabled "Send all ready stays" above a
one-line empty state, so the one next step sat at the very bottom of the page.
With no property there is nothing to filter or send, so now only the empty state
shows. The demo button follows the Overview and appears only where demo data can
actually load, and an empty list with no calendar asks for a calendar instead of
pointing at the properties page.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "stays-empty-host"

EMPTY_PANEL_RE = re.compile(r'<div class="panel empty">\n(.*?)\n\s*</div>', re.DOTALL)
FILTER_FORM_RE = re.compile(
    r'<form method="get" action="/reservations" class="filters panel".*?</form>',
    re.DOTALL,
)
PRIMARY_LINK_RE = re.compile(r'<a class="btn primary" href="([^"]+)">([^<]+)</a>')
STRINGS = host_i18n.STRINGS
CONNECT_CALENDAR = {lang: STRINGS[lang]["dashboard.empty.connect_calendar"] for lang in ("en", "cs")}
DEMO_BUTTON = STRINGS["en"]["demo.load"]
TIMELINE_LABEL = STRINGS["en"]["stays.view.timeline"]
SEND_ALL_LABEL = STRINGS["en"]["send.all_ready"]


def _owner_filter() -> str:
    return "(SELECT id FROM user_account WHERE username = ?)"


def _cleanup():
    """Delete this module's rows but keep the account other tables point at."""
    owner = _owner_filter()
    db.execute(
        f"DELETE FROM ical_feed WHERE apartment_id IN "
        f"(SELECT id FROM apartment WHERE owner_user_id = {owner})",
        (USERNAME,),
    )
    db.execute(f"DELETE FROM apartment WHERE owner_user_id = {owner}", (USERNAME,))
    db.execute(f"DELETE FROM legal_entity WHERE owner_user_id = {owner}", (USERNAME,))


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _property_id() -> int:
    return db.query_one(
        "SELECT a.id FROM apartment a JOIN user_account u ON u.id = a.owner_user_id "
        "WHERE u.username = ? ORDER BY a.id LIMIT 1",
        (USERNAME,),
    )["id"]


def _add_property() -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Stays Empty s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@stays-empty.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Quiet Flat",
            "permalink_token": "staysempty1",
            "automation_mode": "manual",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def _add_feed(apartment_id: int) -> None:
    db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://example.test/feed.ics",
            "label": "Airbnb",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def _empty_panel(page_text: str) -> str:
    match = EMPTY_PANEL_RE.search(page_text)
    assert match, "no empty-state panel on the page"
    return match.group(1)


def _primary_links(block: str) -> list[tuple[str, str]]:
    return [(url, label.strip()) for url, label in PRIMARY_LINK_RE.findall(block)]


@pytest.fixture
def host():
    """An owner with nothing at all: no operator, no property, no stay."""
    db.init_db()
    _cleanup()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not existing:
        auth.create_account(f"{USERNAME}@example.test", "Stays Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def host_with_property(host):
    _add_property()
    return host


# --- no property: the empty state is the whole page -----------------------


def test_the_page_shows_no_toolbar_without_a_property(host):
    page = host.get("/reservations")

    assert page.status_code == 200
    assert 'class="stays-toolbar"' not in page.text
    assert 'class="filters panel"' not in page.text
    assert "data-save-view" not in page.text
    assert TIMELINE_LABEL not in page.text


def test_the_page_shows_no_dead_send_all_without_a_property(host):
    page = host.get("/reservations")

    assert SEND_ALL_LABEL not in page.text
    assert 'action="/reservations/submit-ready"' not in page.text


def test_the_empty_state_names_exactly_one_next_step(host):
    page = host.get("/reservations")
    panel = _empty_panel(page.text)

    assert _primary_links(panel) == [
        ("/apartments/new", STRINGS["en"]["stays.empty.add_first"])
    ]


def test_the_empty_state_still_explains_itself(host):
    page = host.get("/reservations")

    assert STRINGS["en"]["stays.empty.no_apartments"] in page.text


# --- the demo button only where demo data can load ------------------------


def test_the_demo_button_is_offered_on_the_mock_environment(host):
    page = host.get("/reservations")

    assert DEMO_BUTTON in page.text
    assert 'action="/demo"' in page.text


def test_the_demo_button_is_hidden_where_demo_data_cannot_load(host, monkeypatch):
    monkeypatch.setattr(config, "UBYPORT_ENV", "prod")

    page = host.get("/reservations")

    assert page.status_code == 200
    assert DEMO_BUTTON not in page.text
    assert 'action="/demo"' not in page.text
    assert STRINGS["en"]["demo.load_detail"] not in page.text


def test_hiding_the_demo_button_leaves_the_one_next_step(host, monkeypatch):
    monkeypatch.setattr(config, "UBYPORT_ENV", "prod")

    panel = _empty_panel(host.get("/reservations").text)

    assert len(_primary_links(panel)) == 1


# --- a property but no calendar: ask for the calendar --------------------


def test_a_host_with_no_calendar_is_sent_to_connect_one(host_with_property):
    page = host_with_property.get("/reservations")
    panel = _empty_panel(page.text)

    assert page.status_code == 200
    assert _primary_links(panel) == [
        (f"/apartments/{_property_id()}#calendars", CONNECT_CALENDAR["en"])
    ]
    assert STRINGS["en"]["stays.empty.go_apartments"] not in page.text


def test_with_a_calendar_the_empty_state_keeps_its_quiet_link(host_with_property):
    _add_feed(_property_id())

    page = host_with_property.get("/reservations")
    panel = _empty_panel(page.text)

    assert f'href="/apartments/{_property_id()}#calendars"' not in page.text
    assert _primary_links(panel) == []
    assert (
        f'<a class="btn" href="/apartments">'
        f'{STRINGS["en"]["stays.empty.go_apartments"]}</a>' in panel
    )


def test_the_toolbar_and_filters_return_with_a_property(host_with_property):
    page = host_with_property.get("/reservations")

    assert 'class="stays-toolbar"' in page.text
    assert 'class="filters panel"' in page.text
    assert 'action="/reservations/submit-ready"' in page.text


# --- the filter's Apply is a neutral button, not the page primary (UX-145) --


def test_the_filter_apply_is_neutral_not_coral(host_with_property):
    page = host_with_property.get("/reservations")
    match = FILTER_FORM_RE.search(page.text)

    assert match, "no filter form on the page"
    assert 'class="btn primary filter-apply"' not in match.group(0)
    assert 'class="btn filter-apply"' in match.group(0)


def test_the_filter_apply_is_neutral_in_czech(host_with_property):
    page = host_with_property.get("/reservations?lang=cs")
    match = FILTER_FORM_RE.search(page.text)

    assert match, "no filter form on the Czech page"
    assert 'class="btn primary filter-apply"' not in match.group(0)
    assert f'>{STRINGS["cs"]["common.apply"]}</button>' in match.group(0)


def test_the_empty_state_asks_for_a_calendar_in_czech(host_with_property):
    page = host_with_property.get("/reservations?lang=cs")
    panel = _empty_panel(page.text)

    assert _primary_links(panel) == [
        (f"/apartments/{_property_id()}#calendars", CONNECT_CALENDAR["cs"])
    ]
    assert CONNECT_CALENDAR["en"] not in page.text


def test_the_czech_page_without_a_property_shows_no_toolbar(host):
    page = host.get("/reservations?lang=cs")

    assert page.status_code == 200
    assert 'class="stays-toolbar"' not in page.text
    assert STRINGS["cs"]["stays.empty.no_apartments"] in page.text
