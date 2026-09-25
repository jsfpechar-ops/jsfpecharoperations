"""Every host-facing redirect message goes through ``_flash``.

A flash message travels through the query string, so it has to be translated
where it is raised rather than where it is rendered. Raising it as an English
literal is what left a Czech host reading English at the exact moment they were
stuck, so this test fails if a literal reappears.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import host_i18n

ROUTES = Path(__file__).resolve().parent.parent / "app" / "routes"

# admin_helpers.py is the plumbing itself: it *defines* back(msg="", err="")
# and builds the ?msg=/?err= query string out of whatever it is handed.
EXEMPT = {"admin_helpers.py"}

# A keyword argument after "(" or "," whose value starts with a string literal,
# with or without an f prefix and with or without wrapping parentheses.
LITERAL_ARGUMENT = re.compile(r'(?<=[(,])\s*(msg|err)\s*=\s*\(?\s*f?["\']', re.S)

# The key each call passes, so the copy can be checked to exist in both languages.
FLASH_KEY = re.compile(r'_flash\(\s*request\s*,\s*["\']([^"\']+)["\']', re.S)


def _route_modules():
    return sorted(p for p in ROUTES.glob("*.py") if p.name not in EXEMPT)


def test_no_route_raises_an_english_message_literal():
    offenders = []
    for path in _route_modules():
        text = path.read_text()
        for match in LITERAL_ARGUMENT.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line} {text[match.start():match.start() + 60]!r}")
    assert not offenders, (
        "route messages must be translated with _flash(request, key):\n"
        + "\n".join(offenders)
    )


def test_every_flashed_key_exists_in_both_languages():
    missing = []
    for path in _route_modules():
        for key in set(FLASH_KEY.findall(path.read_text())):
            for lang in ("en", "cs"):
                if key not in host_i18n.STRINGS[lang]:
                    missing.append(f"{path.name}: {key} ({lang})")
    assert not missing, "flashed keys must exist in EN and CS:\n" + "\n".join(missing)


def test_the_grep_would_catch_a_literal():
    """Guard the guard: the pattern has to match what it is meant to catch."""
    assert LITERAL_ARGUMENT.search('return _back("/x", err="No such stay.")')
    assert LITERAL_ARGUMENT.search('_back("/x", msg=f"Sent {n}.")')
    assert LITERAL_ARGUMENT.search('_back(\n        "/x",\n        err=(\n            "Nope."\n        ),\n    )')
    assert not LITERAL_ARGUMENT.search('_back("/x", err=_flash(request, "flash.error.no_such_stay"))')
    assert not LITERAL_ARGUMENT.search('_back("/x", err=exc.key)')
    assert not LITERAL_ARGUMENT.search('query.append(f"err={quote(err)}")')


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_the_new_error_keys_are_sentences_not_stubs(lang):
    keys = [k for k in host_i18n.STRINGS[lang] if k.startswith("flash.error.")]
    assert len(keys) > 40
    for key in keys:
        value = host_i18n.STRINGS[lang][key]
        assert value.strip() == value and value
        assert value.endswith((".", "!", "?", ":")) or "%(detail)s" in value, key
