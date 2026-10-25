"""0324: the panel is on every host page; its launchers are links."""
from __future__ import annotations

import html

from app import havel
from tests.test_submission_retry_cap import host as host  # noqa: F401


def test_panel_max_matches_the_engine_constant():
    assert havel.MAX_MESSAGE_CHARS == 600  # the literal in _havel_panel.html


def test_fab_and_greeting_on_the_dashboard_but_not_on_havel(host):
    page = html.unescape(host.get("/?lang=en").text)
    assert 'id="havel-sheet"' in page and page.count('data-sheet-open="havel-sheet"') == 1
    assert page.count("data-havel-fab") == 1 and "data-havel-modeless" in page
    assert 'class="host-help havel-launcher"' not in page and "ui-btn-icon havel-launcher" not in page
    assert "data-havel-more" in page and "/static/havel.js?v=" in page
    assert page.count("data-havel-greeting") == 1 and "Hello, I'm Havel" in page
    assert "Dobrý den, jsem Havel" in html.unescape(host.get("/?lang=cs").text)
    own = html.unescape(host.get("/havel?lang=en").text)
    assert 'id="havel-sheet"' not in own and "data-havel-fab" not in own
    assert own.count("data-havel-greeting") == 1 and "Hello, I'm Havel" in own
