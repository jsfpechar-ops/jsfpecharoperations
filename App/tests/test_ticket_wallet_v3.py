"""Ticket Wallet v3: the defects found by driving the guest flow on a phone.

These are the fast, markup-level halves of the checks. The browser halves -
the ones that prove the behaviour, not just the code - are in
test_guest_browser_e2e.py.
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
TICKET_JS = (APP / "static" / "ticket.js").read_text(encoding="utf-8")
CSS = (APP / "static" / "guest-ticket.css").read_text(encoding="utf-8")
BASE = (APP / "templates" / "guest" / "base.html").read_text(encoding="utf-8")
CLAIM = (APP / "templates" / "guest" / "claim.html").read_text(encoding="utf-8")
STAY = (APP / "templates" / "guest" / "stay.html").read_text(encoding="utf-8")
FORM = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")


# 1. The group size never opens empty --------------------------------------

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


# 2. The signature pad is never sized while hidden -------------------------

def test_the_pad_waits_until_it_is_visible_before_sizing_itself():
    resize = SIGNATURE_JS[SIGNATURE_JS.index("function resize()"):]
    resize = resize[: resize.index("function pos(")]
    assert "if (!rect.width || !rect.height) return;" in resize
    # Same size, nothing to do: a phone's address bar must not wipe a drawing.
    assert "canvas.width === width && canvas.height === height" in resize


def test_the_pad_is_sized_again_when_its_step_is_shown():
    assert 'ownForm.addEventListener("guest-wizard:shown"' in SIGNATURE_JS
    assert "new ResizeObserver" in SIGNATURE_JS


def test_an_empty_canvas_never_counts_as_a_signature():
    assert "if (dirty && canvas.width && canvas.height) {" in SIGNATURE_JS
    # "Signed" is only shown for a real image, never for the empty "data:,".
    assert 'hidden.value.indexOf("data:image/") === 0' in TICKET_JS


# 3. After one person, the next one is named --------------------------------

def _hub_after_first_of_three(lang="en"):
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
    return browser.get(saved.headers["location"]).text


def test_the_saved_ticket_carries_the_button_for_the_next_guest():
    try:
        page = _hub_after_first_of_three()
    finally:
        _cleanup()
    saved = page[page.index("g-saved tw-ticket"):page.index('class="g-card g-summary"')]
    assert "Register guest 2 of 3" in saved
    # Exactly one way forward: no second "your group" card with its own button.
    assert page.count("data-tw-next-guest") == 1
    assert "Add a person" not in page


def test_the_next_guest_button_is_czech_on_a_czech_page():
    try:
        page = _hub_after_first_of_three("cs")
    finally:
        _cleanup()
    assert "Registrovat hosta 2 z 3" in page


def test_every_form_step_says_whose_form_it_is():
    token, stay, _other = _make_apartment_with_stays()
    browser = TestClient(app)
    try:
        complete_guest_claim(browser, token, stay, party_size=3)
        page = browser.get(f"/l/{token}/{stay}/new?lang=en").text
    finally:
        _cleanup()
    assert page.count('data-tw-strip="Guest 1 of 3"') == page.count("data-guest-step data-tw-strip")
    assert page.count('data-tw-strip="Guest 1 of 3"') >= 5
    assert ".tw [data-guest-step][data-tw-strip]::before { content: attr(data-tw-strip); }" in CSS


# 4. Layout ------------------------------------------------------------------

def test_the_birth_date_boxes_have_no_second_row_of_labels():
    """The Day/Month/Year row pushed the boxes below the field beside them."""
    dob = TICKET_JS[TICKET_JS.index("function initDobCells()"):]
    dob = dob[: dob.index("function initCountryCombos()")]
    assert 'createElement("small")' not in dob
    assert 'box.setAttribute("aria-label", n[0]);' in dob


def test_fields_in_a_row_share_one_rhythm():
    assert ".tw .g-row > .g-field { margin-bottom: 0; }" in CSS
    assert ".tw .g-row { gap: 20px; margin-bottom: 20px; }" in CSS


def test_screen_reader_words_are_never_painted():
    """signature.js marks finished tracker steps with class="sr-only"."""
    assert 'sr.className = "sr-only";' in SIGNATURE_JS
    rule = CSS[CSS.index(".tw .sr-only {"):]
    assert "clip: rect(0 0 0 0);" in rule[: rule.index("}")]


def test_back_and_continue_share_one_line():
    assert ".tw [data-guest-step] > .g-wizard-nav { flex-wrap: nowrap; align-items: stretch; }" in CSS


def test_a_new_step_does_not_open_under_the_app_bar():
    assert "scroll-margin-top: 104px;" in CSS


# 5. Shipping ----------------------------------------------------------------

def test_the_changed_files_get_new_cache_keys():
    """A phone that cached the broken files must fetch the fixed ones."""
    assert "guest-ticket.css?v=20260930a" in BASE
    assert "signature.js?v=20260930a" in BASE
    assert "ticket.js?v=20261001a" in BASE


def test_the_czech_pass_says_arrival_and_departure():
    assert i18n.STRINGS["cs"]["check_in"] == "Příjezd"
    assert i18n.STRINGS["cs"]["check_out"] == "Odjezd"


def test_the_new_strings_exist_in_both_languages():
    for key in ("tw_guest_n_of", "tw_guest_n", "tw_next_guest"):
        assert key in i18n.STRINGS["en"] and key in i18n.STRINGS["cs"]


def test_the_app_bar_title_shrinks_instead_of_pushing_the_language_switch_down():
    assert ".tw .g-head .g-title { flex: 1 1 0; }" in CSS
    assert ".tw .g-head .g-lang { flex: 0 0 auto; }" in CSS
