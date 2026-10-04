"""WP29: no em dash used as punctuation in user-visible copy.

Every string in the translation catalogues (guest pages in all five
languages, the host app, the guide, the legal pages, the public pages and the
validation messages) and the visible text of the legal and mail templates
must use a full stop, comma, colon or parentheses instead. A lone dash as an
empty-cell placeholder in a template is fine, and so is a dash inside a
template comment.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import app

PUNCTUATION_DASHES = (" — ", "— ")
TEMPLATES = Path(app.__file__).resolve().parent / "templates"
LEGAL_AND_MAIL_TEMPLATES = (
    "terms.html",
    "privacy.html",
    "dpa.html",
    "legal.html",
    "subprocessors.html",
    "public_legal_base.html",
    "_legal_toc.html",
    "_cookie_table.html",
    "mail_unsubscribe.html",
)


def _catalogue_modules():
    names = sorted(
        info.name for info in pkgutil.iter_modules(app.__path__) if info.name.endswith("_i18n")
    )
    assert {"i18n", "host_i18n", "guide_i18n", "validation_i18n"} <= set(names + ["i18n"])
    return [importlib.import_module(f"app.{name}") for name in ["i18n", *names]]


def _strings(value, path):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def _offenders():
    found = []
    for module in _catalogue_modules():
        for name, value in vars(module).items():
            if name.startswith("__") or not isinstance(value, (dict, list, tuple)):
                continue
            for path, text in _strings(value, f"{module.__name__}.{name}"):
                if any(dash in text for dash in PUNCTUATION_DASHES):
                    found.append(f"{path}: {text[:80]}")
    return found


def test_no_catalogue_string_uses_an_em_dash_as_punctuation():
    found = _offenders()
    assert not found, "\n".join(found)


def test_the_guest_catalogue_is_checked_in_every_language():
    from app import i18n

    assert set(i18n.LANGUAGES) >= {"en", "cs", "de", "es", "fr"}
    for lang in i18n.LANGUAGES:
        for key, text in i18n.STRINGS[lang].items():
            assert not any(dash in text for dash in PUNCTUATION_DASHES), (lang, key)


def test_the_check_catches_an_em_dash():
    assert any(dash in "Saved \u2014 thank you" for dash in PUNCTUATION_DASHES)
    assert any(dash in "\u2014 none \u2014" for dash in PUNCTUATION_DASHES)
    assert not any(dash in "—" for dash in PUNCTUATION_DASHES)


def test_legal_and_mail_templates_have_no_em_dash_in_their_text():
    found = []
    for name in LEGAL_AND_MAIL_TEMPLATES:
        path = TEMPLATES / name
        if not path.exists():
            continue
        text = re.sub(r"\{#.*?#\}", "", path.read_text(encoding="utf-8"), flags=re.S)
        for number, line in enumerate(text.splitlines(), start=1):
            if any(dash in line for dash in PUNCTUATION_DASHES):
                found.append(f"{name}:{number}: {line.strip()[:80]}")
    assert not found, "\n".join(found)
