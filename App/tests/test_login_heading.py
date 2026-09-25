"""UX-124 (audit B-20): the login h1 states the job, the lede states the product.

The h1 was the marketing line "Your guest reporting workspace." at
clamp(2.1rem, 3.2vw, 2.9rem), wrapping to three lines on a phone and pushing
Continue toward the fold, while the real instruction sat in the lede. The two
swap, and the Czech h1 gains the case ending it was missing ("do UbyHost" ->
"do UbyHostu").
"""
from __future__ import annotations

import html
import re

from fastapi.testclient import TestClient

from app import db, host_i18n
from app.main import app

TITLE_EN = "Log in to UbyHost"
TITLE_CS = "Přihlášení do UbyHostu"
LEDE_EN = "Your guest reporting workspace."
LEDE_CS = "Váš pracovní prostor pro hlášení hostů."


def _heading(page: str) -> tuple[str, str]:
    title = re.search(r'<h1 class="auth-title">(.*?)</h1>', page, re.S)
    lede = re.search(r'<p class="auth-lede">(.*?)</p>', page, re.S)
    assert title and lede, "the login h1/lede disappeared"
    return html.unescape(title.group(1)).strip(), html.unescape(lede.group(1)).strip()


def _login(lang: str) -> str:
    db.init_db()
    return TestClient(app).get(f"/login?lang={lang}").text


def test_the_h1_is_the_instruction_and_the_lede_is_the_workspace():
    page = _login("en")
    assert _heading(page) == (TITLE_EN, LEDE_EN)


def test_the_czech_h1_uses_the_correct_case_ending():
    page = _login("cs")
    assert _heading(page) == (TITLE_CS, LEDE_CS)


def test_the_czech_copy_never_says_do_ubyhost():
    """The old lede dropped the -u; the string is gone, not just reordered."""
    for lang in ("en", "cs"):
        for key in ("login.title", "login.lede"):
            text = host_i18n.translate(lang, key)
            assert not re.search(r"\bdo UbyHost(?!u)\b", text), (lang, key, text)


def test_both_languages_carry_both_halves():
    for lang, expected in (("en", (TITLE_EN, LEDE_EN)), ("cs", (TITLE_CS, LEDE_CS))):
        assert (
            host_i18n.translate(lang, "login.title"),
            host_i18n.translate(lang, "login.lede"),
        ) == expected
