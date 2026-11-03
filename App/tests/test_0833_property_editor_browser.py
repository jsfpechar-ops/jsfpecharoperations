"""0833: property editor help "?", single heading per section, no summary subtitles, wide fields."""
from __future__ import annotations

import os
from pathlib import Path

from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_0710_v2_mockup_match_browser import _placeholders, base, dashboard_host, dashboard_rich_host  # noqa: F401
from tests.test_0830_airbnb_pages_browser import seeded  # noqa: F401

WIDTHS_0833 = (390, 768, 1280)
SHOTS = os.environ.get("UBYHOST_SHOTS_0833")

_TAG_JS = """() => {
    const vis = e => e.getClientRects().length && !(e.closest('details:not([open])') && !e.closest('summary'));
        document.querySelectorAll(".property-settings-form .help-tip-btn").forEach(b => { if (vis(b)) b.setAttribute("data-vis0833", "1"); });
}"""

_HEADINGS_JS = """() => {
    const out = [];
    document.querySelectorAll('details.prop-sec[open]').forEach(sec => {
        const seen = new Map();
        sec.querySelectorAll('summary b, h2, h3').forEach(el => {
            if (!el.getClientRects().length) return;
            const t = el.textContent.trim();
            seen.set(t, (seen.get(t) || 0) + 1);
        });
        seen.forEach((n, t) => { if (n > 1) out.push(sec.id + ': ' + t); });
    });
    return out;
}"""

_ROWS_JS = """() => {
    const out = [];
    const vis = e => e.getClientRects().length && !(e.closest('details:not([open])') && !e.closest('summary'));
    const boxes = [...document.querySelectorAll('.property-settings-form .help-tip-btn')]
        .filter(vis);
    const inputs = [...document.querySelectorAll('.property-settings-form label, .property-settings-form input:not([type=hidden]), .property-settings-form select, .property-settings-form textarea, .property-settings-form h2, .property-settings-form h3, .property-settings-form summary b')]
        .filter(vis);
    for (const b of boxes) {
        const r = b.getBoundingClientRect();
        const row = b.closest('.field-label-row, .field');
        const lbl = row && row.querySelector('label, h2, h3, strong');
        if (lbl && vis(lbl)) {
            const range = document.createRange();
            range.selectNodeContents(lbl);
            if (lbl.contains(b)) range.setEndBefore(b.closest('.help-tip') || b);  // 0852: the macro may put the tip inside the label
            const lr = range.getBoundingClientRect();
            const mid = (x) => x.top + x.height / 2;
            out.push({kind: 'row', dy: Math.abs(mid(r) - mid(lr)), gap: r.left - lr.right});
        }
        for (const e of inputs) {
            if (e === b || b.contains(e) || e.contains(b)) continue;
            const er = e.getBoundingClientRect();
            const overlap = r.left < er.right && er.left < r.right && r.top < er.bottom && er.top < r.bottom;
            if (overlap) out.push({kind: 'overlap', tag: e.tagName + ' ' + e.className + ' ' + e.name + ' btn=' + [r.x, r.y, r.width, r.height].map(Math.round) + ' el=' + [er.x, er.y, er.width, er.height].map(Math.round) + ' bsec=' + (b.closest('details') || {}).id + ' esec=' + (e.closest('details') || {}).id + ' eopen=' + (e.closest('details') || {}).open + ' ebox=' + [e.getClientRects().length, getComputedStyle(e).position], text: (b.closest('.field') || {}).outerHTML ? b.closest('.field').outerHTML.slice(0, 300) : ''});
        }
    }
    return {count: boxes.length, rows: out};
}"""


def _open_settings(browser, base_url, cookie, apartment_id, width):
    from app import auth

    context = browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base_url + "/"}])
    page = context.new_page()
    page.goto(f"{base_url}/apartments/{apartment_id}?view=settings&lang=en")
    page.wait_for_load_state("networkidle")
    settle_motion(page)
    return context, page


def test_0833_property_editor_help_headings_and_width(base, dashboard_rich_host, seeded):  # noqa: F811
    from playwright import sync_api

    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    apartment_id = _placeholders(dashboard_rich_host)["first_property"]
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in WIDTHS_0833:
            context, page = _open_settings(browser, base, cookie, apartment_id, width)
            page.evaluate(_TAG_JS)
            buttons = page.locator(".property-settings-form .help-tip-btn[data-vis0833]")
            if buttons.count() == 0:
                problems.append(f"{width}: no visible help ? on the property editor")
            for i in range(buttons.count()):
                btn = buttons.nth(i)
                box = btn.bounding_box()
                if not 16 <= box["width"] <= 26 or not 16 <= box["height"] <= 26:
                    problems.append(f"{width}: ? #{i} is {box['width']:.0f}x{box['height']:.0f} px")
                radius = btn.evaluate("e => getComputedStyle(e).borderRadius")
                if radius not in ("50%", "9999px"):
                    problems.append(f"{width}: ? #{i} is not round ({radius})")
                body = btn.locator("xpath=following-sibling::*[contains(@class,'help-tip-body')][1]")
                if body.count() and body.first.is_visible():
                    problems.append(f"{width}: ? #{i} body is open before click")
                if body.count():
                    btn.click()
                    settle_motion(page)
                    if not body.first.is_visible():
                        problems.append(f"{width}: ? #{i} body does not open on click")
                    else:
                        bb = body.first.bounding_box()
                        vp = page.viewport_size
                        if bb["x"] < 0 or bb["x"] + bb["width"] > vp["width"] + 1:
                            problems.append(f"{width}: ? #{i} body leaves the viewport")
                    page.keyboard.press("Escape")
                    page.mouse.move(0, 0)
                    settle_motion(page)
            rows = page.evaluate(_ROWS_JS)
            for item in rows["rows"]:
                if item["kind"] == "row" and (item["dy"] > 10 or item["gap"] < 12):
                    problems.append(f"{width}: ? not on its label row (dy {item['dy']:.1f}, gap {item['gap']:.1f})")
                if item["kind"] == "overlap":
                    problems.append(f"{width}: ? overlaps {item['tag']} {item['text']!r}")
            dupes = page.evaluate(_HEADINGS_JS)
            if dupes:
                problems.append(f"{width}: duplicate headings {dupes}")
            if page.locator("details.prop-sec > summary > div > small:visible").count():
                problems.append(f"{width}: a summary subtitle is still visible")
            if width == 1280:
                input_width = page.locator("#internal_name").bounding_box()["width"]
                if input_width < 400:
                    problems.append(f"1280: first text input is {input_width:.0f} px wide")
            if SHOTS:
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(Path(SHOTS) / f"property-editor-{width}.png"), full_page=False)
            context.close()
        browser.close()
    assert not problems, problems
