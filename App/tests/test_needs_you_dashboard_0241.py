"""0241 (idea N): the dashboard card carries the alerts; other pages keep the stack."""

from __future__ import annotations

from app import db
from tests.test_alert_stack import _alert, host  # noqa: F401
from tests.test_signed_in_chrome import host_with_property  # noqa: F401


def test_alerts_show_once_on_the_dashboard_and_still_on_other_pages(host_with_property):  # noqa: F811
    owner = db.query_one("SELECT owner_user_id FROM apartment ORDER BY id DESC LIMIT 1")
    db.insert("alert", {
        "level": "warning", "kind": "feed_error", "apartment_id": None,
        "owner_user_id": owner["owner_user_id"], "dedupe_key": "wf0241-feed",
        "message": "Calendar 'Test' could not be synchronised.", "detail": "boom",
        "params": '{"feed": "Test", "error": "boom"}', "created_at": db.utcnow(),
    })
    try:
        dashboard = host_with_property.get("/?lang=en").text
        assert "data-host-alerts" not in dashboard, "the stack repeats the card on the dashboard"
        assert "Calendar &#39;Test&#39; could not be read." in dashboard or "Calendar 'Test' could not be read." in dashboard
        stays = host_with_property.get("/reservations?lang=en").text
        assert "data-host-alerts" in stays
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", ("wf0241-feed",))


def test_the_calm_line_when_nothing_needs_the_host(host_with_property):  # noqa: F811
    page = host_with_property.get("/?lang=en").text
    card = page.split('id="needs-action"', 1)[1].split("</section>", 1)[0]
    if 'class="needs-you-item"' not in card:
        assert "Nothing needs you today." in card
