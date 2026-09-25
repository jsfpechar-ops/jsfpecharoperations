"""UX-142: the signed-in chrome stopped burying help and doubling headings.

Four small things a host reads on every page: the support address sat inside the
11 px legal link row, the language button said "CZ" next to "EN", the command
palette's search box was the only unlabelled control in the app, and a brand-new
host's Overview printed two <h1>s (the page header's "Overview" and the welcome
card's title).
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "signed-in-chrome-host"


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


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _login(client: TestClient) -> None:
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


@pytest.fixture
def empty_host():
    """A brand-new host: an account and nothing else, so Overview is the zero state."""
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Chrome Host", must_change_password=False)
    client = TestClient(app)
    _login(client)
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture
def host_with_property():
    """A host with one property, so Overview is not the zero state."""
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Chrome Host", must_change_password=False)
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Chrome s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@chrome.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Chrome Flat",
            "addr_obec": "Praha",
            "addr_house_no": "12",
            "addr_zip": "12000",
            "permalink_token": "chromeflat1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    _login(client)
    try:
        yield client
    finally:
        _cleanup()


def _sidebar(page: str) -> str:
    match = re.search(r'<div class="sidebar-footer">.*?</div>\s*</aside>', page, re.S)
    assert match, "the sidebar footer is missing"
    return match.group(0)


# --- the support line -----------------------------------------------------------------


def test_the_support_sentence_exists_in_both_languages_with_the_same_placeholder():
    assert host_i18n.STRINGS["en"]["nav.support_help"] == "Need help with UbyHost? %(email)s"
    assert (
        host_i18n.STRINGS["cs"]["nav.support_help"]
        == "Potřebujete pomoc s UbyHostem? %(email)s"
    )


def test_the_old_bare_support_label_is_gone():
    """Its only consumer moved to the full sentence, so the key went with it."""
    assert "nav.support" not in host_i18n.STRINGS["en"]
    assert "nav.support" not in host_i18n.STRINGS["cs"]


def test_the_support_line_names_the_configured_operator_address(host_with_property):
    page = host_with_property.get("/?lang=en").text

    assert config.OPERATOR_EMAIL in page
    assert f'href="mailto:{config.OPERATOR_EMAIL}"' in page
    assert "Need help with UbyHost?" in page


def test_the_support_line_is_not_part_of_the_legal_link_row(host_with_property):
    footer = _sidebar(host_with_property.get("/?lang=en").text)
    links_row = re.search(
        r'<nav class="sidebar-footer-links".*?</nav>', footer, re.S
    ).group(0)

    assert "mailto:" not in links_row
    assert 'class="sidebar-footer-support"' in footer
    # Its own row, above the language switch and log out.
    assert footer.index("sidebar-footer-support") < footer.index("sidebar-footer-row")


def test_the_support_line_translates(host_with_property):
    page = host_with_property.get("/?lang=cs").text

    assert "Potřebujete pomoc s UbyHostem?" in page


# --- the language label ---------------------------------------------------------------


def test_the_czech_language_button_says_cs_in_both_catalogues():
    assert host_i18n.STRINGS["en"]["lang.cs"] == "CS"
    assert host_i18n.STRINGS["cs"]["lang.cs"] == "CS"
    assert host_i18n.STRINGS["en"]["lang.en"] == "EN"


def test_the_sidebar_switcher_offers_the_cs_label(host_with_property):
    page = host_with_property.get("/?lang=en").text

    assert 'name="lang" value="cs" class="">CS</button>' in page


# --- the command palette input --------------------------------------------------------


def _command_input(page: str) -> str:
    """The palette's search box itself, not the app-bar button that shares its name."""
    match = re.search(r"<input[^>]*data-command-input[^>]*>", page)
    assert match, "the command palette input is missing"
    return match.group(0)


def test_the_command_input_has_an_accessible_name(host_with_property):
    field = _command_input(host_with_property.get("/?lang=en").text)

    assert 'aria-label="Search or jump to…"' in field
    assert "placeholder=" in field


def test_the_command_input_label_translates(host_with_property):
    field = _command_input(host_with_property.get("/?lang=cs").text)

    assert 'aria-label="Hledat nebo přejít…"' in field


# --- the zero-state heading -----------------------------------------------------------


def test_the_zero_state_overview_has_one_h1(empty_host):
    page = empty_host.get("/?lang=en").text

    assert page.count("<h1") == 1
    assert host_i18n.STRINGS["en"]["onboarding.welcome_title"] in page
    assert f"<h1>{host_i18n.STRINGS['en']['dashboard.title']}</h1>" not in page


def test_the_zero_state_overview_still_renders_the_welcome_card(empty_host):
    page = empty_host.get("/?lang=en").text

    assert 'class="onboarding-welcome"' in page
    assert host_i18n.STRINGS["en"]["onboarding.kicker"] in page


def test_a_workspace_with_a_property_keeps_the_page_header(host_with_property):
    page = host_with_property.get("/?lang=en").text

    assert f"<h1>{host_i18n.STRINGS['en']['dashboard.title']}</h1>" in page


def test_the_skipped_onboarding_still_gets_the_page_header(empty_host):
    """With the guidance dismissed there is no welcome card, so Overview needs its own h1."""
    empty_host.post("/onboarding/dismiss", data={"return_to": "/"}, follow_redirects=False)

    page = empty_host.get("/?lang=en").text

    assert page.count("<h1") == 1
    assert f"<h1>{host_i18n.STRINGS['en']['dashboard.title']}</h1>" in page
