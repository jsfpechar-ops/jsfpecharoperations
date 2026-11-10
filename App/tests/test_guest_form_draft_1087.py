"""Brief 1087: the guest form posts its draft and says when one came back.

1082 built the store and the ``/draft`` route. Here: the autosave script only
reads the form, the page shows one "Welcome back" line after a restore, and the
language switch and the validation error keep autosave on for a new guest.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db, i18n, mail
from app.main import app
from tests.conftest import login_as
from tests.test_guest_child_document import TOKEN, _cleanup, _payload, _seed

APP_DIR = Path(__file__).resolve().parents[1] / "app"
HOST = "draft1087-host"
WELCOME = {
    "en": "Welcome back. Continue where you left off.",
    "cs": "Vítejte zpět. Pokračujte tam, kde jste skončili.",
    "de": "Willkommen zurück. Machen Sie dort weiter, wo Sie aufgehört haben.",
    "es": "Bienvenido de nuevo. Continúe donde lo dejó.",
    "fr": "Bon retour. Reprenez là où vous vous êtes arrêté.",
    "uk": "З поверненням. Продовжте з того місця, де зупинилися.",
}
WELCOME_RE = re.compile(r'<p class="g-ok" id="draft-welcome" role="status">([^<]*)</p>')
OWNED_RE = re.compile(r'data-draft-owned="(\d+)"')


def _drop_drafts(reservation_id: int) -> None:
    db.execute("DELETE FROM guest_form_draft WHERE reservation_id = ?", (reservation_id,))


@pytest.fixture
def stay(monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    reservation_id = _seed()
    try:
        yield reservation_id
    finally:
        _drop_drafts(reservation_id)
        _cleanup()


def _draft(client, rid: int, **data):
    data.setdefault("draft_owned", "0")
    return client.post(f"/l/{TOKEN}/{rid}/draft?lang=en", data=data)


def _new(client, rid: int, lang: str = "en"):
    return client.get(f"/l/{TOKEN}/{rid}/new?lang={lang}")


def _save(client, rid: int, **overrides):
    return client.post(
        f"/l/{TOKEN}/{rid}/save?lang=en", data=_payload(**overrides), follow_redirects=False
    )


def _relang(client, rid: int, **overrides):
    return client.post(f"/l/{TOKEN}/{rid}/relang?lang=cs", data=_payload(**overrides))


def _sent_guest_id(rid: int) -> int:
    row = db.query_one("SELECT id FROM guest WHERE reservation_id = ? ORDER BY id DESC", (rid,))
    assert row, "the save stored no guest"
    return int(row["id"])


# --- a. the script only reads the form --------------------------------------


def _draft_script() -> str:
    source = (APP_DIR / "static" / "signature.js").read_text(encoding="utf-8")
    start = source.index("  function initGuestDraft() {")
    return source[start : source.index("\n  }\n", start)]


def test_the_autosave_script_reads_and_never_writes():
    script = _draft_script()
    for banned in (".value =", ".checked =", "innerHTML", "passport_photo", "signature", "legal_ack"):
        assert banned not in script, banned
    for needed in (
        "keepalive",
        "pagehide",
        "draft_owned",
        "data-lang-draft",
        "if (!el) return;",
        "names.indexOf(",
        "2000",
        "15000",
    ):
        assert needed in script, needed


def test_the_script_is_started_once():
    source = (APP_DIR / "static" / "signature.js").read_text(encoding="utf-8")
    assert source.count("initGuestDraft();") == 1


def test_the_form_has_one_welcome_line_and_one_owned_attribute():
    form = (APP_DIR / "templates" / "guest" / "form.html").read_text(encoding="utf-8")
    assert form.count('id="draft-welcome"') == 1
    assert form.count("data-draft-owned") == 1


def test_the_welcome_copy_exists_in_six_languages():
    for lang, text in WELCOME.items():
        assert i18n.translator(lang)("draft_welcome") == text


# --- b. what the page renders -----------------------------------------------


@pytest.mark.parametrize("lang", sorted(WELCOME))
def test_a_returning_device_sees_the_welcome_line_in_its_language(stay, lang):
    device = TestClient(app)
    assert _draft(device, stay, surname="Zzdraftsur", first_name="Zzdraftfirst").status_code == 204
    page = _new(device, stay, lang)
    assert page.status_code == 200
    assert WELCOME_RE.findall(page.text) == [WELCOME[lang]]
    assert "Zzdraftsur" in page.text
    assert f'data-draft-url="/l/{TOKEN}/{stay}/draft' in page.text


def test_a_fresh_device_gets_autosave_and_no_welcome_line(stay):
    first = TestClient(app)
    assert _draft(first, stay, surname="Zzdraftsur").status_code == 204
    page = _new(TestClient(app), stay)
    assert page.status_code == 200
    assert f'data-draft-url="/l/{TOKEN}/{stay}/draft' in page.text
    assert "data-draft-fields=" in page.text
    assert OWNED_RE.findall(page.text) == ["0"]
    assert "draft-welcome" not in page.text
    assert "Zzdraftsur" not in page.text


def test_the_owned_count_is_the_number_of_guests_this_device_sent(stay):
    device = TestClient(app)
    assert OWNED_RE.findall(_new(device, stay).text) == ["0"]
    saved = _save(device, stay)
    assert saved.status_code == 303, saved.text[:300]
    assert OWNED_RE.findall(_new(device, stay).text) == ["1"]
    assert OWNED_RE.findall(_new(TestClient(app), stay).text) == ["0"]


def test_the_edit_form_has_no_autosave(stay):
    device = TestClient(app)
    assert _save(device, stay).status_code == 303
    page = device.get(f"/l/{TOKEN}/{stay}/edit/{_sent_guest_id(stay)}?lang=en")
    assert page.status_code == 200
    assert 'id="guest-form"' in page.text
    assert "data-draft-url" not in page.text and "draft-welcome" not in page.text


def test_the_host_preview_has_no_autosave(stay):
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (HOST,))
    owner_id = (
        int(row["id"])
        if row
        else auth.create_account(f"{HOST}@example.test", HOST.title(), role="host", username=HOST)
    )
    db.execute("UPDATE apartment SET owner_user_id = ? WHERE permalink_token = ?", (owner_id, TOKEN))
    host = TestClient(app)
    signed_in = login_as(host, HOST, url="/login?lang=en", remember=True, follow_redirects=False)
    assert signed_in.status_code == 303, signed_in.text
    page = _new(host, stay)
    assert page.status_code == 200
    assert 'id="guest-form"' in page.text
    assert "data-draft-url" not in page.text and "draft-welcome" not in page.text


# --- c. the two re-renders ---------------------------------------------------


def test_a_language_switch_keeps_autosave_on_without_the_welcome_line(stay):
    device = TestClient(app)
    assert _draft(device, stay, surname="Zzdraftsur").status_code == 204
    page = _relang(device, stay, surname="Zzdraftsur")
    assert page.status_code == 200
    assert f'data-draft-url="/l/{TOKEN}/{stay}/draft?lang=cs"' in page.text
    assert OWNED_RE.findall(page.text) == ["0"]
    assert "draft-welcome" not in page.text


def test_a_validation_error_keeps_autosave_on_without_the_welcome_line(stay):
    device = TestClient(app)
    assert _draft(device, stay, surname="Zzdraftsur").status_code == 204
    page = _save(device, stay, surname="Zzdraftsur", birth_date="")
    assert page.status_code == 422
    assert f'data-draft-url="/l/{TOKEN}/{stay}/draft' in page.text
    assert OWNED_RE.findall(page.text) == ["0"]
    assert "draft-welcome" not in page.text


def test_the_re_renders_carry_the_owned_count_of_this_device(stay):
    device = TestClient(app)
    assert _save(device, stay).status_code == 303
    page = _relang(device, stay, surname="Other", first_name="Person", doc_number="P7654321")
    assert page.status_code == 200
    assert OWNED_RE.findall(page.text) == ["1"]


def test_the_re_renders_of_an_edit_have_no_autosave(stay):
    device = TestClient(app)
    assert _save(device, stay).status_code == 303
    guest_id = str(_sent_guest_id(stay))
    relang = _relang(device, stay, guest_id=guest_id)
    assert relang.status_code == 200
    assert 'id="guest-form"' in relang.text and "data-draft-url" not in relang.text
    failed = _save(device, stay, guest_id=guest_id, birth_date="")
    assert failed.status_code == 422
    assert 'id="guest-form"' in failed.text and "data-draft-url" not in failed.text
