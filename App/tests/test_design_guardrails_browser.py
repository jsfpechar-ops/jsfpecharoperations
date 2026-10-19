"""Layout guard: MASTER 11.0 hard layout rules on every host page (0156)."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from fastapi.testclient import TestClient
from tests.conftest import login_as
from tests.browser_support import chromium_launch_kwargs
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures are re-created here)
    CAPTURE_ROUTES,
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

GUARD = (Path(__file__).parent / "design_guard.js").read_text()

ROUTES = {key: path for key, (path, _selector) in CAPTURE_ROUTES.items()}
ROUTES.update({
    "cleaning": "/cleaning",
    "guest-new": "/reservations/{reservation_id}/guests/new",
    "setup-property": "/apartments/{property_id}/setup/property",
    "setup-police": "/apartments/{property_id}/setup/police",
    "setup-guest-link": "/apartments/{property_id}/setup/guest_link",
    "setup-calendar": "/apartments/{property_id}/setup/calendar",
    "setup-stay-fee": "/apartments/{property_id}/setup/stay_fee",
    "setup-door-lock": "/apartments/{property_id}/setup/door_lock",
    "setup-automation": "/apartments/{property_id}/setup/automation",
    "setup-try-it": "/apartments/{property_id}/setup/try_it",
    "settings-account": "/settings",
})


def test_every_host_page_passes_the_layout_guard(wide_host, wide_base):
    cookie = wide_host["cookie"]
    routes = {
        key: path.format(
            invoice_id=wide_host["invoice"], entity_id=wide_host["entity"],
            reservation_id=wide_host["reservations"][0],
            submission_id=wide_host["submission"],
            property_id=wide_host["apartments"][0],
            unconfigured_apartment=wide_host["unconfigured_apartment"],
            configured_apartment=wide_host["configured_apartment"],
            today=wide_host["today"], housebook_end=wide_host["housebook_end"],
        )
        for key, path in ROUTES.items()
    }
    findings = []
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
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
                context.add_init_script(
                    "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}"
                    % ("1" if collapsed else "0")
                )
                page = context.new_page()
                for name, path in routes.items():
                    separator = "&" if "?" in path else "?"
                    response = page.goto(f"{wide_base}{path}{separator}lang=en")
                    assert response and response.status < 400, (
                        f"{name}/{width}/{state}: HTTP {response.status if response else 'none'}"
                    )
                    _wait_for_host_layout(page)
                    _dismiss_optional_security_prompt(page)
                    for finding in page.evaluate(GUARD, width < 1024):
                        findings.append((name, width, state, finding))
                    trigger = page.locator("button.row-menu-trigger:visible").first
                    if trigger.count():
                        trigger.click()
                        panel = page.locator(".row-menu-panel:visible").first
                        if panel.count():
                            box = panel.bounding_box()
                            doc_h = page.evaluate("document.documentElement.scrollHeight")
                            if box and (box["x"] < 0 or box["x"] + box["width"] > width
                                        or box["y"] + box["height"] > doc_h):
                                findings.append((name, width, state, ["menu-off-screen", box]))
                            if panel.locator("input:not([type=hidden]):not(.sr-only):visible, textarea:visible, select:visible").count():
                                findings.append((name, width, state, ["menu-holds-form"]))
                        page.keyboard.press("Escape")
                context.close()
        browser.close()
    report = os.environ.get("UBYHOST_GUARD_REPORT", "/tmp/ubyhost-layout-guard.json")
    Path(report).write_text(json.dumps(
        [{"route": r, "width": w, "sidebar": s, "finding": f} for r, w, s, f in findings], indent=1))
    counts = {}
    for _r, _w, _s, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    lines = [f"{r} {w} {s}: {f}" for r, w, s, f in findings[:40]]
    assert not findings, f"{len(findings)} layout findings {counts}\n" + "\n".join(lines)


def test_admin_pages_pass_the_layout_guard(wide_host, wide_base):
    username = f"guard-admin-{secrets.token_hex(4)}"
    admin_id = auth.create_account(f"{username}@example.test", "Guard Admin", role="admin", username=username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    assert cookie
    routes = {
        "admin-users": "/admin/users",
        "admin-users-manage": f"/admin/users?manage={wide_host['owner']}",
    }
    findings = []
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
                    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
                    context.add_init_script(
                        "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}"
                        % ("1" if collapsed else "0")
                    )
                    page = context.new_page()
                    for name, path in routes.items():
                        separator = "&" if "?" in path else "?"
                        response = page.goto(f"{wide_base}{path}{separator}lang=en")
                        assert response and response.status < 400, (
                            f"{name}/{width}/{state}: HTTP {response.status if response else 'none'}"
                        )
                        _wait_for_host_layout(page)
                        _dismiss_optional_security_prompt(page)
                        for finding in page.evaluate(GUARD, width < 1024):
                            findings.append((name, width, state, finding))
                        trigger = page.locator("button.row-menu-trigger:visible").first
                        if trigger.count():
                            trigger.click()
                            panel = page.locator(".row-menu-panel:visible").first
                            if panel.count():
                                box = panel.bounding_box()
                                doc_h = page.evaluate("document.documentElement.scrollHeight")
                                if box and (box["x"] < 0 or box["x"] + box["width"] > width
                                            or box["y"] + box["height"] > doc_h):
                                    findings.append((name, width, state, ["menu-off-screen", box]))
                                if panel.locator("input:not([type=hidden]):not(.sr-only):visible, textarea:visible, select:visible").count():
                                    findings.append((name, width, state, ["menu-holds-form"]))
                            page.keyboard.press("Escape")
                    context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM audit WHERE owner_user_id = ? OR actor_user_id = ?", (admin_id, admin_id))
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (admin_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (admin_id,))
    lines = [f"{r} {w} {s}: {f}" for r, w, s, f in findings[:40]]
    assert not findings, f"{len(findings)} admin layout findings\n" + "\n".join(lines)
