"""Behavioural guest fixes that must hold under Arrival lane (TW archived).

Ticket Wallet markup lives under templates/guest/archive/ticket-wallet/; only
the fixes below apply to the active templates and signature.js.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app import i18n
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim
from tests.test_guest_navigation import (
    _cleanup,
    _form,
    _make_apartment_with_stays,
    _passport_files,
)

APP = Path(__file__).resolve().parent.parent / "app"
SIGNATURE_JS = (APP / "static" / "signature.js").read_text(encoding="utf-8")
TICKET_JS = (APP / "static" / "archive" / "ticket-wallet" / "ticket.js").read_text(
    encoding="utf-8"
)
CLAIM = (APP / "templates" / "guest" / "claim.html").read_text(encoding="utf-8")
STAY = (APP / "templates" / "guest" / "stay.html").read_text(encoding="utf-8")
FORM = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")


def test_the_claim_page_opens_the_group_size_at_one():
    """An empty box plus "+" gave 1, so a family registered one person."""
    token, stay, _other = _make_apartment_with_stays()
    try:
        page = TestClient(app).get(f"/l/{token}/{stay}?lang=en").text
    finally:
        _cleanup()
    field = page[page.index('id="party_size"'):]
    field = field[: field.index(">")]
    assert 'value="1"' in field


def test_every_party_size_box_has_a_starting_number():
    assert "claim.declared_guests or reservation.expected_guests_override or 1" in CLAIM
    assert 'autocomplete="off" value="1">' in STAY
    assert "values.get('party_size') or 1" in FORM


def test_the_pad_waits_until_it_is_visible_before_sizing_itself():
    resize = SIGNATURE_JS[SIGNATURE_JS.index("function resize()"):]
    resize = resize[: resize.index("function pos(")]
    assert "if (!rect.width || !rect.height) return;" in resize
    assert "canvas.width === width && canvas.height === height" in resize


def test_the_pad_is_sized_again_when_its_step_is_shown():
    assert 'ownForm.addEventListener("guest-wizard:shown"' in SIGNATURE_JS
    assert "new ResizeObserver" in SIGNATURE_JS


def test_an_empty_canvas_never_counts_as_a_signature():
    assert "if (dirty && canvas.width && canvas.height) {" in SIGNATURE_JS
    assert 'hidden.value.indexOf("data:image/") === 0' in TICKET_JS


def test_the_hub_still_offers_a_clear_add_person_action():
    token, stay, _other = _make_apartment_with_stays()
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, "en")
    try:
        complete_guest_claim(browser, token, stay, party_size=3, lang="en")
        saved = browser.post(
            f"/l/{token}/{stay}/save",
            data=_form(party_size="3"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert saved.status_code == 303
        page = browser.get(saved.headers["location"]).text
        assert "Add a person" in page
        assert page.index("Add a person") < page.index('class="g-card g-summary"')
    finally:
        _cleanup()


def test_the_birth_date_boxes_have_no_second_row_of_labels():
    dob = TICKET_JS[TICKET_JS.index("function initDobCells()"):]
    dob = dob[: dob.index("function initCountryCombos()")]
    assert 'createElement("small")' not in dob
    assert 'box.setAttribute("aria-label", n[0]);' in dob


def test_the_czech_pass_says_arrival_and_departure():
    assert i18n.STRINGS["cs"]["check_in"] == "Příjezd"
    assert i18n.STRINGS["cs"]["check_out"] == "Odjezd"
