"""1001: the host page back link points at its parent list, not an empty href."""
from __future__ import annotations

from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401


def test_stay_fee_detail_back_link_has_list_href(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Back Link Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    detail = client.get(f"/stay-fees/{apartment_id}?month=2026-08&lang=en").text
    assert 'class="ui-ph-back airbnb-back" href="/stay-fees?month=2026-08"' in detail
    assert 'class="ui-ph-back airbnb-back" href=""' not in detail
