"""Brief 1090 (K-L04): the guest form for a guest under 15.

The pad is replaced by one note; an adult this phone saved confirms for the
child with a role tick. The server half is brief 1089; this file covers what
the form renders and that a child's form sends without JavaScript.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db, i18n
from app.main import app
from tests.conftest import complete_guest_claim
from tests.test_under15_signature_1089 import (  # noqa: F401  (stay is a fixture)
    TOKEN,
    _client,
    _insert,
    _post,
    _save,
    stay,
)

APP = Path(__file__).resolve().parents[1] / "app"
LANGS = ("en", "cs", "de", "es", "fr", "uk")


def _tag(html: str, element_id: str) -> str:
    """The opening tag of the element with this id, or '' when it is absent."""
    match = re.search(r'<[a-z]+[^>]*\bid="%s"[^>]*>' % re.escape(element_id), html)
    return match.group(0) if match else ""


def _hidden(html: str, element_id: str) -> bool:
    tag = _tag(html, element_id)
    assert tag, f"#{element_id} is not in the page"
    return bool(re.search(r"\shidden(\s|>|=)", tag))


def _child_birth(stay, years=10) -> str:
    return f"1.1.{stay['today'].year - years}"


def _new(browser, stay, lang="en") -> str:
    response = browser.get(f"/l/{TOKEN}/{stay['reservation_id']}/new?lang={lang}")
    assert response.status_code == 200, response.text[-400:]
    return response.text


def _rerender(browser, stay, first_name, birth, **over) -> str:
    """A 422 re-render: everything valid except the acknowledgement tick."""
    response = _post(browser, stay, first_name, birth, legal_ack="", **over)
    assert response.status_code == 422, response.status_code
    return response.text


# --- a. source pins -----------------------------------------------------------

def test_the_script_only_shows_and_hides():
    source = (APP / "static" / "signature.js").read_text(encoding="utf-8")
    start = source.index("function initUnder15()")
    body = source[start:source.index("function initChildToggle()")]
    for banned in (".value =", ".checked =", ".required", "innerHTML"):
        assert banned not in body, banned
    assert "if (!hidden.value && !signatureWaived()) {" in source
    assert "if (canvas && signature && !signature.value && !signatureWaived()) {" in source
    assert "    initChildToggle();\n    initUnder15();\n" in source


def test_the_template_has_one_block_each_and_the_pad_stays_inside():
    template = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")
    assert template.count('id="sig-block"') == 1
    assert template.count('id="u15-block"') == 1
    sig = template.index('id="sig-block"')
    u15 = template.index('id="u15-block"')
    assert sig < template.index('id="sig-canvas"') < u15
    assert sig < template.index('id="signature"') < u15


def test_the_radio_shares_the_tick_box_rule():
    css = (APP / "static" / "guest.css").read_text(encoding="utf-8")
    assert ".checkline input[type=checkbox],\n.checkline input[type=radio] {" in css


# --- b. render ----------------------------------------------------------------

def test_a_new_form_renders_both_blocks(stay):
    html = _new(_client(stay), stay)
    assert not _hidden(html, "sig-block")
    assert not _hidden(html, "u15-block")
    assert "sign-for-child" not in html


@pytest.mark.parametrize("years,child", [(10, True), (16, False), (40, False)])
def test_a_rerender_shows_only_the_right_block(stay, years, child):
    html = _rerender(_client(stay), stay, "Kid", _child_birth(stay, years))
    assert _hidden(html, "sig-block") is child
    assert _hidden(html, "u15-block") is (not child)


@pytest.mark.parametrize("lang", LANGS)
def test_the_note_renders_in_each_language(stay, lang):
    html = _new(_client(stay), stay, lang)
    note = i18n.translator(lang)("u15_note")
    assert note and note != "u15_note"
    assert note in html
    if lang != "en":
        assert note != i18n.translator("en")("u15_note")


# --- c. the lists hold only people this phone saved ------------------------------

def test_a_childs_form_offers_the_adult_this_phone_saved(stay):
    browser = _client(stay)
    adult = _save(browser, stay, "Grownup", "1.1.1990")
    html = _new(browser, stay)
    assert _tag(html, "sign-for-child")
    assert f'<input type="hidden" name="signed_by" value="{adult["id"]}">' in html
    assert 'name="child_sign_role" value="parent"' in html
    assert 'name="child_sign_role" value="responsible_adult"' in html
    assert "checked" not in _tag(html, "sign-for-child")
    assert not re.search(r'name="child_sign_role"[^>]*checked', html)

    other = TestClient(app)
    complete_guest_claim(other, TOKEN, stay["reservation_id"], party_size=12)
    theirs = _new(other, stay)
    assert not _tag(theirs, "sign-for-child")
    assert 'name="signed_by"' not in theirs
    assert "Grownup" not in theirs and "GROWNUP" not in theirs


def test_several_adults_become_radios(stay):
    browser = _client(stay)
    first = _save(browser, stay, "Grownup", "1.1.1990")
    second = _save(browser, stay, "Auntie", "1.1.1985")
    html = _new(browser, stay)
    for row in (first, second):
        assert f'<input type="radio" name="signed_by" value="{row["id"]}">' in html
    assert i18n.translator("en")("sign_for_who") in html
    assert '<input type="hidden" name="signed_by"' not in html


def test_an_archived_or_unsigned_adult_is_not_offered(stay):
    browser = _client(stay)
    adult = _save(browser, stay, "Grownup", "1.1.1990")
    db.execute("UPDATE guest SET archived_at = ? WHERE id = ?", (db.utcnow(), adult["id"]))
    assert not _tag(_new(browser, stay), "sign-for-child")
    db.execute(
        # The drawing lives in the encrypted column; clear both.
        "UPDATE guest SET archived_at = NULL, signature_png = '', signature_png_enc = NULL "
        "WHERE id = ?",
        (adult["id"],),
    )
    assert not _tag(_new(browser, stay), "sign-for-child")


def test_an_adults_form_names_the_pending_children(stay):
    browser = _client(stay)
    child = _save(browser, stay, "Kiddo", _child_birth(stay), signature="")
    html = _new(browser, stay)
    assert _tag(html, "sign-for-children")
    assert not _hidden(html, "sign-for-children")
    assert f'<input type="hidden" name="sign_for_ids" value="{child["id"]}">' in html
    sentence = re.search(r'id="sign-for-children-text">([^<]*)<', html).group(1)
    assert "kiddo under" in sentence.lower()
    assert "%(" not in sentence and "{names}" not in sentence

    # A 16-year-old may not sign for anyone: the block is rendered hidden.
    teen = _rerender(browser, stay, "Teen", _child_birth(stay, 16))
    assert _hidden(teen, "sign-for-children")

    adult = _save(
        browser, stay, "Grownup", "1.1.1990",
        sign_for_ids=str(child["id"]), sign_for_role="responsible_adult",
    )
    linked = db.query_one("SELECT * FROM guest WHERE id = ?", (child["id"],))
    assert linked["signed_for_guest_id"] == adult["id"]
    assert not _tag(_new(browser, stay), "sign-for-children")


def test_people_the_host_entered_appear_in_neither_list(stay):
    """No owned id, as in a host's own view of the form: neither block."""
    _insert(stay, "Hostadult", "01011990")
    _insert(stay, "Hostchild", f"0101{stay['today'].year - 10}", signature="")
    html = _new(_client(stay), stay)
    assert not _tag(html, "sign-for-child")
    assert not _tag(html, "sign-for-children")
    assert "hostadult" not in html.lower() and "hostchild" not in html.lower()


