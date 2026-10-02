"""An unknown guest headcount should read as unknown, not as "0 / ?".

The Overview and Stays lists printed "0 / ?" and left the host to guess what the
question mark meant. The focus card's Czech note counted "%(filled)s /
%(expected)s formulářů hostů", so one registered guest read "1 formulářů hostů".
The Overview now shows nothing until the count is declared; tables show a
quiet dash with the meaning for screen readers.
"""
from __future__ import annotations

from app import db, host_i18n
from tests.test_submission_retry_cap import (  # noqa: F401
    _cleanup,
    _seed,
    host as host,
)

UNKNOWN_EN = "Number of guests not known yet"
UNKNOWN_CS = "Počet hostů zatím neznáme"
LIST_DASH = '<span class="muted" aria-hidden="true">–</span><span class="sr-only">{text}</span>'


def _seed_unknown_headcount(token: str):
    """A stay whose headcount nobody knows, with nobody registered yet."""
    apartment, reservation, _guest = _seed(token)
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (reservation["id"],))
    db.update("reservation", reservation["id"], {"expected_guests_override": None})
    return apartment, reservation


def test_the_overview_says_nothing_about_an_unknown_headcount(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-dash")
    try:
        english = host.get("/?lang=en").text
        czech = host.get("/?lang=cs").text

        assert "0 / ?" not in english
        assert UNKNOWN_EN not in english
        assert UNKNOWN_CS not in czech
    finally:
        _cleanup(apartment["id"])


def test_the_reservations_list_shows_a_quiet_dash(host):
    apartment, _reservation = _seed_unknown_headcount("ux147-list")
    try:
        page = host.get("/reservations?lang=en").text

        assert LIST_DASH.format(text=UNKNOWN_EN) in page
        assert "0 / ?" not in page
    finally:
        _cleanup(apartment["id"])


def test_a_known_headcount_shows_the_count(host):
    apartment, reservation = _seed_unknown_headcount("ux147-known")
    db.update("reservation", reservation["id"], {"expected_guests_override": 3})
    try:
        page = host.get("/?lang=en").text

        assert "0 / 3" in page
    finally:
        _cleanup(apartment["id"])


def test_the_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["common.guests_unknown"] == UNKNOWN_EN
    assert host_i18n.STRINGS["cs"]["common.guests_unknown"] == UNKNOWN_CS
