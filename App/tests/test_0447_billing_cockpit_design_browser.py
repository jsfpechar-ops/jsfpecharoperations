"""0447: rigorous geometry + design test for the changed billing pages.

/admin/fakturace (the cockpit) and /admin/customers/{id} (operator actions) with
rich data: every section populated, at 390/1280/2000 px, through the MASTER
layout guard (design_guard.js), plus per-section presence and no-JS form checks.
"""
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

from fastapi.testclient import TestClient

from app import auth, billing, billing_analytics, billing_invoices, config, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.conftest import login_as
from tests.test_design_guardrails_browser import GUARD
from tests.test_host_wide_geometry_browser import (  # noqa: F401  (fixtures)
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0447"
TODAY = date.today()
SECTIONS = (
    "revenue",
    "trend",
    "movement",
    "funnel",
    "discounts",
    "watch",
    "portfolio",
    "accounts",
)


def _seed_rich_billing(owner: int) -> None:
    """One paying customer with a discount, an open invoice, and history."""
    billing.ensure_account(owner)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'max', billing_interval = 'month', "
        "apartments_billed = 6, addon_ttlock = 1, buyer_name = 'Penzion Na Kopci s.r.o.', "
        "buyer_street = 'Hlavní 1', buyer_city = 'Brno', buyer_zip = '60200', "
        "buyer_ico = '27074358', period_start = ?, period_end = ? WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), owner),
    )
    billing.apply_discount(owner, 15, reason="Stálý zákazník", actor="operator:guard")
    billing_invoices.issue_for_period(
        owner, TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), today=TODAY)
    billing_analytics.write_month_snapshot()
    # last month's snapshot so movement has something to compare against
    prev = (TODAY.replace(day=1) - timedelta(days=1))
    db.execute(
        "INSERT INTO billing_month_snapshot (owner_user_id, month, status, plan, billing_interval, "
        "apartments, list_czk, net_czk, monthly_czk, created_at) VALUES (?, ?, 'active', 'standard', "
        "'month', 2, 298, 298, 298, ?)",
        (owner, f"{prev:%Y-%m}", db.utcnow()),
    )


def _cleanup(owner: int) -> None:
    db.execute("DELETE FROM bank_payment WHERE matched_invoice_id IN "
               "(SELECT id FROM platform_invoice WHERE owner_user_id = ?)", (owner,))
    db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM billing_month_snapshot WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
    db.execute("UPDATE user_account SET role = 'host' WHERE id = ?", (owner,))


def _fits(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


def test_the_cockpit_and_customer_pages_pass_the_layout_guard(wide_host, wide_base, monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    owner = wide_host["owner"]
    _seed_rich_billing(owner)
    username = f"guard-admin-{os.urandom(4).hex()}"
    admin_id = auth.create_account(f"{username}@example.test", "Guard Admin", role="admin",
                                   username=username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=cs", follow_redirects=False)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    routes = {
        "admin-fakturace": "/admin/fakturace",
        "admin-fakturace-search": "/admin/fakturace?q=Kopci&state=active",
        "admin-customer-actions": f"/admin/customers/{owner}",
    }
    findings = []
    capture = os.environ.get("UBYHOST_CAPTURE_0447") == "1"
    try:
        with sync_api.sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(**chromium_launch_kwargs())
            except Exception:
                if REQUIRE_BROWSER:
                    raise
                pytest.skip("Chromium is required for the layout guard")
            for width in (390, 1280, 2000):
                for collapsed in ((False, True) if width >= 1024 else (False,)):
                    state = "collapsed" if collapsed else "open"
                    context = browser.new_context(viewport={"width": width, "height": 1000})
                    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie,
                                          "url": wide_base + "/"}])
                    context.add_init_script(
                        "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}"
                        % ("1" if collapsed else "0"))
                    page = context.new_page()
                    for name, path in routes.items():
                        separator = "&" if "?" in path else "?"
                        response = page.goto(f"{wide_base}{path}{separator}lang=cs")
                        assert response and response.status < 400, (
                            f"{name}/{width}/{state}: HTTP {response.status if response else 'none'}")
                        _wait_for_host_layout(page)
                        _dismiss_optional_security_prompt(page)
                        for finding in page.evaluate(GUARD, width < 1024):
                            findings.append((name, width, state, finding))
                        assert _fits(page), f"{name}/{width}/{state} sideways overflow"
                        if capture and width == 390 and state == "open":
                            EVIDENCE.mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(EVIDENCE / f"{name}-390.png"), full_page=True)
                    context.close()
            browser.close()
    finally:
        _cleanup(owner)
        db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (admin_id,))
    lines = [f"{r} {w} {s}: {f}" for r, w, s, f in findings[:40]]
    counts: dict = {}
    for _r, _w, _s, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    assert not findings, f"{len(findings)} layout findings {counts}\n" + "\n".join(lines)


