"""0203/0630: the fee list shows check, then one send-and-pay box (PDF, data box, QR) after the confirm."""
from __future__ import annotations

import re

from tests.test_stay_fee_detail import _property, _stay, host  # noqa: F401


def _csrf(html: str) -> str:
    return re.search(r'<meta name="csrf-token" content="([^"]+)"', html).group(1)


def test_steps_are_locked_until_the_period_is_confirmed(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Vivus Apartment with Balcony & Garage")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    assert 'class="ui-section fee-pay"' in page
    assert 'data-fee-step="1"' in page and "Are these numbers right?" in page
    assert f'/stay-fees/{apartment_id}/pdf?month=2026-08' not in page
    assert 'name="return_to" value="/stay-fees?month=2026-08' in page


def test_confirm_from_the_list_comes_back_with_pdf_and_qr(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Vivus Apartment with Balcony & Garage")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    response = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": _csrf(page), "month": "2026-08", "confirm_collected": "1",
              "return_to": "/stay-fees?month=2026-08"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/stay-fees?month=2026-08")
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    assert f'/stay-fees/{apartment_id}/pdf?month=2026-08' in page
    assert 'data-fee-step="2"' in page
    assert "https://www.mojedatovaschranka.cz/" in page and 'class="fee-qr-panel"' in page


def test_return_to_outside_the_fee_pages_is_ignored(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, "Vivus Apartment with Balcony & Garage")
    _stay(apartment_id, "2026-08-10", "2026-08-14", [{}])
    page = client.get("/stay-fees?month=2026-08&lang=en").text
    response = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": _csrf(page), "month": "2026-08", "confirm_collected": "1",
              "return_to": "https://evil.example/"},
        follow_redirects=False,
    )
    assert response.headers["location"].startswith(f"/stay-fees/{apartment_id}?month=2026-08")
