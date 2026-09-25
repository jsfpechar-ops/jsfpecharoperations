"""Stay-detail and house-book labels read as the police form reads them.

The Czech side called citizenship "Národnost" (ethnicity), the lead guest
"vedoucí" (a manager), the birth date "Narozen" (gendered), and the guest-forms
note "2 podléhá povinnosti" (ungrammatical — 2 … podléhají). The e-mail hint was
a calque of "Stored for your reference".

The audit's copy is pinned here in both languages. The host guide still says
"vedoucí host" in one sentence; that is UX-149's scope, not this one.
"""
from __future__ import annotations

import pytest

from app import host_i18n

# (key, EN, CS) exactly as the audit writes them.
AUDITED_COPY = [
    (
        "stay.detail.metric.guests_note",
        "Reported %(sent)s of %(reportable)s foreign guests",
        "Nahlášeno %(sent)s z %(reportable)s cizinců",
    ),
    ("stay.detail.guests.lead", "main guest", "hlavní host"),
    ("stay.detail.guests.born", "Date of birth", "Datum narození"),
    ("stay.detail.guests.nationality", "Citizenship", "Státní občanství"),
    ("housebook.born", "Date of birth", "Datum narození"),
    ("housebook.nationality", "Citizenship", "Státní občanství"),
]

# Keys whose Czech wording changed but whose English wording the audit kept.
CS_ONLY = [
    (
        "stay.detail.settings.email_hint",
        "Jen pro vaši informaci. Automatické zprávy hostům se posílají na "
        "e-mail, kterým host odkaz převezme.",
    ),
    (
        "stay.detail.settings.expected_blank",
        "Kalendář neposkytuje počet. Nechte prázdné, aby ho uvedl hlavní host.",
    ),
]

# The one host key that legitimately still says "vedoucí": the guide sentence
# UX-149 owns. terms.s24_body uses the word in an unrelated legal sense.
ALLOWED_VEDOUCI = {"guide.guests.body", "terms.s24_body"}


@pytest.mark.parametrize("key,en,cs", AUDITED_COPY, ids=[c[0] for c in AUDITED_COPY])
def test_the_audited_copy_is_in_both_dictionaries(key, en, cs):
    assert host_i18n.STRINGS["en"][key] == en
    assert host_i18n.STRINGS["cs"][key] == cs


@pytest.mark.parametrize("key,cs", CS_ONLY, ids=[c[0] for c in CS_ONLY])
def test_the_czech_rewrite_is_in_both_dictionaries(key, cs):
    assert host_i18n.STRINGS["cs"][key] == cs
    # The English side is kept, but must not be missing.
    assert host_i18n.STRINGS["en"][key]


def test_the_audited_keys_exist_in_both_languages():
    for key, _en, _cs in AUDITED_COPY:
        assert key in host_i18n.STRINGS["en"]
        assert key in host_i18n.STRINGS["cs"]
    for key, _cs in CS_ONLY:
        assert key in host_i18n.STRINGS["en"]
        assert key in host_i18n.STRINGS["cs"]


def test_the_guest_forms_note_keeps_both_placeholders():
    for lang in ("en", "cs"):
        text = host_i18n.STRINGS[lang]["stay.detail.metric.guests_note"]
        assert "%(sent)s" in text
        assert "%(reportable)s" in text
        # The old wording counted "subject to the duty"; the note now counts
        # people, so it must not read as a bare duty statement any more.
        assert "podléhá povinnosti" not in text
        assert "subject to the duty" not in text


def test_citizenship_is_never_called_ethnicity():
    for lang in ("en", "cs"):
        for key, text in host_i18n.STRINGS[lang].items():
            if isinstance(text, str):
                assert "Národnost" not in text, key


def test_the_lead_guest_is_never_called_a_manager():
    for lang in ("en", "cs"):
        for key, text in host_i18n.STRINGS[lang].items():
            if not isinstance(text, str) or key in ALLOWED_VEDOUCI:
                continue
            assert "vedoucí" not in text, key


def test_the_birth_date_is_never_a_gendered_verb():
    for lang in ("en", "cs"):
        for key, text in host_i18n.STRINGS[lang].items():
            if isinstance(text, str):
                assert text != "Narozen", key
