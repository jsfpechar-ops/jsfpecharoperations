"""0894: admin billing and operations in the Airbnb pattern (geometry, fine print, gaps)."""

import os
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.test_0893_admin_airbnb_browser import (  # noqa: F401
    GEOMETRY_JS,
    base,
    chromium_launch_kwargs,
    fine_print_and_gap_findings,
    host,
)

WIDTHS = [320, 390, 768, 1024, 1280, 1440]
SHOT_WIDTHS = {390, 1280}
SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0894"
PAGES = {
    "admin_billing": "/admin/fakturace",
    "admin_operations": "/admin/operations",
}


def shoot(page, name, width):
    """Save a full-page screenshot at 390 and 1280 px when UBYHOST_SHOTS_0893=1."""
    if os.environ.get("UBYHOST_SHOTS_0893") != "1" or width not in SHOT_WIDTHS:
        return
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / f"0894-{name}-{width}.png"), full_page=True)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("name", list(PAGES))
def test_admin_billing_ops_geometry(host, base, name, width):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}{PAGES[name]}?lang=en")
        tag = f"{name} {width}"
        problems = [f"{tag}: {item}" for item in page.evaluate(GEOMETRY_JS)]
        problems += [f"{tag}: {item}" for item in fine_print_and_gap_findings(page)]
        shoot(page, name, width)
        browser.close()
    assert not problems, "\n".join(problems)
