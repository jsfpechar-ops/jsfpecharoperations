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
    "claim_help": (
        "We'll e-mail you a private link so only your group can open the forms.",
        "Pošleme vám soukromý odkaz, aby formuláře otevřela jen vaše skupina.",
    ),
    "claim_email_help": (
        "We send the link here, one reminder the day before arrival if forms "
        "are missing, and a receipt (your host gets a copy). Elsewhere it is "
        "shown masked. No marketing.",
        "Pošleme sem odkaz, jedno připomenutí den před příjezdem, pokud "
        "formuláře chybí, a potvrzení (kopii dostane i ubytovatel). Jinde se "
        "adresa zobrazuje zakrytě. Žádný marketing.",
    ),
    "claim_cookie_help": (
        "Only necessary cookies: PIN access (7 days), your language and this "
        "stay (60 days).",
        "Jen nezbytné cookies: přístup přes PIN (7 dní), jazyk a tento pobyt "
        "(60 dní).",
    ),
}

# The guest pages that render the shared "why we collect this" fold.
GUEST_PAGES_WITH_WHY = (
    "claim.html",
    "form.html",
    "pick.html",
    "unavailable.html",
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
    # "two hint paragraphs of ~100 words" was the finding; the fix is 58/48.
    for lang, budget in (("en", 65), ("cs", 55)):
        total = sum(
            len(i18n.STRINGS[lang][key].split())
            for key in ("claim_help", "claim_email_help", "claim_cookie_help")
        )
        assert total <= budget, (lang, total)


def test_the_claim_hints_keep_every_point_design_md_requires():
    # cheap guard against a future "condensing" pass that drops a promise
    english = " ".join(
        i18n.STRINGS["en"][key].lower()
        for key in ("claim_help", "claim_email_help", "claim_cookie_help")
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
    assert "{{ t('claim_email_help') }}" in template
    assert "{{ t('claim_cookie_help') }}" in template
    # no leftover private copy of the same two paragraphs
    assert "assigned_email_help" not in template
    assert "assigned_cookie_help" not in template
