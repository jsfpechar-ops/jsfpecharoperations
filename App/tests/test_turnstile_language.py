"""UX-128 (audit B-24): the Turnstile widget follows the page language.

Without `data-language` the challenge follows the browser, so a host reading
the Czech login page can be handed an English challenge.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import db, templating
from app.main import app


def _login_page(monkeypatch, lang: str, site_key: str) -> str:
    db.init_db()
    monkeypatch.setitem(templating.templates.env.globals, "turnstile_site_key", site_key)
    response = TestClient(app).get(f"/login?lang={lang}")
    assert response.status_code == 200
    return response.text


def _widget(page: str) -> str:
    start = page.index('class="cf-turnstile"')
    return page[start : page.index("</div>", start)]


def test_the_widget_is_told_which_language_the_page_is_in(monkeypatch):
    assert 'data-language="cs"' in _widget(_login_page(monkeypatch, "cs", "site-key"))


def test_the_english_page_tells_the_widget_english(monkeypatch):
    assert 'data-language="en"' in _widget(_login_page(monkeypatch, "en", "site-key"))


def test_the_widget_stays_hidden_when_turnstile_is_off(monkeypatch):
    assert "cf-turnstile" not in _login_page(monkeypatch, "en", "")
