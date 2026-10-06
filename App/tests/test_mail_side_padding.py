"""UX-133 (audit E-24): give the phone a wider text column.

The card is 351px wide at 375px, and every block was inset 32px per side,
leaving a 287px column. There is no ``@media`` in mail, so the desktop inset
was also the phone inset. Narrowing the gutter to 24px buys 16px of text width
on every message without touching the layout.

The fix is a single number repeated in each block, so these tests assert the
rule (side insets are 24px) rather than pinning one cell.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from app import config, mail_notify

LANGS = ("en", "cs")
HOST = {"name": "Riverside", "email": "host@gutter.test", "phone": "+420999888777"}
STAY = {
    "id": 1,
    "summary": "Riverside Loft",
    "date_from": "2026-01-05",
    "date_to": "2026-01-08",
    "property_name": "Riverside Loft",
}

SIDE_PADDING = re.compile(r"padding:(\d+)px (\d+)px (\d+)px (\d+)px")
SHELL_ROW = "padding:28px 24px 0 24px;"


def _claim(lang: str):
    return mail_notify.build_claim_link(
        lang=lang,
        property_name="Riverside Loft",
        dates="2026-01-05 \u2013 2026-01-08",
        link=f"{config.PUBLIC_BASE_URL}/l/gutterlink/1/claim",
        host=HOST,
    )


def _completion(lang: str):
    return mail_notify.build_completion(
        lang=lang,
        property_name="Riverside Loft",
        dates="2026-01-05 \u2013 2026-01-08",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/gutterlink/1",
        host=HOST,
    )


def _reminder_guest(lang: str):
    return mail_notify.build_reminder_guest(
        lang=lang,
        property_name="Riverside Loft",
        stay_url=f"{config.PUBLIC_BASE_URL}/l/gutterlink/1",
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


def test_no_message_still_insets_by_thirty_two_pixels():
    """32px was only ever a side inset in this module; its return would be a
    regression on a 375px screen."""
    for kind, lang, content in _every_message():
        assert "32px" not in content["html"], (kind, lang)


def test_every_inset_block_uses_the_same_narrow_gutter():
    """Left and right must agree, and they must be 24px.

    A block that drifted back to 32px, or an asymmetric one, would make the
    column jump between sections of the same card.
    """
    seen = 0
    for kind, lang, content in _every_message():
        for top, right, bottom, left in SIDE_PADDING.findall(content["html"]):
            seen += 1
            assert right == "24" and left == "24", (kind, lang, top, bottom)
    assert seen, "no inset block was rendered at all"


def test_the_shell_itself_was_narrowed():
    """The header and footer rows sit outside the blocks; they were 32px too."""
    for kind, lang, content in _every_message():
        assert SHELL_ROW in content["html"], (kind, lang)


@pytest.mark.parametrize("lang", LANGS)
def test_the_text_part_is_untouched(lang):
    """Plain text carries no padding, so the fix must not have leaked into it."""
    content = _claim(lang)
    assert "padding" not in content["text"]


def test_the_wide_gutter_is_gone_from_the_module_source():
    """Belt and braces: the number cannot come back in one place."""
    source = pathlib.Path(mail_notify.__file__).read_text(encoding="utf-8")
    assert "32px" not in source
