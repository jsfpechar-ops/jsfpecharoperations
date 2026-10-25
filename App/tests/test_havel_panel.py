"""0324: the panel is on every host page; its launchers are links."""
from __future__ import annotations

import html
import re

from app import havel
from tests.test_submission_retry_cap import host as host  # noqa: F401


def test_panel_max_matches_the_engine_constant():
    assert havel.MAX_MESSAGE_CHARS == 600  # the literal in _havel_panel.html


def test_panel_and_launchers_on_the_dashboard_but_not_on_havel(host):
    page = html.unescape(host.get("/?lang=en").text)
    assert 'id="havel-sheet"' in page and page.count('data-sheet-open="havel-sheet"') == 2
    assert 'data-havel-more' in page and '/static/havel.js?v=' in page
    assert re.search(r'<a class="host-help havel-launcher" href="/havel"', page)
    assert page.count("Havel (AI)") >= 3
    own = html.unescape(host.get("/havel?lang=en").text)
    assert 'id="havel-sheet"' not in own
    assert re.search(r'<a class="host-help havel-launcher"[^>]*aria-current="page"', own)
