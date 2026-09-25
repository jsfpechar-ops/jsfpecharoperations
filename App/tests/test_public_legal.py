"""The legal pages are public pages, so they get public chrome.

They used to extend `base.html`, the signed-in host shell, with
`show_nav = false`. A stranger reading the Terms was therefore served the
command palette, the CSV-export dialog, the keyboard-shortcut sheet and
`app.js`, had no logo to click home, no way to switch language, and the only
exit was "Back to login" — to a page they had never seen.
"""
from __future__ import annotations

import re

from starlette.testclient import TestClient

from app import db, host_i18n
from app.main import app

LEGAL_PATHS = ("/legal", "/terms", "/privacy", "/dpa", "/subprocessors")

LEGAL_TEMPLATES = (
    "legal.html",
    "terms.html",
    "privacy.html",
    "dpa.html",
    "subprocessors.html",
)

# What `base.html` adds for signed-in hosts. None of it belongs on a page a
# stranger can read.
HOST_FURNITURE = (
    'class="sidebar"',
    'class="appbar"',
    "data-nav-toggle",
    "data-command-open",
    "data-confirm",
    'id="command-palette"',
    "/static/app.js",
)


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _read(name: str) -> str:
    from pathlib import Path

    return (
        Path(__file__).resolve().parents[1] / "app" / "templates" / name
    ).read_text(encoding="utf-8")


def test_every_legal_page_extends_the_public_base_not_the_host_shell():
    for name in LEGAL_TEMPLATES:
        template = _read(name)
        assert '{% extends "public_legal_base.html" %}' in template, name
        assert '{% extends "base.html" %}' not in template, name
        assert "show_nav" not in template, name


def test_the_public_legal_base_wears_the_shared_public_chrome():
    base = _read("public_legal_base.html")
    assert '{% include "_public_header.html" %}' in base
    assert '{% include "_public_footer.html" %}' in base
    # The reading column the legal templates were written against.
    assert re.search(r'<main id="content" class="wrap', base)
    assert "{% block content %}{% endblock %}" in base


def test_the_legal_base_keeps_the_stylesheets_the_reading_column_needs():
    base = _read("public_legal_base.html")
    # `panel`, `kv`, `table-cards` and the page header all live in app.css /
    # components.css, so dropping them would flatten these pages.
    for sheet in ("tokens.css", "landing.css", "app.css", "components.css"):
        assert sheet in base, sheet


def test_no_legal_page_ships_host_furniture_or_host_javascript():
    for path in LEGAL_PATHS:
        html = _client().get(f"{path}?lang=en").text
        for needle in HOST_FURNITURE:
            assert needle not in html, (path, needle)


def test_every_legal_page_carries_the_public_header_and_footer():
    for path in LEGAL_PATHS:
        html = _client().get(f"{path}?lang=en").text
        assert 'class="landing-header"' in html, path
        assert 'class="landing-footer"' in html, path
        # The logo is the way home for a visitor who never logged in.
        assert 'class="landing-brand"' in html, path


def test_every_legal_page_offers_the_language_switch():
    for path in LEGAL_PATHS:
        html = _client().get(f"{path}?lang=cs").text
        assert f'href="{path}?lang=en"' in html, path
        assert f'href="{path}?lang=cs"' in html, path


def test_back_to_ubyhost_replaces_back_to_login():
    for path in LEGAL_PATHS:
        html = _client().get(f"{path}?lang=en").text
        assert host_i18n.translate("en", "legal.back_login") not in html, path
        assert host_i18n.translate("en", "legal.back_home") in html, path
        # And it goes home, not to the login form.
        assert '<a href="/?lang=en">' in html, path


def test_back_home_is_translated_and_kept_at_parity():
    english = host_i18n.translate("en", "legal.back_home")
    czech = host_i18n.translate("cs", "legal.back_home")
    assert english == "Back to UbyHost"
    assert czech == "Zpět na UbyHost"
    assert english != czech, "a missing translation falls back to the English key"


def test_the_legal_pages_keep_a_way_to_log_in():
    # The shared footer keeps "Host login", so the chrome swap did not strand
    # an existing host who followed a link out of the login page.
    for path in LEGAL_PATHS:
        html = _client().get(f"{path}?lang=en").text
        assert f'href="/login?lang=en"' in html, path
