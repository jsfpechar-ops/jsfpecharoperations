"""UX-59 (A-23): one Czech noun for the guest's contact.

The guest used to read "Váš hostitel" in the footer and "Zpráva od vašeho
ubytovatele" three lines later. Joe's decision: "hostitel" everywhere a guest
is being talked to, in the UI and in guest mail; "ubytovatel" survives only
inside the legal notice and the privacy notice, where it is the statutory term.

This file is the guard. Without it the two words drift back together the next
time someone writes a line of guest copy.
"""
from __future__ import annotations

import re

from app import i18n, validation, validation_i18n

LEGAL_PREFIXES = ("legal_", "privacy")
WORD = "ubytovatel"


def _guest_keys_with(word):
    """Guest-facing keys whose Czech says ``word``, minus the legal prose."""
    return sorted(
        key
        for key, value in i18n.STRINGS["cs"].items()
        if re.search(word, value, re.I) and not key.startswith(LEGAL_PREFIXES)
    )


def test_no_guest_ui_or_mail_copy_calls_the_host_ubytovatel():
    assert _guest_keys_with(WORD) == []


def test_the_legal_notice_and_privacy_notice_keep_the_statutory_word():
    """The legal text is not guest copy - "ubytovatel" is the term of art."""
    legal = sorted(
        key
        for key, value in i18n.STRINGS["cs"].items()
        if re.search(WORD, value, re.I)
    )
    assert legal, "the statutory term disappeared from the legal text too"
    for key in legal:
        assert key.startswith(LEGAL_PREFIXES), key
    assert "legal_intro" in legal
    assert "privacy" in legal


def test_the_screens_that_named_the_other_word_now_name_the_host():
    cs = i18n.STRINGS["cs"]
    assert cs["message_from_host"] == "Zpráva od vašeho hostitele"
    assert "hostitel" in cs["host_details"]
    assert "hostitel" in cs["host_details_help"]
    assert cs["form_locked_short"] == "Uloženo a uzamčeno. Pro změnu kontaktujte hostitele."
    assert "hostitel" in cs["pin_help"].lower()
    assert "hostitel" in cs["passport_photo_help"]
    assert "hostitel" in cs["why_point_book"]


def test_the_guest_mail_footer_agrees_with_the_ui():
    """Surface E owns these keys; the noun has to match the pages they link to."""
    cs = i18n.STRINGS["cs"]
    assert cs["mail_guest_footer_host_label"] == "Váš hostitel"
    assert "hostitelem" in cs["mail_guest_footer_help"]
    assert "hostitel" in cs["mail_completion_note"]
    assert "hostitele" in cs["mail_claim_next_body"]


def test_a_guest_validation_message_that_mentions_the_host_uses_the_same_word():
    czech = validation_i18n.localize(validation.STAY_OUTSIDE_BOOKING_MESSAGE, "cs")
    assert "hostitele" in czech
    assert WORD not in czech


def test_the_english_side_already_says_your_host_everywhere_guest_facing():
    en = i18n.STRINGS["en"]
    for key, value in en.items():
        if key.startswith(LEGAL_PREFIXES):
            continue
        assert "property manager" not in value, key
        assert "accommodation provider" not in value, key
    assert en["message_from_host"] == "A message from your host"
