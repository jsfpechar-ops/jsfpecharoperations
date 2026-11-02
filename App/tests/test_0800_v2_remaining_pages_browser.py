"""0800: the remaining host pages (wizard, onboarding, new property, guest guide, help guide, Havel, cleaning
sub-pages) are on the v2 shell and keep their layout at every width (320/390/768/1024/1280/1440)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.test_0710_v2_mockup_match_browser import _launch, _open_app, _path, base, dashboard_host, dashboard_rich_host
from tests.v2_mockup import DESKTOP, WIDTHS, geometry_findings

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

# name -> path ({first_property} is the rich host's first property). One row per page; a brief owns its rows.
ROUTES = {
    "property-new": "/apartments/new",  # 0800
    "onboarding": "/onboarding",  # 0800
    "setup-property": "/apartments/{first_property}/setup/property",  # 0801
    "setup-calendar": "/apartments/{first_property}/setup/calendar",  # 0801
    "setup-police": "/apartments/{first_property}/setup/police",  # 0801
    "setup-guest-link": "/apartments/{first_property}/setup/guest_link",  # 0801
    "setup-stay-fee": "/apartments/{first_property}/setup/stay_fee",  # 0801
    "setup-done": "/apartments/{first_property}/setup/done",  # 0801
    "guest-guide": "/apartments/{first_property}/guide",  # 0802
    "guest-guide-quick": "/apartments/{first_property}/guide/quick",  # 0802
    "guide": "/guide",  # 0803
    "havel": "/havel",  # 0803
    "cleaning-new": "/cleaning/new",  # 0804
    "cleaning-shares": "/cleaning/shares",  # 0804
    "cleaning-properties": "/cleaning/properties",  # 0804
}
SHOTS_DIR = Path(__file__).resolve().parents[2] / "docs/tasks/screenshots-0800"  # UBYHOST_SHOTS_0800=1 writes one PNG per case
CASES = [(name, width) for name in ROUTES for width in WIDTHS]
IDS = [f"{name}-{width}" for name, width in CASES]

_SHELL_JS = """() => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  return {
    v2: document.body.classList.contains('v2'),
    h1: [...document.querySelectorAll('h1')].filter(visible).length,
    side: !!document.querySelector('.side') && visible(document.querySelector('.side')),
    tabs: !!document.querySelector('.tabs') && visible(document.querySelector('.tabs')),
  };
}"""


@pytest.mark.parametrize("name,width", CASES, ids=IDS)
def test_v2_remaining_page(name, width, base, dashboard_rich_host):
    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with _launch_ctx() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, _path({"path": ROUTES[name]}, dashboard_rich_host), width)
        shell = page.evaluate(_SHELL_JS)
        findings = geometry_findings(page, width)
        url = page.url
        if os.environ.get("UBYHOST_SHOTS_0800") == "1":
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS_DIR / f"{name}-{width}.png"), full_page=True)
        context.close()
        browser.close()
    problems = []
    if not shell["v2"]:
        problems.append("body is not on the v2 shell (set v2 = true in the template)")
    if shell["h1"] != 1:
        problems.append(f"{shell['h1']} visible h1 elements, expected exactly 1")
    if width >= DESKTOP and not shell["side"]:
        problems.append("no visible v2 sidebar (.side) from 1024 px")
    if width < DESKTOP and not (shell["tabs"] or shell["side"]):
        problems.append("no visible v2 navigation (.tabs or .side) below 1024 px")
    problems += findings
    assert not problems, f"{name} ({url}) at {width} px:\n" + "\n".join(problems)


def _launch_ctx():
    from tests.test_host_quiet_dashboard_browser import sync_api

    return sync_api.sync_playwright()
