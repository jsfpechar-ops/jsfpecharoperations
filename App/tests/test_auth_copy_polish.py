"""UX-127 (audit B-23): auth copy polish.

The 2FA field had a different name from its own title, "autentizátor" read
stiffly, and "Start over" didn't say what it starts over. (The password checks
went with the passwords in task 0003.)
"""
from __future__ import annotations

from app import host_i18n

LANGS = ("en", "cs")


def test_the_2fa_field_has_the_same_name_as_its_title():
    for lang in LANGS:
        assert host_i18n.translate(lang, "account.2fa.code_label") == host_i18n.translate(
            lang, "account.2fa.code_title"
        )


def test_start_over_says_what_it_starts_over():
    assert host_i18n.translate("en", "account.2fa.start_over") == "Use a different account"
    assert host_i18n.translate("cs", "account.2fa.start_over") == "Přihlásit se jiným účtem"


def test_no_stiff_authenticator_wording_survives():
    for lang in LANGS:
        for key in host_i18n.STRINGS[lang]:
            text = host_i18n.STRINGS[lang][key]
            if not isinstance(text, str):
                continue
            assert "autentizátor" not in text, (lang, key)
