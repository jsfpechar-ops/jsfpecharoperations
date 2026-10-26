"""0416: /predplatne in a real browser at 390 and 1280 px: order form, then the ordered plan."""
from __future__ import annotations

import os
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

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0416"


def _fits(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_the_plan_page_fits_and_works_without_scrolling_sideways(calendar_workspace, calendar_origin, monkeypatch):
    owner = calendar_workspace["owner"]
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    billing.ensure_account(owner)
    capture = os.environ.get("UBYHOST_CAPTURE_0416") == "1"
    try:
        with sync_api.sync_playwright() as playwright:
            browser = launch(playwright)
            for width in (390, 1280):
                db.execute("UPDATE billing_account SET status = 'trial_pending', plan = NULL, "
                           "billing_interval = NULL WHERE owner_user_id = ?", (owner,))
                context, page = open_page(browser, calendar_workspace, calendar_origin,
                                          width=width, locale="cs", touch=width < 768)
                page.goto(f"{calendar_origin}/predplatne?lang=cs&plan=max&interval=year")
                settle_motion(page)
                form = page.locator("[data-billing-order]")
                assert form.is_visible(), width
                assert page.locator('input[name="plan"][value="max"]').is_checked(), width
                assert page.locator("[data-billing-total]").inner_text().endswith("Kč"), width
                assert _fits(page), width
                if capture and width == 390:
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(EVIDENCE / "predplatne-order-390.png"), full_page=True)
                db.execute("UPDATE billing_account SET status = 'active', plan = 'standard', "
                           "billing_interval = 'month', apartments_billed = 3, period_end = '2099-01-31' "
                           "WHERE owner_user_id = ?", (owner,))
                page.reload()
                settle_motion(page)
                assert page.locator("[data-billing-order]").count() == 0, width
                assert page.get_by_text("Přejít na Max").is_visible(), width
                assert _fits(page), width
                if capture and width == 390:
                    page.screenshot(path=str(EVIDENCE / "predplatne-plan-390.png"), full_page=True)
                context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
