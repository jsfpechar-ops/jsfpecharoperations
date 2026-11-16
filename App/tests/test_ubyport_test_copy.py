"""A2: the connection-test copy says the login was accepted and never claims that filing works."""

from __future__ import annotations

import pytest

from app import host_i18n, host_vi_i18n

KEYS = ("flash.apartments.letter_test_ok", "flash.apartments.connection_ok")


def _copy(lang: str, key: str) -> str:
    if lang == "vi":
        merged: dict = {}
        for table in vars(host_vi_i18n).values():
            if isinstance(table, dict):
                merged.update(table)
        return merged[key]
    return host_i18n.STRINGS[lang][key]


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
@pytest.mark.parametrize("key", KEYS)
def test_connection_test_copy_never_claims_filing_works(lang, key):
    text = _copy(lang, key)
    for claim in ("Connection works", "Spojení funguje", "Kết nối hoạt động"):
        assert claim not in text
    if lang == "en":
        assert "does not prove filing works" in text
    if lang == "cs":
        assert "neověřuje, že podání funguje" in text
