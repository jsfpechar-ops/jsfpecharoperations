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

from app import db, host_i18n, templating
from app.main import app
from app.routes.legal import (
    DPA_SECTION_IDS,
    PRIVACY_SECTION_IDS,
    TERMS_SECTION_IDS,
)

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


# ---- UX-111: the documents cross-reference each other by path ---------------
#
# The bodies used to say "the Data Processing Agreement at /dpa" and leave the
# reader to retype the URL. A filter now turns the five sibling paths into
# links. The copy is untouched, so these tests check the rendering rather than
# the strings.

# A cross-reference is a sibling path standing on its own after a space, and
# not the tail of a longer route such as the guest notice `/l/{token}/privacy`.
# Deliberately stricter than the filter, so the test can only under-count.
REFERENCE_RE = re.compile(
    r"(?<=\s)(/(?:dpa|legal|privacy|subprocessors|terms))(?=$|[\s.,;:)])"
)
ANCHOR_RE = re.compile(r'<a href="(/(?:dpa|legal|privacy|subprocessors|terms))">')
SIBLING_PATHS = ("/dpa", "/legal", "/privacy", "/subprocessors", "/terms")

# The prose each page renders, and nothing else, so a link in the shared
# cross-link row at the foot of the page cannot stand in for a link in a body.
BODY_KEYS = {
    "/legal": (
        "legal.roles_body",
        "legal.software_body",
        "legal.security_body",
        "legal.dpa_body",
        "legal.disclaimer_body",
    ),
    "/terms": tuple(f"terms.s{sid}_body" for sid in TERMS_SECTION_IDS),
    "/privacy": tuple(f"privacy.s{sid}_body" for sid in PRIVACY_SECTION_IDS),
    "/dpa": ("dpa.incorporation_note",)
    + tuple(f"dpa.s{sid}_body" for sid in DPA_SECTION_IDS),
}


def _bodies(html: str) -> list[str]:
    """The prose of a legal page, links and all.

    The cross-link row at the foot of each page is excluded: it is a link list,
    so a link there must not stand in for a link in the prose.
    """
    bodies = re.findall(r'<div class="terms-section">(.*?)</div>', html, re.S)
    bodies += [
        para
        for para in re.findall(r'<p class="small muted">(.*?)</p>', html, re.S)
        if "&middot;" not in para
    ]
    return bodies


def _linkify(text: str) -> str:
    return str(templating.templates.env.filters["legal_links"](text))


def test_no_legal_body_leaves_a_cross_reference_as_plain_text():
    for path, keys in BODY_KEYS.items():
        for lang in ("en", "cs"):
            html = _client().get(f"{path}?lang={lang}").text
            for body in _bodies(html):
                # Drop the anchors entirely, then look for a path left behind.
                plain = re.sub(r"<a\b[^>]*>.*?</a>", "", body, flags=re.S)
                assert REFERENCE_RE.findall(plain) == [], (path, lang, plain[:200])


def test_every_legal_page_that_names_a_sibling_path_links_it():
    for path, keys in BODY_KEYS.items():
        for lang in ("en", "cs"):
            html = _client().get(f"{path}?lang={lang}").text
            linked = set()
            for body in _bodies(html):
                linked.update(ANCHOR_RE.findall(body))
            expected = set()
            for key in keys:
                expected.update(REFERENCE_RE.findall(host_i18n.translate(lang, key)))
            assert expected, (path, lang, "no cross-reference to test")
            assert linked == expected, (path, lang, linked, expected)


def test_the_link_text_is_the_path_so_no_copy_changed():
    html = _client().get("/terms?lang=en").text
    assert '<a href="/dpa">/dpa</a>' in html
    html = _client().get("/terms?lang=cs").text
    assert '<a href="/dpa">/dpa</a>' in html


def test_both_languages_link_the_same_paths():
    for path in BODY_KEYS:
        linked = {}
        for lang in ("en", "cs"):
            html = _client().get(f"{path}?lang={lang}").text
            found = set()
            for body in _bodies(html):
                found.update(ANCHOR_RE.findall(body))
            linked[lang] = found
        assert linked["en"], path
        assert linked["en"] == linked["cs"], path


def test_the_guest_notice_route_is_not_mistaken_for_the_privacy_page():
    # `/l/{token}/privacy` ends in a sibling path but is a different page.
    html = _client().get("/privacy?lang=en").text
    assert "/l/{token}/privacy" in html
    assert "/l/{token}/<a" not in html


def test_the_filter_only_links_a_whole_sibling_path():
    assert "<a " not in _linkify("See the notice at /l/{token}/privacy, please.")
    assert "<a " not in _linkify("Sign in at /login or read /legalnotices.")
    assert _linkify("Contact details on /legal.") == (
        'Contact details on <a href="/legal">/legal</a>.'
    )


def test_the_filter_escapes_the_body_before_it_adds_links():
    out = _linkify('<script>alert("x")</script> the agreement at /dpa')
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert '<a href="/dpa">/dpa</a>' in out


def test_the_filter_leaves_ordinary_prose_alone():
    assert _linkify("Nothing to link here.") == "Nothing to link here."
