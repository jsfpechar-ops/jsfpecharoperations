"""Owner 2026-11-13: "Fix rejection" did nothing on a phone (it linked to #guests,
the list already on screen). It opens the first refused guest's card.

Screenshots: UBYHOST_SHOTS_DIR=<dir> writes calendar-fix-rejection-stay-<width>.png
and calendar-fix-rejection-guest-<width>.png.
"""
from __future__ import annotations

from app import db, reporting
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_0766_phone_stays_browser import _cookie
from tests.test_dashboard_calendar_browser import shot
from tests.test_host_quiet_dashboard_browser import _launch, base, dashboard_host, dashboard_rich_host, sync_api  # noqa: F401

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]


def test_fix_rejection_opens_the_refused_guests_card(base, dashboard_rich_host):
    reservation_id = dashboard_rich_host["ready"]
    guest = db.query_one(
        "SELECT id FROM guest WHERE reservation_id = ? AND archived_at IS NULL ORDER BY id", (reservation_id,)
    )
    db.execute(
        "UPDATE guest SET submit_state = ?, last_errors = ?, submit_attempts = 1 WHERE id = ?",
        (reporting.ERROR, "106: Nekorektní číslo cestovního dokladu", guest["id"]),
    )
    try:
        for width in (390, 768, 1280):
            with sync_api.sync_playwright() as playwright:
                browser = _launch(playwright)
                context, page = _open_app(browser, base, _cookie(dashboard_rich_host),
                                          f"/reservations/{reservation_id}", width)
                button = page.locator("a[data-fix-rejection]:visible").first
                assert button.count() == 1, width
                shot(page, f"fix-rejection-stay-{width}")
                button.click()
                page.wait_for_url(f"**/guests/{guest['id']}?return_to=/reservations/{reservation_id}")
                assert "Nekorektní číslo cestovního dokladu" in page.content()
                shot(page, f"fix-rejection-guest-{width}")
                context.close()
                browser.close()
    finally:
        db.execute(
            "UPDATE guest SET submit_state = ?, last_errors = NULL, submit_attempts = 0 WHERE id = ?",
            (reporting.PENDING, guest["id"]),
        )
