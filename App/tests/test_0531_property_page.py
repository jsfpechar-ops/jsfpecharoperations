"""Property page restyle (brief 0531): guest-link card, save bar, POST still saves."""
from __future__ import annotations

import re

from app import db
from tests.test_property_hub import host, two_properties  # noqa: F401  (fixtures)


def test_property_page_has_guest_link_card_with_one_copy_button(host):
    client, apartment_id = host
    text = client.get(f"/apartments/{apartment_id}?lang=en").text
    assert 'class="card guest-card"' in text
    assert text.count('data-copy="property-guest-url"') == 1


def test_overview_no_longer_has_its_own_guest_url_copy(host):
    client, apartment_id = host
    text = client.get(f"/apartments/{apartment_id}?view=overview&lang=en").text
    assert "overview-guest-url" not in text


def test_settings_save_row_is_a_save_bar_with_save_last(host):
    client, apartment_id = host
    text = client.get(f"/apartments/{apartment_id}?view=settings&lang=en").text
    match = re.search(
        r'<div class="savebar">(.*?)</div>', text, re.S
    )
    assert match, "settings save row must carry savebar"
    tags = re.findall(r"<(?:button|a)\b[^>]*>", match.group(1))
    assert tags, "save bar has no buttons"
    assert 'type="submit"' in tags[-1], "Save must be the last button in the save bar"


def test_property_save_still_saves_after_restyle(host):
    client, apartment_id = host
    apt = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    response = client.post(
        f"/apartments/{apartment_id}",
        data={
            "return_to": f"/apartments/{apartment_id}",
            "internal_name": apt["internal_name"],
            "legal_entity_id": apt["legal_entity_id"],
            "permalink_pin": apt["permalink_pin"],
            "permalink_window_days": str(apt["permalink_window_days"] or 2),
            "permalink_reachback_days": str(apt["permalink_reachback_days"] or 365),
        },
        follow_redirects=False,
    )
    assert response.status_code in (303, 302)
