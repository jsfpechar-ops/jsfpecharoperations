"""0957: a lock action result shows inside its section, once, and the Save row ends the property page."""
from __future__ import annotations

import re

from app import ttlock
from tests.test_smart_locks_page import USERS, _client, _connect, _post, flats, hosts  # noqa: F401


def _failed_refresh_page(hosts, flats, monkeypatch):
    _connect(hosts[0], "hjhfa_uhaaaa")

    def fail(_account_id):
        raise ttlock.TTLockError("synthetic", kind="network")

    monkeypatch.setattr(ttlock, "check_locks", fail)
    client = _client(USERS[0])
    response = _post(client, "/smart-locks/refresh", return_to=f"/apartments/{flats[0]}", section="list")
    location = response.headers["location"]
    assert "sec=lock" in location and location.endswith("#sec-lock")
    return client.get(location).text


def test_the_notice_sits_inside_the_lock_section_and_is_not_repeated(hosts, flats, monkeypatch):
    html = _failed_refresh_page(hosts, flats, monkeypatch)
    match = re.search(r'data-section-notice[^>]*><span class="grow">(.*?)</span>', html, re.S)
    assert match, "no inline notice on the property page"
    assert html.index('id="sec-lock"') < html.index("data-section-notice")
    assert html.count(match.group(1)) == 1, "the top toast repeats the notice"


def test_the_save_row_is_one_bar_after_the_sections_and_before_the_preview(hosts, flats, monkeypatch):
    html = _failed_refresh_page(hosts, flats, monkeypatch)
    assert html.count('class="savebar') == 1
    bar = html.index('class="savebar')
    assert html.index('id="sec-lock"') < bar < html.index('<aside class="preview"')
    assert re.search(r'<button class="btn" type="submit" form="property-settings-form">', html)