# --- c2. what a re-render echoes ------------------------------------------------------

def test_a_rerender_keeps_the_ticks_and_a_language_switch_does_not(stay):
    browser = _client(stay)
    first = _save(browser, stay, "Grownup", "1.1.1990")
    second = _save(browser, stay, "Auntie", "1.1.1985")
    html = _rerender(
        browser, stay, "Kid", _child_birth(stay), signature="",
        signed_by=str(second["id"]), child_sign_role="responsible_adult",
    )
    assert f'name="signed_by" value="{second["id"]}" checked' in html
    assert f'name="signed_by" value="{first["id"]}">' in html
    assert 'name="child_sign_role" value="responsible_adult" checked' in html
    assert 'name="child_sign_role" value="parent">' in html
    # The sentence carries the child's own name from step one.
    sentence = re.search(r'id="sign-for-child-text"[^>]*>([^<]*)<', html).group(1)
    assert "kid under" in sentence.lower()
    assert 'data-template="I confirm that the details of {names}, under 15,' in html

    data = {
        "surname": "Under", "first_name": "Kid", "birth_date": _child_birth(stay),
        "nationality": "GBR", "signed_by": str(second["id"]),
        "child_sign_role": "responsible_adult", "sign_for_role": "parent",
    }
    relang = browser.post(f"/l/{TOKEN}/{stay['reservation_id']}/relang?lang=cs", data=data)
    assert relang.status_code == 200, relang.status_code
    assert i18n.translator("cs")("u15_note") in relang.text
    assert _hidden(relang.text, "sig-block")
    assert not re.search(r'name="(signed_by|child_sign_role|sign_for_role)"[^>]*checked', relang.text)


def test_an_adults_role_tick_survives_a_rerender(stay):
    browser = _client(stay)
    _save(browser, stay, "Kiddo", _child_birth(stay), signature="")
    html = _rerender(browser, stay, "Grownup", "1.1.1990", sign_for_role="parent")
    assert 'name="sign_for_role" value="parent" checked' in html
    assert 'name="sign_for_role" value="responsible_adult">' in html


def test_only_whitelisted_values_are_echoed(stay):
    browser = _client(stay)
    _save(browser, stay, "Grownup", "1.1.1990")
    _save(browser, stay, "Auntie", "1.1.1985")
    html = _rerender(
        browser, stay, "Kid", _child_birth(stay), signature="",
        signed_by="1 OR 1", child_sign_role="boss", sign_for_role="boss",
    )
    assert "1 OR 1" not in html
    assert "boss" not in html
    assert not re.search(r'name="(signed_by|child_sign_role|sign_for_role)"[^>]*checked', html)


# --- d. no JavaScript: a plain POST ----------------------------------------------------

def test_a_childs_form_sends_without_a_signature_and_carries_the_role(stay):
    browser = _client(stay)
    adult = _save(browser, stay, "Grownup", "1.1.1990")
    data_without_signature = {"signed_by": str(adult["id"]), "child_sign_role": "parent"}
    response = _post(browser, stay, "Kid", _child_birth(stay), **data_without_signature, signature="")
    assert response.status_code == 303, response.text[-400:]
    rows = db.query("SELECT * FROM guest WHERE reservation_id = ?", (stay["reservation_id"],))
    kid = next(row for row in rows if row["first_name"].upper() == "KID")
    assert kid["signed_for_guest_id"] == adult["id"]
    assert kid["signed_for_role"] == "parent"
    assert not kid["signature_png"]


def test_a_childs_form_sends_with_no_role_and_stores_no_link(stay):
    browser = _client(stay)
    adult = _save(browser, stay, "Grownup", "1.1.1990")
    kid = _save(browser, stay, "Kid", _child_birth(stay), signature="", signed_by=str(adult["id"]))
    assert kid["signed_for_guest_id"] is None
    assert not kid["signed_for_role"]
    assert not kid["signature_png"]
