"""0419: /admin/fakturace in a real browser at 390 and 1280 px, with one unpaid invoice."""
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

from app import billing, billing_invoices, config, db
from tests.browser_support import settle_motion

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0419"
TODAY = date.today()


def _fits(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_the_billing_admin_page_fits(calendar_workspace, calendar_origin, monkeypatch):
    owner = calendar_workspace["owner"]
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    db.execute("UPDATE user_account SET role = 'admin' WHERE id = ?", (owner,))
    billing.ensure_account(owner)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 3, buyer_name = 'Penzion Na Kopci s.r.o.', buyer_street = 'Hlavní 1', "
        "buyer_city = 'Brno', buyer_zip = '60200' WHERE owner_user_id = ?",
        (owner,),
    )
    invoice_id = billing_invoices.issue_for_period(owner, TODAY.isoformat(),
                                                   (TODAY + timedelta(days=29)).isoformat(), today=TODAY)
    number = billing_invoices.get(invoice_id)["number"]
    capture = os.environ.get("UBYHOST_CAPTURE_0419") == "1"
    try:
        with sync_api.sync_playwright() as playwright:
            browser = launch(playwright)
            for width in (390, 1280):
                context, page = open_page(browser, calendar_workspace, calendar_origin,
                                          width=width, locale="cs", touch=width < 768)
                page.goto(f"{calendar_origin}/admin/fakturace?lang=cs")
                settle_motion(page)
                page.evaluate("window.scrollTo(0, 0)")
                assert page.locator(f'[data-billing-admin-unpaid="{number}"]').count() == 1, width
                assert page.locator("[data-billing-admin-statement]").is_visible(), width
                assert _fits(page), width
                if capture and width == 390:
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(EVIDENCE / "admin-fakturace-390.png"), full_page=True)
                context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
        db.execute("UPDATE user_account SET role = 'host' WHERE id = ?", (owner,))
