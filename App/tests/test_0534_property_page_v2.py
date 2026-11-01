"""0534: the property page is one scroll page of details sections on the v2 shell."""
from __future__ import annotations

import re
from pathlib import Path

from app import db
from tests.test_property_hub import host  # noqa: F401  (fixture)

SECTION = re.compile(r'<details class="prop-sec" id="sec-([\w-]+)"( open)?>')


def _page(client, apartment_id, query=""):
    response = client.get(f"/apartments/{apartment_id}{query}")
    assert response.status_code == 200
    return response.text


def _sections(html):
    return [(m.group(1), bool(m.group(2))) for m in SECTION.finditer(html)]


def _opened(client, apartment_id, query=""):
    return [name for name, is_open in _sections(_page(client, apartment_id, query)) if is_open]


def test_page_is_one_scroll_page_without_tabs(host):
    client, apartment_id = host
    html = _page(client, apartment_id)
    assert "property-tabs" not in html
    assert "data-property-view" not in html
    assert "data-property-views" not in html
    assert "data-settings-group" not in html
    assert "property-settings-nav" not in html
    assert 'class="crumb"' in html
    assert "<h1>" in html
    assert 'class="savebar"' in html


def test_sections_are_details_in_order(host):
    client, apartment_id = host
    names = [name for name, _ in _sections(_page(client, apartment_id))]
    # The fixture has no door codes, so the lock section is not rendered.
    assert names == ["basics", "archive", "messages", "police", "fee", "calendars"]


def test_no_view_opens_basics_only(host):
    client, apartment_id = host
    assert _opened(client, apartment_id) == ["basics"]


def test_section_guests_opens_messages(host):
    client, apartment_id = host
    assert _opened(client, apartment_id, "?view=settings&section=guests") == ["messages"]


def test_section_reporting_opens_police_and_fee(host):
    client, apartment_id = host
    assert _opened(client, apartment_id, "?view=settings&section=reporting") == ["police", "fee"]


def test_bookings_view_opens_calendars(host):
    client, apartment_id = host
    assert _opened(client, apartment_id, "?view=bookings") == ["calendars"]


def test_old_anchor_ids_still_resolve(host):
    client, apartment_id = host
    html = _page(client, apartment_id)
    for anchor in ("basics", "address", "communication", "ubyport", "automation",
                   "stay-fee-settings", "calendars"):
        assert f'id="{anchor}"' in html, anchor


def test_settings_form_still_saves_a_field(host):
    client, apartment_id = host
    apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    response = client.post(
        f"/apartments/{apartment_id}",
        data={
            "return_to": f"/apartments/{apartment_id}",
            "internal_name": "Renamed Flat",
            "legal_entity_id": apt["legal_entity_id"],
            "permalink_pin": apt["permalink_pin"],
            "permalink_window_days": str(apt["permalink_window_days"] or 2),
            "permalink_reachback_days": str(apt["permalink_reachback_days"] or 365),
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    row = db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (apartment_id,))
    assert row["internal_name"] == "Renamed Flat"


# 0535: the mockup order is CSS only (DOM order stays); the aside links to the sections.
MOCKUP_ORDER = {"basics": 1, "police": 2, "calendars": 3, "messages": 4, "lock": 5, "fee": 6, "archive": 7, "lock-account": 8}
APP2_CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "app2.css"


def test_css_order_is_the_mockup_order():
    css = APP2_CSS.read_text(encoding="utf-8")
    for key, rank in MOCKUP_ORDER.items():
        assert re.search(r"body\.v2 #sec-%s\{order:%d\}" % (re.escape(key), rank), css), key


def test_rendered_sections_show_in_mockup_order(host):
    client, apartment_id = host
    names = [name for name, _ in _sections(_page(client, apartment_id))]
    visible = sorted(names, key=lambda name: MOCKUP_ORDER[name])
    assert visible == ["basics", "police", "calendars", "messages", "fee", "archive"]


def test_aside_has_cards_and_links_to_each_section(host):
    client, apartment_id = host
    html = _page(client, apartment_id)
    start = html.index('<aside class="preview"')
    aside = html[start:html.index("</aside>", start)]
    assert aside.count('class="pv"') >= 2
    for key in ("basics", "police", "calendars", "lock", "fee"):
        assert f'href="#sec-{key}"' in aside, key
