"""Cleaning calendar: two stays that overlap in a week with cleanings must both be drawn (not hidden behind "+1 more")."""

import os
import secrets
from pathlib import Path

import pytest

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_0705_v2_shell_browser import _sync_playwright
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0905"


def _seed():
    username = f"cs{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Cs", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Cs s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    now = db.utcnow()
    flats = []
    for name, start in (("Cozy flat", "2026-11-01"), ("Spacious flat", "2026-11-03")):
        flat = db.insert("apartment", {"internal_name": name, "owner_user_id": owner, "legal_entity_id": entity,
                                       "permalink_token": f"cs{secrets.token_hex(4)}", "active": 1,
                                       "created_at": now, "automation_mode": "manual"})
        db.insert("reservation", {"apartment_id": flat, "uid": secrets.token_hex(16), "source": "manual",
                                  "date_from": start, "date_to": "2026-11-08", "status": "active",
                                  "created_at": now, "updated_at": now})
        db.insert("cleaning_event", {"apartment_id": flat, "scheduled_date": "2026-11-08", "state": "scheduled",
                                     "created_at": now, "updated_at": now})
        flats.append(flat)
    return username


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_two_overlapping_stays_both_draw_in_a_week_with_cleanings(base, width):
    username = _seed()
    with _sync_playwright().sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
        page = context.new_page()
        page.goto(base + "/cleaning?lang=en&cal_date=2026-11-03")
        page.wait_for_selector(".cal-week")
        page.wait_for_timeout(500)
        week = page.locator(".cal-week", has=page.locator('[data-date="2026-11-08"]'))
        if width >= 768:  # phone tiles show every stay as a dot, not as pills
            # The week of 2-8 Nov holds both stays, drawn as two stacked pills, with no "+N" overflow button.
            names = week.locator(".cal-pill").all_inner_texts()
            assert sum("Cozy" in n for n in names) == 1 and sum("Spacious" in n for n in names) == 1, names
            assert week.locator(".cal-pill-more").count() == 0
        if os.environ.get("UBYHOST_TASK_SHOTS") == "1" and width in (390, 768, 1280):
            SHOTS.mkdir(parents=True, exist_ok=True)
            week.scroll_into_view_if_needed()
            page.screenshot(path=str(SHOTS / f"cleaning-{width}.png"), full_page=True)
        # The two pills do not overlap each other.
        if width < 768:  # phone tiles list stays in the day sheet, not as pills
            browser.close()
            return
        week.scroll_into_view_if_needed()
        a, b = [week.locator(".cal-pill").nth(i).bounding_box() for i in (0, 1)]
        assert a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"], (a, b)
        browser.close()
