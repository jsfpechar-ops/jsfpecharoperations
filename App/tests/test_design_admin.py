"""0145: smart locks and the admin pages render on host_page without inline styles."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app import db

from tests.test_smart_locks_page import _client, _connect, hosts, USERS  # noqa: F401

TEMPLATES = ("users.html", "admin_incidents.html", "admin_operations.html", "admin_funnel.html")
LOCK = {"lock_id": "1", "alias": "Door A", "battery": 80, "tz_offset_ms": 3600000}


def _main(page: str) -> str:
    """The page lane only: from the v2 page wrapper to the first shared dialog of base.html."""
    return page.split('<div class="ui-page"', 1)[1].split("<dialog", 1)[0]


def test_smart_locks_has_the_v2_shell_and_one_primary_in_every_state(hosts):
    client = _client(USERS[0])
    states = [client.get("/apartments?lang=en").text]
    _connect(hosts[0], "hjhfa_uhaaaa")
    states.append(client.get("/apartments?lang=en").text)
    db.execute("UPDATE lock_account SET locks_json = ? WHERE owner_user_id = ?", (json.dumps([LOCK]), hosts[0]))
    states.append(client.get("/apartments?lang=en").text)
    for index, page in enumerate(states):
        main = _main(page)
        assert main.count("<h1") == 1, index
        assert 'style="' not in main and not re.search(r'class="(btn|pill)[ "]', main), index
        assert 'href="/apartments" aria-current="page"' in main, index
    assert 'action="/smart-locks/remove"' in states[2] and "data-confirm" in states[2]


def test_templates_have_no_raw_style_or_legacy_control():
    root = Path(__file__).resolve().parents[1] / "app" / "templates"
    for name in TEMPLATES:
        text = (root / name).read_text(encoding="utf-8")
        assert text.startswith('{% extends "host_page.html" %}'), name
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert "page_header" not in text and text.count("ui-btn-primary") <= 1, name
