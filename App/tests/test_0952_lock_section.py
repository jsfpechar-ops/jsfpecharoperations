"""0952: one Smart lock accordion on the property page, with unique DOM ids."""
from __future__ import annotations

import re
from collections import Counter
from unittest.mock import patch

from tests.test_property_hub import host  # noqa: F401  (fixture)
from tests.test_0534_property_page_v2 import _page

ID = re.compile(r'\sid="([^"{]+)"')
SUMMARY_TITLE = re.compile(r'<details class="prop-sec" id="sec-lock"[^>]*><summary>.*?<b>(.*?)</b>', re.S)
PANEL = {"smart_locks_enabled": True, "account": None, "receiver": "", "locks": [], "fetched_at": None,
         "reauth": False, "return_to": "/smart-locks", "properties_using": {}}


def _dup_ids(html):
    return [name for name, count in Counter(ID.findall(html)).items() if count > 1]


def _check_one_section(html):
    assert html.count('id="sec-lock"') == 1
    assert 'sec-lock-account' not in html
    title = SUMMARY_TITLE.search(html).group(1)
    assert title and html.count(f"<b>{title}</b>") == 1
    assert _dup_ids(html) == []
    return title


def test_one_lock_section_without_account(host):
    client, apartment_id = host
    _check_one_section(_page(client, apartment_id, "?lang=en"))


def test_one_lock_section_with_lock_panel(host):
    client, apartment_id = host
    with patch("app.routes.admin._smart_lock_panel_context", return_value=PANEL):
        html = _page(client, apartment_id, "?lang=en")
    _check_one_section(html)
    if 'id="smart-locks"' in html or 'id="door-code"' in html:
        start = html.index('id="sec-lock"')
        end = html.index("</details>", start)
        inner = html[start:end]
        assert inner.count('id="smart-locks"') + inner.count('id="door-code"') >= 1
