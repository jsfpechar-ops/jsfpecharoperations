"""0414: the billing line on the dashboard, in a real browser at 390 and 1280 px."""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_dashboard_calendar_browser import (  # noqa: F401
    calendar_origin, calendar_workspace, launch, open_page,
)

from app import billing, config, db
from tests.browser_support import settle_motion

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0414"


def test_the_billing_line_shows_and_fits_a_phone(calendar_workspace, calendar_origin, monkeypatch):
    owner = calendar_workspace["owner"]
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    billing.ensure_account(owner)
    ends = (date.today() + timedelta(days=2)).isoformat()
    db.execute(
        "UPDATE billing_account SET status = 'trialing', trial_ends_at = ? WHERE owner_user_id = ?",
        (ends, owner),
    )
    capture = os.environ.get("UBYHOST_CAPTURE_0414") == "1"
    try:
        with sync_api.sync_playwright() as playwright:
            browser = launch(playwright)
            for width in (390, 1280):
                context, page = open_page(browser, calendar_workspace, calendar_origin,
                                          width=width, locale="cs", touch=width < 768)
                line = page.locator('[data-billing-banner="trial"]')
                assert line.is_visible(), width
                assert "Zkušební doba končí" in line.inner_text(), width
                assert line.locator('a[href="/predplatne"]').count() == 1, width
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), width
                if capture and width == 390:
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    settle_motion(page)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(EVIDENCE / "dashboard-390.png"))
                db.execute("UPDATE billing_account SET status = 'paused' WHERE owner_user_id = ?", (owner,))
                page.reload()
                assert page.locator('[data-billing-banner="paused"]').is_visible(), width
                db.execute("UPDATE billing_account SET status = 'trialing' WHERE owner_user_id = ?", (owner,))
                context.close()
            monkeypatch.setattr(config, "BILLING_ENABLED", False)
            context, page = open_page(browser, calendar_workspace, calendar_origin, width=390, locale="cs")
            assert page.locator("[data-billing-banner]").count() == 0
            context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