def test_every_cockpit_section_is_present_with_rich_data(wide_host, wide_base, monkeypatch):
    """The sections only render with data behind them; empty states hide bugs."""
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    owner = wide_host["owner"]
    _seed_rich_billing(owner)
    username = f"guard-admin-{os.urandom(4).hex()}"
    auth.create_account(f"{username}@example.test", "Guard Admin", role="admin", username=username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=cs", follow_redirects=False)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    try:
        with sync_api.sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(**chromium_launch_kwargs())
            except Exception:
                if REQUIRE_BROWSER:
                    raise
                pytest.skip("Chromium is required for cockpit section checks")
            for width in (390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE,
                                      "value": cookie, "url": wide_base + "/"}])
                page = context.new_page()
                page.goto(f"{wide_base}/admin/fakturace?lang=cs")
                settle_motion(page)
                for section in SECTIONS:
                    assert page.locator(f"#{section}").count() == 1, f"#{section} missing at {width}"
                assert page.locator("[data-billing-admin-portfolio]").count() >= 1, width
                assert page.locator("[data-billing-admin-discount]").count() == 1, width
                assert page.locator("[data-billing-admin-trend]").count() >= 1, width
                assert "data-billing-admin-watch=" in page.content(), width
                context.close()
            browser.close()
    finally:
        _cleanup(owner)


def test_the_operator_forms_work_without_javascript(wide_host, monkeypatch):
    """Rule 6: every operator action is a plain form post; JS only enhances."""
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    monkeypatch.setattr(config, "BILLING_IBAN", "CZ6503000000000123456789")
    owner = wide_host["owner"]
    username = f"nojs-admin-{os.urandom(4).hex()}"
    auth.create_account(f"{username}@example.test", "No-JS Admin", role="admin", username=username)
    billing.ensure_account(owner)
    db.execute(
        "UPDATE billing_account SET status = 'active', plan = 'standard', billing_interval = 'month', "
        "apartments_billed = 1, buyer_name = 'No-JS s.r.o.', period_start = ?, period_end = ? "
        "WHERE owner_user_id = ?",
        (TODAY.isoformat(), (TODAY + timedelta(days=29)).isoformat(), owner))
    client = TestClient(app)
    login_as(client, username, url="/login?lang=cs")
    try:
        detail = client.get(f"/admin/customers/{owner}")
        assert detail.status_code == 200 and "data-customer-discount" in detail.text
        for marker in ('name="percent"', 'name="reason"', 'name="field"', 'name="value"',
                       'name="status"', 'name="_csrf"'):
            assert marker in detail.text, f"missing form field {marker}"
        posted = client.post(f"/admin/customers/{owner}/sleva",
                             data={"percent": "10", "reason": "No-JS test"}, follow_redirects=False)
        assert posted.status_code == 303
        assert billing.account(owner)["discount_percent"] == 10
    finally:
        db.execute("DELETE FROM platform_invoice WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner,))
        db.execute("UPDATE user_account SET role = 'host' WHERE id = ?", (owner,))
