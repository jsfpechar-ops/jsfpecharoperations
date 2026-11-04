"""0949: the dashboard no longer reminds the host to paste the guest message."""

from __future__ import annotations

from app import claim, db
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401


def _stay_today(apartment_id: int) -> int:
    today = claim.prague_today().isoformat()
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "wf0233-a", "date_from": today, "date_to": "2099-01-01",
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_dashboard_never_shows_the_paste_reminder(host):  # noqa: F811
    _stay_today(_apartment_id())
    for lang, text in (("en", "No guest has used the link"), ("cs", "Host ještě nepoužil odkaz")):
        page = host.get(f"/?lang={lang}").text
        assert "data-paste-check" not in page
        assert 'data-needs-you="paste"' not in page
        assert text not in page
