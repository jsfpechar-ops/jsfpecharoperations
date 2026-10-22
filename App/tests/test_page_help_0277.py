"""0277: "How does this work?" on each main host page (idea P)."""
from __future__ import annotations

import re

import pytest

from app import demo, host_i18n
from tests.test_onboarding_wizard_survival import _full_apartment, host  # noqa: F401

KEYS = ("dashboard", "stays", "stay", "properties", "property", "reports", "invoices", "stay_fees", "housebook")


def _paths(host):
    flat = _full_apartment(host)
    stay = demo.create_demo_stay(flat["id"])
    return {
        "dashboard": "/", "stays": "/reservations", "stay": f"/reservations/{stay}",
        "properties": "/apartments", "property": f"/apartments/{flat['id']}",
        "reports": "/submissions", "invoices": "/invoices", "stay_fees": "/stay-fees", "housebook": "/housebook",
    }


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_every_main_page_has_one_closed_help(host, lang):
    for key, path in _paths(host).items():
        page = host["client"].get(f"{path}{'&' if '?' in path else '?'}lang={lang}")
        assert page.status_code == 200, (key, page.status_code)
        text = page.text
        assert text.count("data-how=") == 1, key
        assert f'data-how="{key}"' in text, key
        block = text.split(f'data-how="{key}"', 1)[1].split("</details>", 1)[0]
        assert " open" not in text.split(f'data-how="{key}"', 1)[0].rsplit("<details", 1)[1], key
        assert block.count("<li>") == 3, key
        for n in (1, 2, 3):
            assert host_i18n.translate(lang, f"how.{key}.{n}") != f"how.{key}.{n}", (lang, key, n)
        assert re.search(r'href="/guide#[a-z_-]+"', block), key


def test_strings_are_short():
    for lang in ("en", "cs", "vi"):
        for key in KEYS:
            for n in (1, 2, 3):
                assert len(host_i18n.translate(lang, f"how.{key}.{n}")) <= 120, (lang, key, n)
