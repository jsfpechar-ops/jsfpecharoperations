"""A host who cannot remember their password needs a way out of the login page.

The only hint of help used to be a bare address as the fifth link of the 12.5px
footer, and the footnote talked about who may sign up rather than about how to
recover an account. Both now name the address in the sentence that explains it.
"""
from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from app import db, host_i18n, operator
from app.main import app

LANGS = ("en", "cs")


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


def _page(lang):
    return TestClient(app).get(f"/login?lang={lang}")


def _body(response):
    return html.unescape(response.text)


def test_the_password_field_offers_a_way_back_in():
    email = operator.details()["email"]
    for lang in LANGS:
        page = _page(lang)
        assert page.status_code == 200
        text = _body(page)
        assert '<details class="auth-help">' in page.text
        assert host_i18n.translate(lang, "login.forgot_summary") in text
        assert host_i18n.translate(lang, "login.forgot_body", email=email) in text
        assert email in text


def test_the_disclosure_sits_under_the_password_field_and_inside_the_form():
    for lang in LANGS:
        text = _body(_page(lang))
        form_start = text.index('<form method="post" action="/login"')
        password = text.index('id="password"')
        details = text.index('<details class="auth-help">')
        submit = text.index('class="auth-submit"')
        form_end = text.index("</form>", form_start)
        assert form_start < password < details < submit < form_end


def test_the_footnote_names_the_address_instead_of_an_administrator():
    email = operator.details()["email"]
    for lang in LANGS:
        text = _body(_page(lang))
        assert host_i18n.translate(lang, "login.footnote", email=email) in text
    assert "ask your administrator" not in _body(_page("en"))
    assert "účet vám vytvoří správce" not in _body(_page("cs"))


def test_the_new_login_help_keys_carry_the_same_placeholders_in_both_languages():
    for key in ("login.footnote", "login.forgot_body"):
        english = re.findall(r"%\((\w+)\)s", host_i18n.STRINGS["en"][key])
        czech = re.findall(r"%\((\w+)\)s", host_i18n.STRINGS["cs"][key])
        assert english == czech == ["email"], key
