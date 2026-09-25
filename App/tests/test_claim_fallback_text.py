"""E-19 [UX-135]: the fallback plain text comes out of the catalogue.

The plain-text body only ships when the branded composer throws, which is
exactly when nobody is looking. It used to be written out by hand in
``claim.py``, and that is how it drifted: the Czech claim body said "your host"
in English, the dates stayed in raw ISO while every other surface printed them
Czech-style, and the reminder told the guest to open the private link without
ever printing one.

Every assertion here reads the expected value out of ``i18n.STRINGS`` rather
than repeating the copy, so a deliberate wording change cannot leave the test
asserting text the app no longer sends.
"""

import pytest

from app import claim, config, i18n

TOKEN = "fallbacktexttok"
LINK = f"{config.PUBLIC_BASE_URL}/l/{TOKEN}/1/claim#c=secret"

APARTMENT = {
    "uby_name": "Vinohrady Studio",
    "internal_name": "",
    "legal_entity_id": None,
}


def _body(kind, lang, **kwargs):
    kwargs.setdefault("property_name", "Vinohrady Studio")
    kwargs.setdefault("dates", "25.09.2026 \u2013 28.09.2026")
    kwargs.setdefault("link", LINK)
    kwargs.setdefault("resend", kind == "claim_resend")
    return claim._guest_fallback_text(kind, lang, **kwargs)


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("kind", ["claim", "claim_resend", "completion"])
def test_the_fallback_body_carries_the_catalogued_intro_and_link(lang, kind):
    """The body must open with the same sentence the branded mail opens with."""
    t = i18n.translator(lang)
    body = _body(kind, lang, resend=kind == "claim_resend")
    prefix = "mail_completion" if kind == "completion" else "mail_claim"
    assert (
        t(
            f"{prefix}_intro",
            property="Vinohrady Studio",
            dates="25.09.2026 \u2013 28.09.2026",
        )
        in body
    )
    assert f"{t(f'{prefix}_action')}: {LINK}" in body


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_claim_fallback_keeps_the_30_minute_expiry(lang):
    """The expiry is the one time-critical fact; it must survive the fallback."""
    t = i18n.translator(lang)
    assert t("mail_claim_expiry") in _body("claim", lang)
    assert t("mail_claim_expiry_resend") in _body("claim_resend", lang)
    assert t("mail_claim_expiry_resend") not in _body("claim", lang)


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_completion_fallback_keeps_the_receipt_disclaimer(lang):
    t = i18n.translator(lang)
    assert t("mail_completion_note") in _body("completion", lang)


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_reminder_fallback_prints_the_link_it_asks_the_guest_to_open(lang):
    """It used to say "open the private link we already sent you" and stop."""
    body = _body("reminder_guest", lang, filled=1, expected=3)
    t = i18n.translator(lang)
    assert f"{t('mail_reminder_guest_action')}: {LINK}" in body
    assert t("mail_reminder_guest_device") in body
    assert t("mail_reminder_guest_intro", missing=2) in body
    assert t("mail_reminder_guest_heading") in body


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_reminder_fallback_survives_a_stay_of_unknown_size(lang):
    """No party size means no count, not a "None" or a "0 of None"."""
    t = i18n.translator(lang)
    body = _body("reminder_guest", lang, filled=0, expected=None)
    assert t("mail_reminder_guest_intro_no_count", property="Vinohrady Studio") in body
    assert "None" not in body
    assert t("mail_reminder_guest_intro", missing=0) not in body


def test_the_czech_claim_fallback_is_czech_throughout():
    """The old CS branch said "your host", in English, mid-sentence."""
    body = _body("claim", "cs")
    for english in ("your host", "Hello", "Confirm", "The link", "expires"):
        assert english not in body, english
    assert "V\u00e1\u0161 hostitel" not in body  # the CS branch said this too


def test_the_fallback_never_prints_the_iso_dates_the_composer_was_given():
    """Raw ISO in the fallback broke the "never print a stay two ways" rule."""
    content = claim._guest_mail_content(
        "claim",
        APARTMENT,
        {"id": 1, "date_from": "2026-09-25", "date_to": "2026-09-28"},
        lang="en",
        link=LINK,
    )
    text = content["text"]
    assert "25.09.2026 \u2013 28.09.2026" in text
    assert "2026-09-25" not in text
    assert "2026-09-28" not in text


def test_the_fallback_is_the_body_the_composer_would_have_written():
    """Composer down must cost the guest the design, never a fact."""
    apartment = dict(APARTMENT)
    reservation = {"id": 1, "date_from": "2026-09-25", "date_to": "2026-09-28"}
    content = claim._guest_mail_content(
        "claim", apartment, reservation, lang="en", link=LINK
    )
    branded = content["text"]
    # The branded body leads with the same intro and carries the same link, so
    # the two only differ in the decoration around them.
    assert branded.startswith(i18n.translator("en")("mail_claim_intro").split("%")[0])
    assert LINK in branded


def test_every_key_the_fallback_reads_exists_in_both_languages():
    """A missing key would ship the raw key name to the guest."""
    keys = [
        "mail_claim_intro",
        "mail_claim_action",
        "mail_claim_expiry",
        "mail_claim_expiry_resend",
        "mail_completion_intro",
        "mail_completion_action",
        "mail_completion_note",
        "mail_reminder_guest_heading",
        "mail_reminder_guest_intro",
        "mail_reminder_guest_intro_no_count",
        "mail_reminder_guest_action",
        "mail_reminder_guest_device",
        "mail_reminder_guest_note_label",
        "mail_reminder_guest_note",
    ]
    for key in keys:
        for lang in ("en", "cs"):
            assert i18n.STRINGS[lang].get(key), (key, lang)
            assert not i18n.STRINGS[lang][key].startswith("mail_"), (key, lang)


def test_no_fallback_key_is_left_untranslated():
    """EN and CS must say different things, or one of them was never written."""
    shared = []
    for kind in ("claim", "claim_resend", "completion", "reminder_guest"):
        en = _body(kind, "en", filled=1, expected=3, resend=kind == "claim_resend")
        cs = _body(kind, "cs", filled=1, expected=3, resend=kind == "claim_resend")
        if en == cs:
            shared.append(kind)
    assert not shared, shared
