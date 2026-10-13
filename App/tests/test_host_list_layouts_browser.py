"""0079: Dashboard and Stays rows share one Open + adjacent More action pair."""
from __future__ import annotations

import os
from pathlib import Path

from app import auth
from tests.test_host_quiet_dashboard_browser import (  # noqa: F401  (fixtures)
    base, dashboard_host, dashboard_rich_host, sync_api,
)
from tests.test_host_stay_actions_browser import (  # noqa: F401  (fixtures)
    _browser, stay_actions_base, stay_actions_host,
)

WIDTHS = (360, 390, 760, 1024, 1280, 1440)
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0079-evidence"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0079") == "1"
OPEN_LABEL = {"en": "Open", "cs": "Otevřít"}

PAIRS = """(selector) => [...document.querySelectorAll(selector)].map(row => {
  const open = [...row.querySelectorAll('a.btn')].find(
    a => !a.closest('.row-menu-panel') && (a.classList.contains('dashboard-open') || a.classList.contains('row-open')));
  const more = row.querySelector('.row-menu-trigger');
  const rect = el => { const r = el.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  const rr = row.getBoundingClientRect();
  return {open: open ? rect(open) : null, more: more ? rect(more) : null, openText: open ? open.textContent.trim() : '',
          row: {l: rr.left, r: rr.right}};
})"""


def _check_pairs(pairs, label, locale):
    assert len(pairs) >= 3, label
    for pair in pairs:
        assert pair["open"] and pair["more"], label
        assert pair["openText"] == OPEN_LABEL[locale], (label, pair["openText"])
        o, m = pair["open"], pair["more"]
        assert abs(o["h"] - m["h"]) <= 1, (label, o, m)
        assert abs(m["w"] - m["h"]) <= 1, (label, m)
        assert o["w"] >= 90, (label, o)
        assert m["l"] >= o["r"] - 1 and m["l"] - o["r"] <= 14, ("More not adjacent to Open", label, o, m)
        assert abs(o["t"] - m["t"]) <= 2, (label, o, m)
        assert o["l"] >= pair["row"]["l"] - 1 and m["r"] <= pair["row"]["r"] + 1, ("clipped", label, pair)


def test_dashboard_and_stays_share_open_more_pair(
    dashboard_rich_host, base, stay_actions_host, stay_actions_base,
):
    dash_cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    stay_cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    heights = {}
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        for locale in ("en", "cs"):
            for width in WIDTHS:
                for name, url, cookie, selector in (
                    ("dashboard", base, dash_cookie, ".dashboard-row"),
                    ("stays", stay_actions_base, stay_cookie, ".stays-view tbody tr"),
                ):
                    context = browser.new_context(viewport={"width": width, "height": 900})
                    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": url + "/"}])
                    page = context.new_page()
                    path = "/?" if name == "dashboard" else "/reservations?range=all&"
                    page.goto(f"{url}{path}lang={locale}")
                    page.wait_for_load_state("networkidle")
                    later = page.locator("#security-prompt [data-security-prompt-later]")
                    if later.is_visible():
                        later.click()
                    label = f"{name}/{locale}/{width}"
                    assert page.evaluate("document.documentElement.scrollWidth - innerWidth") <= 1, label
                    pairs = page.evaluate(PAIRS, selector)
                    _check_pairs(pairs, label, locale)
                    heights.setdefault((locale, width), {})[name] = round(pairs[0]["open"]["h"])
                    if CAPTURE and width in (360, 390, 1280, 1440):
                        EVIDENCE.mkdir(parents=True, exist_ok=True)
                        page.evaluate("window.scrollTo(0, 0)")
                        page.screenshot(path=str(EVIDENCE / f"{name}-{width}-{locale}.png"), full_page=True)
                    context.close()
        browser.close()
    for key, per_page in heights.items():
        assert per_page["dashboard"] == per_page["stays"], (key, per_page)
