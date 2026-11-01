"""0710: every v2 page matches the approved mockup's styles and keeps its layout at every width."""
from __future__ import annotations

import os
from pathlib import Path

from app import auth
from tests.test_host_quiet_dashboard_browser import (  # the quiet overview's fixtures and helpers
    _launch,
    base,
    dashboard_host,
    dashboard_rich_host,
    sync_api,
)
from tests.v2_mockup import (
    COLOR_OVERRIDES,
    PAGES,
    STYLE_PROPS,
    WIDTHS,
    computed,
    geometry_findings,
    mockup_url,
    route_offline,
    same_value,
    show_view,
)

import pytest

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

CASES = [(spec, width) for spec in PAGES for width in WIDTHS]
IDS = [f"{spec['name']}-{width}" for spec, width in CASES]
SHOTS_DIR = Path(__file__).resolve().parents[2] / "docs/tasks/screenshots-0710"


def _open_app(browser, base_url, cookie, path, width):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base_url + "/"}])
    context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}")
    page = context.new_page()
    page.goto(f"{base_url}{path}?lang=en")
    page.wait_for_load_state("networkidle")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    page.evaluate("window.scrollTo(0, 0)")
    return context, page


def _open_mockup(browser, view, width):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    route_offline(page)
    page.goto(mockup_url())
    show_view(page, view)
    return context, page


@pytest.mark.parametrize("spec,width", CASES, ids=IDS)
def test_v2_page_matches_mockup_styles(spec, width, base, dashboard_rich_host):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    diffs = []
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        app_ctx, app_page = _open_app(browser, base, cookie, spec["path"], width)
        mock_ctx, mock_page = _open_mockup(browser, spec["view"], width)
        for selector in spec["selectors"]:
            mock_styles = computed(mock_page, selector)
            if mock_styles is None:
                diffs.append(f"{selector}: missing in mockup view {spec['view']}")
                continue
            app_styles = computed(app_page, selector)
            if app_styles is None:
                if selector not in spec["missing_ok"]:
                    diffs.append(f"{selector}: missing in app")
                continue
            for prop in STYLE_PROPS:
                app_value = app_styles[prop]
                mock_value = COLOR_OVERRIDES.get(mock_styles[prop], mock_styles[prop])
                if not same_value(prop, app_value, mock_value):
                    diffs.append(f"{selector} {prop}: app={app_value} mockup={mock_value}")
        app_ctx.close()
        mock_ctx.close()
        browser.close()
    assert not diffs, f"{spec['name']} at {width} px: {len(diffs)} style differences\n" + "\n".join(diffs)


@pytest.mark.parametrize("spec,width", CASES, ids=IDS)
def test_v2_page_geometry(spec, width, base, dashboard_rich_host):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, spec["path"], width)
        findings = geometry_findings(page, width)
        context.close()
        browser.close()
    assert not findings, f"{spec['name']} at {width} px: {len(findings)} findings\n" + "\n".join(findings)


def test_v2_screenshots(base, dashboard_rich_host):
    """Only when UBYHOST_SHOTS_V2=1: writes the report screenshots (returns early otherwise)."""
    if os.environ.get("UBYHOST_SHOTS_V2") != "1":
        return
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for spec in PAGES:
            for width in WIDTHS:
                context, page = _open_app(browser, base, cookie, spec["path"], width)
                page.screenshot(path=str(SHOTS_DIR / f"{spec['name']}-{width}.png"), full_page=True)
                context.close()
                mock_ctx, mock_page = _open_mockup(browser, spec["view"], width)
                mock_page.screenshot(path=str(SHOTS_DIR / f"mockup-{spec['view']}-{width}.png"), full_page=True)
                mock_ctx.close()
        browser.close()
