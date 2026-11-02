"""0232: the five-step strip and the stay tracker."""

from __future__ import annotations

from datetime import timedelta

from app import claim, db
from tests.test_guest_links_bilingual import _apartment_id, host  # noqa: F401


def _stay(apartment_id: int) -> int:
    start = claim.prague_today() + timedelta(days=1)
    return db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "wf0232-a",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=2)).isoformat(),
        "status": "active", "source": "airbnb", "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def test_the_empty_dashboard_tells_the_whole_story_with_the_hosts_own_option(host):  # noqa: F811
    _apartment_id()  # automation_mode manual
    page = host.get("/?lang=en")
    assert page.status_code == 200
    # 0706: removed from Overview by the v2 rebuild (the strip stays on /guide, see below)
    assert "data-workflow-strip" not in page.text
    assert 'data-workflow-step="paste"' not in page.text
    assert 'data-workflow-step="police_manual"' not in page.text


def test_the_guide_opens_with_the_strip(host):  # noqa: F811
    page = host.get("/guide?lang=en")
    assert "data-workflow-strip" in page.text


# 0528/0526: the v2 stays pages (approved mockup) show the status pill and deadline instead of the
# five-step journey strip, so the per-stay "Step 2 of 5" checks were removed; the guide keeps the strip.
