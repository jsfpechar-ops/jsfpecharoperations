"""The stay hub reads in one order: status, the next action, then the records.

The guest's own saved forms are the least urgent thing on the page, so they fold
to a name and a state and sit below the one thing the guest still has to do.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim
from tests.test_guest_navigation import (
    _cleanup,
    _form,
    _make_apartment_with_stays,
    _passport_files,
)


def _hub(lang: str = "en"):
    """A stay where one of three people is saved, and the hub page for it."""
    token, stay, _other = _make_apartment_with_stays()
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, lang)
    complete_guest_claim(browser, token, stay, party_size=3)
    saved = browser.post(
        f"/l/{token}/{stay}/save",
        data=_form(party_size="3"),
        files=_passport_files(),
        follow_redirects=False,
    )
    assert saved.status_code == 303
    page = browser.get(f"/l/{token}/{stay}?lang={lang}")
    assert page.status_code == 200
    return page.text


def test_the_next_action_sits_above_the_records():
    try:
        page = _hub()
    finally:
        _cleanup()
    # The group card and its primary action sit above the folded records.
    assert "Add a person" in page
    assert page.index("Add a person") < page.index('class="g-card g-summary"')
    assert page.index("Add a person") < page.index("Your submission")


def test_the_status_line_says_how_many_are_still_to_register():
    try:
        page = _hub()
    finally:
        _cleanup()
    assert "Registered: 1 of 3" in page
    assert "Still to register: 2" in page
    assert "1 of 3 people completed" not in page
    assert "Still missing details for" not in page


def test_the_status_line_reads_in_czech_too():
    try:
        page = _hub("cs")
    finally:
        _cleanup()
    assert "Zaregistrováno: 1 z 3" in page
    assert "Zbývá zaregistrovat: 2" in page
    assert "vyplněno 1 z 3 osob" not in page
    assert "Chybí ještě údaje" not in page


def test_still_to_register_shows_when_every_saved_person_is_on_this_device():
    """The one-phone family is the common case, and it saw no "1 more to go".

    The sentence used to live only in the other-people card, which renders only
    when some saved person is *not* on this device — so a guest filling in the
    whole group alone never saw it.
    """
    try:
        page = _hub()
    finally:
        _cleanup()
    assert "g-still-missing" in page
    assert "Still to register: 2" in page
    assert 'class="g-person"' not in page


def test_the_records_fold_to_a_name_and_a_state():
    try:
        page = _hub()
    finally:
        _cleanup()
    assert '<details class="g-card g-summary">' in page
    assert (
        '<summary class="g-summary-fold">JOHN PAUL SMITH &middot; saved ✓</summary>'
        in page
    )
    assert 'class="g-summary-name"' not in page


def test_the_records_fold_to_a_czech_name_and_state():
    try:
        page = _hub("cs")
    finally:
        _cleanup()
    assert (
        '<summary class="g-summary-fold">JOHN PAUL SMITH &middot; uloženo ✓</summary>'
        in page
    )
