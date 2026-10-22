"""0233: the dashboard reminds the host until a guest has used the link."""

from __future__ import annotations

from app import claim, db
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401


def _stay_today(apartment_id: int) -> int:
    today = claim.prague_today().isoformat()
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "wf0233-a", "date_from": today, "date_to": "2099-01-01",
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_no_card_before_any_stay_reaches_the_link(host):  # noqa: F811
    _apartment_id()
    assert "data-paste-check" not in host.get("/?lang=en").text


def test_card_shows_until_a_guest_claims_a_stay(host):  # noqa: F811
    reservation_id = _stay_today(_apartment_id())
    assert "data-paste-check" in host.get("/?lang=en").text
    db.insert("reservation_claim", {
        "reservation_id": reservation_id, "state": "claimed", "token_version": 0,
        "claimed_at": db.utcnow(), "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    assert "data-paste-check" not in host.get("/?lang=en").text
