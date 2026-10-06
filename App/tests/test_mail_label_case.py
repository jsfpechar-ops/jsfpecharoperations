"""UX-132 (audit E-18): the mail labels read as sentences, not as ALL CAPS.

The brief flags uppercase, letter-spaced labels as a government-form tell --
the kind of chrome a printed form uses to shout a field name. Every label in
the mail already carried sentence-case copy; ``text-transform`` was doing the
shouting. Dropping it (and the tracking that went with it) is the whole fix,
so these tests assert the mechanism is gone from every message rather than
pinning one label.

The note label keeps its brand-ink colour: it sits on the tinted panel, where
that colour was chosen for contrast (E-9 [UX-75]). Everything else moves to the
body ink now that the label is no longer muted small print.
"""
from __future__ import annotations

import html
import pathlib

from app import config, i18n, mail_notify

LANGS = ("en", "cs")
HOST = {"name": "Riverside", "email": "host@label.test", "phone": "+420999888777"}
STAY = {
    "id": 1,
    "summary": "Riverside Loft",
    "date_from": "2026-01-05",
    "date_to": "2026-01-08",
    "property_name": "Riverside Loft",
}

LABEL_STYLE = f"font:600 14px/1.4 {mail_notify._FONT};color:{mail_notify.INK};"


def _claim(lang: str):
    return mail_notify.build_claim_link(
        lang=lang,
        property_name="Riverside Loft",
        dates="2026-01-05 \u2013 2026-01-08",
        link=f"{config.PUBLIC_BASE_URL}/l/labellink/1/claim",
        host=HOST,
    )


def _completion(lang: str):
    return mail_notify.build_completion(
        lang=lang,
        property_name="Riverside Loft",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/labellink/1",
        host=HOST,
    )


def _reminder_guest(lang: str):
    return mail_notify.build_reminder_guest(
        lang=lang,
        property_name="Riverside Loft",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/labellink/1",
        host=HOST,
        filled=1,
        expected=3,
    )


def _reminder_host(lang: str):
    return mail_notify.build_reminder_host(
        property_name="Riverside Loft",
        date="05.01.2026",
        assigned="g***@example.test",
        stay_url=f"{config.PUBLIC_BASE_URL}/reservations/1",
        lang=lang,
        claimed=True,
        filled=1,
        expected=3,
    )


def _submission_problem(lang: str):
    return mail_notify.build_submission_problem(
        property_name="Riverside Loft",
        state="error",
        reason="106: Invalid value in a guest field",
        transport=False,
        stays=[STAY],
        submission_id=7,
        lang=lang,
    )


def _every_message():
    """(kind, lang, content) for every message the app can send."""
    for lang in LANGS:
        for kind, builder in (
            ("claim", _claim),
            ("completion", _completion),
            ("reminder_guest", _reminder_guest),
            ("reminder_host", _reminder_host),
            ("submission_problem", _submission_problem),
        ):
            yield kind, lang, builder(lang)


def test_no_message_shouts_a_label():
    """``text-transform`` is the mechanism; there is no reason to ship one."""
    for kind, lang, content in _every_message():
        assert "text-transform" not in content["html"], (kind, lang)
        assert "letter-spacing" not in content["html"], (kind, lang)


# Kinds that render a section or fact label; the other two messages carry no
# label at all, so a missing style there would be a false alarm.
LABELLED_KINDS = ("claim", "reminder_host", "submission_problem")


def test_the_section_label_is_body_ink_at_fourteen_pixels():
    """A 13px muted ALL-CAPS line reads as small print, not as a heading."""
    seen = set()
    for kind, lang, content in _every_message():
        if kind not in LABELLED_KINDS:
            continue
        part = html.unescape(content["html"])
        assert LABEL_STYLE in part, (kind, lang)
        seen.add(kind)
    assert seen == set(LABELLED_KINDS)


def test_the_note_label_keeps_the_contrast_colour_from_the_tinted_panel():
    """E-9 [UX-75] chose brand ink for a label on ``BRAND_SOFT``; E-18 does not
    undo that, it only stops the shouting."""
    seen = 0
    for kind, lang, content in _every_message():
        part = html.unescape(content["html"])
        if mail_notify.BRAND_SOFT not in part:
            continue
        seen += 1
        assert (
            f"font:600 14px/1.4 {mail_notify._FONT};color:{mail_notify.BRAND_INK};"
            in part
        ), (kind, lang)
    assert seen, "no message renders the tinted note any more"


def test_the_label_copy_is_already_a_sentence():
    """The fix is the styling; the copy must not need a rewrite for it.

    A label that is written in capitals in the catalogue would still shout once
    ``text-transform`` is gone, so this guards the pair.
    """
    labels = [
        "mail_claim_next_label",
        "mail_reminder_guest_note_label",
    ]
    for lang in LANGS:
        for key in labels:
            text = i18n.STRINGS[lang][key]
            assert text != text.upper(), (lang, key)
            assert text[0].isupper(), (lang, key)


def test_the_shouting_is_gone_from_the_module_source():
    """A belt-and-braces check: the mechanism cannot come back in one place."""
    source = pathlib.Path(mail_notify.__file__).read_text(encoding="utf-8")
    assert "text-transform" not in source
    assert "letter-spacing" not in source
