"""0324: the panel is on every host page; its launchers are links."""
from __future__ import annotations

import html

from app import config, havel
from tests.test_submission_retry_cap import host as host  # noqa: F401


def test_panel_max_matches_the_engine_constant():
    assert havel.MAX_MESSAGE_CHARS == 600  # the literal in _havel_panel.html


def _on(monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")


def _panel(page):
    return page.split('id="havel-sheet"', 1)[1].split("</dialog>", 1)[0]


def test_panel_shows_the_off_state_up_front_for_a_host_without_havel(host):
    page = html.unescape(host.get("/?lang=en").text)
    panel = _panel(page)
    assert "havel-status" in panel and "havel-support-open" in panel and 'id="havel-message"' not in panel
    assert page.count('data-sheet-open="havel-sheet"') == 1 and "data-havel-more" not in page  # only the corner button, no Help entries


def test_panel_shows_the_limit_state_up_front_when_over_the_limit(host, monkeypatch):
    _on(monkeypatch)
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: "limit_burst")
    panel = _panel(html.unescape(host.get("/?lang=en").text))
    assert "havel-status" in panel and "havel-support-open" in panel and 'id="havel-message"' not in panel


def test_panel_shows_the_composer_for_a_host_with_havel(host, monkeypatch):
    _on(monkeypatch)
    monkeypatch.setattr(havel, "limit_state", lambda uid, now=None: None)
    page = html.unescape(host.get("/?lang=en").text)
    panel = _panel(page)
    assert 'id="havel-message"' in panel and "havel-support-open" not in panel
    assert "data-havel-other" not in panel and "Other topic" not in panel
    assert page.count('data-sheet-open="havel-sheet"') == 2 and "data-havel-more" in page


def test_fab_and_greeting_on_the_dashboard_but_not_on_havel(host, monkeypatch):
    _on(monkeypatch)
    page = html.unescape(host.get("/?lang=en").text)
    assert 'id="havel-sheet"' in page and page.count('data-sheet-open="havel-sheet"') == 2  # the FAB and the Help entry in the account menu
    assert page.count("data-havel-fab") == 1 and "data-havel-modeless" in page
    assert 'class="host-help havel-launcher"' not in page and "ui-btn-icon havel-launcher" not in page
    assert "data-havel-more" in page and "/static/havel.js?v=" in page
    assert page.count("data-havel-greeting") == 1 and "Hi, I'm Havel" in page
    assert "Dobrý den, jsem Havel" in html.unescape(host.get("/?lang=cs").text)
    own = html.unescape(host.get("/havel?lang=en").text)
    assert 'id="havel-sheet"' not in own and "data-havel-fab" not in own
    assert own.count("data-havel-greeting") == 1 and "Hi, I'm Havel" in own
