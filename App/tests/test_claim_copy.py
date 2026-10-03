"""The claim screen's hints stay short, and the "why" fold stays out of the way.

A-12 [UX-49] asked for two things: condense `claim_title` / `claim_help` /
`claim_email_help` / `claim_cookie_help` without dropping any point DESIGN.md
requires at collection time, and move the shared "why we collect this" fold
below the back link so the Claim screen matches the other guest pages.

Both landed in the UX-13 commit, which had to rewrite the hints anyway once
the form folded away. This file exists so the ~100-word wall cannot come back:
the strings are pinned to the audit's exact wording, and the "why" fold is
pinned to its place under the back link.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import i18n

APP_DIR = Path(__file__).resolve().parents[1]

# The audit's copy, verbatim. Every point DESIGN.md requires at collection is
# in here: the private link, one reminder, the receipt plus host copy, masking,
# no marketing, and necessary cookies with their lifetimes.
AUDIT_COPY = {
    "claim_title": (
        "How many people, and your e-mail",
        "Počet osob a váš e-mail",
    ),
    # WP17 (review 3.E items 8 and 9): the private link and "no marketing"
    # now live only in `tw_email_short`, the line right above the fold, so
    # these two stopped repeating them.
    "claim_help": (
        "Only your group can open the forms.",
        "Formuláře otevře jen vaše skupina.",
    ),
    "tw_email_short": (
        "We send your private link here. No marketing.",
        "Pošleme sem váš soukromý odkaz. Žádný marketing.",
    ),
    "claim_email_help": (
        "Also one reminder the day before arrival if forms are missing, and a "
        "receipt (your host gets a copy). Shown masked elsewhere.",
        "Dále jedno připomenutí den před příjezdem, pokud formuláře chybí, a "
        "potvrzení (kopii dostane i hostitel). Jinde se adresa zobrazuje "
        "zakrytě.",
    ),
    "claim_cookie_help": (
        "Only necessary cookies: PIN access (7 days), your language and this "
        "stay (60 days).",
        "Jen nezbytné cookies: přístup přes PIN (7 dní), jazyk a tento pobyt "
        "(60 dní).",
    ),
}

# Every hint line the claim card renders, in the order the guest reads them.
CLAIM_HINT_KEYS = ("claim_help", "tw_email_short", "claim_email_help", "claim_cookie_help")

# The guest pages that render the shared "why we collect this" fold.
# UX-118 (audit A-31) dropped it from unavailable.html: a dead-end page has no
# form to explain, so the fold only added length.
GUEST_PAGES_WITH_WHY = (
    "claim.html",
    "form.html",
    "pick.html",
)


def _read(name: str) -> str:
    return (APP_DIR / "app" / "templates" / "guest" / name).read_text(
        encoding="utf-8"
    )


def test_the_claim_hints_are_the_audits_condensed_wording():
    for key, (english, czech) in AUDIT_COPY.items():
        assert i18n.STRINGS["en"][key] == english, key
        assert i18n.STRINGS["cs"][key] == czech, key


def test_the_claim_hints_stay_under_the_word_budget():
    # "two hint paragraphs of ~100 words" was the finding; UX-13 got it to
    # 58/48 for three keys. WP17 counts all four rendered lines and is lower.
    for lang, budget in (("en", 55), ("cs", 50)):
        total = sum(
            len(i18n.STRINGS[lang][key].split())
            for key in CLAIM_HINT_KEYS
        )
        assert total <= budget, (lang, total)


def test_the_claim_hints_keep_every_point_design_md_requires():
    # cheap guard against a future "condensing" pass that drops a promise
    english = " ".join(
        i18n.STRINGS["en"][key].lower()
        for key in CLAIM_HINT_KEYS
    )
    assert "private link" in english  # the link is private
    assert "reminder" in english  # exactly one reminder
    assert "receipt" in english and "copy" in english  # receipt + host copy
    assert "masked" in english  # shown masked elsewhere
    assert "no marketing" in english
    assert "cookies" in english and "7 days" in english and "60 days" in english


def test_the_why_fold_sits_below_the_back_link():
    for name in GUEST_PAGES_WITH_WHY:
        template = _read(name)
        why = template.index('{% include "guest/_why.html" %}')
        back = [m.start() for m in re.finditer(r'class="g-back"', template)]
        if not back:
            continue  # the first screen of the flow has nothing to go back to
        assert why > max(back), name


def test_the_claim_page_puts_the_fold_below_the_back_link_specifically():
    template = _read("claim.html")
    assert template.index('{% include "guest/_why.html" %}') > template.index(
        'class="g-back"'
    )


def test_the_assigned_screen_reuses_the_claim_hints_rather_than_its_own():
    template = _read("assigned.html")
    assert "{{ t('tw_email_short') }}" in template
    assert "{{ t('claim_email_help') }}" in template
    assert "{{ t('claim_cookie_help') }}" in template
    # WP17: the full text sits in the same fold as on the claim page, so the
    # screen shows two help lines (body + short e-mail line), not four.
    assert 'class="tw-more"' in template
    assert "assigned_resend_help" not in template
    assert "assigned_private_link" not in template
    # no leftover private copy of the same two paragraphs
    assert "assigned_email_help" not in template
    assert "assigned_cookie_help" not in template
