"""An unknown guest headcount should read as unknown, not as "0 / ?".

The Overview and Stays lists printed "0 / ?" and left the host to guess what the
question mark meant. The focus card's Czech note counted "%(filled)s /
%(expected)s formulářů hostů", so one registered guest read "1 formulářů hostů".
The audit replaces the question mark with a titled dash and rewrites the note
(C-43 / UX-147).
"""
from __future__ import annotations

from app import db, host_i18n
from tests.test_submission_retry_cap import (  # noqa: F401
    _cleanup,
    _seed,
    host as host,
)

DASH = '<span title="{title}">—</span>'
UNKNOWN_EN = "Number of guests not known yet"
UNKNOWN_CS = "Počet hostů zatím neznáme"
READY_EN = "All forms complete — UbyHost sends them automatically."
READY_CS = "Všechny formuláře jsou hotové — UbyHost je odešle automaticky."
FORMS_EN = "Guest forms: %(filled)s/%(expected)s"
FORMS_CS = "Formuláře hostů: %(filled)s/%(expected)s"


def _seed_unknown_headcount(token: str):
    """A stay whose headcount nobody knows, with nobody registered yet."""
    apartment, reservation, _guest = _seed(token)
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
    db.update("reservation", reservation["id"], {"expected_guests_override": None})
    return apartment, reservation


def test_the_queue_shows_a_titled_dash_for_an_unknown_headcount(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-dash")
    try:
        page = host.get("/?lang=en").text

        assert "0 / ?" not in page
        assert DASH.format(title=UNKNOWN_EN) in page
    finally:
        _cleanup(apartment["id"])


def test_the_dash_title_is_localized(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-dash-cs")
    try:
        page = host.get("/?lang=cs").text

        assert DASH.format(title=UNKNOWN_CS) in page
    finally:
        _cleanup(apartment["id"])


def test_the_focus_note_drops_the_question_mark(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-focus")
    try:
        english = host.get("/?lang=en").text
        czech = host.get("/?lang=cs").text

        assert "Guest forms: 0/?" not in english
        assert UNKNOWN_EN in english
        assert "Formuláře hostů: 0/?" not in czech
        assert UNKNOWN_CS in czech
    finally:
        _cleanup(apartment["id"])


def test_the_rewritten_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["common.guests_unknown"] == UNKNOWN_EN
    assert host_i18n.STRINGS["cs"]["common.guests_unknown"] == UNKNOWN_CS
    assert host_i18n.STRINGS["en"]["action.ready_immediate"] == READY_EN
    assert host_i18n.STRINGS["cs"]["action.ready_immediate"] == READY_CS
    assert host_i18n.STRINGS["en"]["dashboard.focus.guest_forms"] == FORMS_EN
    assert host_i18n.STRINGS["cs"]["dashboard.focus.guest_forms"] == FORMS_CS


def test_the_reservations_list_also_uses_the_titled_dash(host):
    """One stay, one row: the unknown count must read the same as the Overview."""
    apartment, _reservation = _seed_unknown_headcount("ux147-list")
    try:
        page = host.get("/reservations?lang=en").text

        assert DASH.format(title=UNKNOWN_EN) in page
        assert "0 / ?" not in page
    finally:
        _cleanup(apartment["id"])
