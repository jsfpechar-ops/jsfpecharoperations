"""0231: the guest-link window is said with the host's own stays."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app import claim, db
from app.main import app
from tests.test_guest_links_bilingual import TOKEN, _apartment_id, host  # noqa: F401


def _stay(apartment_id: int, days_ahead: int) -> int:
    start = claim.prague_today() + timedelta(days=days_ahead)
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": f"wf0231-{days_ahead}",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_the_owner_sees_why_the_guest_link_is_empty(host):  # noqa: F811
    _apartment_id()
    page = host.get(f"/l/{TOKEN}?lang=en")
    assert page.status_code == 200
    assert "data-host-note" in page.text


def test_a_guest_never_sees_the_host_note(host):  # noqa: F811
    _apartment_id()
    page = TestClient(app).get(f"/l/{TOKEN}?lang=en")
    assert "data-host-note" not in page.text


def test_a_far_stay_says_when_it_reaches_the_link_and_offers_its_own_link(host):  # noqa: F811
    apartment_id = _apartment_id()
    reservation_id = _stay(apartment_id, 20)
    page = host.get(f"/reservations/{reservation_id}?lang=en")
    assert page.status_code == 200
    assert 'data-link-window="from"' in page.text
    assert "data-copy-own-link" in page.text
    # 0237: the stay list stays quiet; the stay page carries the date.
    listing = host.get("/reservations?lang=en")
    assert 'data-link-window=' not in listing.text


def test_the_property_editor_names_the_next_stay(host):  # noqa: F811
    apartment_id = _apartment_id()
    _stay(apartment_id, 20)
    page = host.get(f"/apartments/{apartment_id}?view=settings&section=guests&lang=en")
    assert "data-link-window-note" in page.text
