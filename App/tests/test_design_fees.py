"""0142: stay fee pages render on host_page; one primary on the period detail."""
from __future__ import annotations

from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401


def test_fee_list_and_detail_have_the_v2_shells(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Design Demo")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    listing = client.get("/stay-fees?month=2026-08&lang=en").text
    assert listing.count("<h1") == 1 and 'data-body-kind="list"' in listing
    assert 'class="ui-toolbar"' in listing and "ui-btn-primary filter-apply" in listing
    assert listing.count('class="ui-btn ui-btn-primary"') == 1  # 0292: one primary per card (Yes)
    detail = client.get(f"/stay-fees/{apartment_id}?month=2026-08&lang=en").text
    assert 'data-body-kind="detail"' in detail and 'class="ui-ph-back"' in detail
    assert detail.count('class="ui-btn ui-btn-primary"') == 1
    assert detail.index('class="ui-ph"') < detail.index('class="stay-metrics')


def test_templates_have_no_raw_style_or_legacy_control():
    for name in ("stay_fees.html", "stay_fee_detail.html"):
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
