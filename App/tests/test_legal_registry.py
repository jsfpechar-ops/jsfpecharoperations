"""The legal pages localize the ARES link and the footer's Legal label.

"ARES (public register)" was hard-coded English on the CS page, the CS footer
link read the bare adjective "Právní", and legal.footer_short / nav_label were
each defined twice per language so the later value silently won (D-27 / UX-158).
"""
from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from app import db, host_i18n
from app.main import app

HOST_I18N = Path(__file__).resolve().parents[1] / "app" / "host_i18n.py"
LEGAL_PAGES = ("/legal", "/terms", "/privacy", "/dpa")
REGISTRY_EN = "ARES (public register)"
REGISTRY_CS = "ARES (veřejný rejstřík)"


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _get(path: str, lang: str) -> str:
    joiner = "&" if "?" in path else "?"
    response = _client().get(f"{path}{joiner}lang={lang}")
    assert response.status_code == 200, f"{path} answered {response.status_code}"
    return response.text


def test_the_registry_link_copy_is_in_both_dictionaries():
    assert host_i18n.STRINGS["en"]["legal.registry_link"] == REGISTRY_EN
    assert host_i18n.STRINGS["cs"]["legal.registry_link"] == REGISTRY_CS


def test_every_legal_page_localizes_the_registry_link():
    for page in LEGAL_PAGES:
        assert REGISTRY_EN in _get(page, "en"), page
        czech = _get(page, "cs")
        assert REGISTRY_CS in czech, page
        assert REGISTRY_EN not in czech, page


def test_the_czech_footer_legal_label_is_a_noun_phrase():
    assert host_i18n.STRINGS["cs"]["legal.footer_short"] == "Právní informace"
    assert "Právní informace" in _get("/", "cs")


def test_the_legal_footer_keys_are_defined_once_per_language():
    source = HOST_I18N.read_text(encoding="utf-8")
    for key in ("legal.footer_short", "legal.footer_nav_label"):
        assert source.count(f'"{key}"') == 2, f"{key} is duplicated"
