from __future__ import annotations

from pathlib import Path

from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_0710_v2_mockup_match_browser import _placeholders, base, dashboard_host, dashboard_rich_host  # noqa: F401
from tests.test_0830_airbnb_pages_browser import seeded  # noqa: F401

WIDTHS_0851 = ((390, 844), (768, 1024), (1280, 900))
SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0851"

_BOXES_JS = """() => {
    const box = el => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height, width: r.width};
    };
    const bar = document.querySelector('.property-settings-form .savebar');
    const discard = bar && bar.querySelector('[data-unsaved-reset]');
    const submit = bar && bar.querySelector('[type=submit]');
    const ghost = bar && bar.querySelector('a.btn.ghost');
    const visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    return {
        bar: box(bar),
        discard: box(discard), submit: box(submit),
        discardVisible: visible(discard), submitVisible: visible(submit),
        ghostHidden: !ghost || !visible(ghost),
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    };
}"""


def test_0851_savebar_is_one_row_with_quiet_discard_and_coral_save(base, dashboard_rich_host, seeded):  # noqa: F811
    from playwright import sync_api

    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    apartment_id = _placeholders(dashboard_rich_host)["first_property"]
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width, height in WIDTHS_0851:
            context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            page = context.new_page()
            page.goto(f"{base}/apartments/{apartment_id}?view=settings&lang=en")
            page.wait_for_load_state("networkidle")
            settle_motion(page)
            page.evaluate("() => { const s = document.querySelector('#sec-basics'); if (s && s.tagName === 'DETAILS') s.open = true; }")
            field = page.locator("#sec-basics input[type=text]").first
            field.fill((field.input_value() or "") + " x")
            m = page.evaluate(_BOXES_JS)
            d, s, b = m["discard"], m["submit"], m["bar"]
            if not (m["discardVisible"] and m["submitVisible"]):
                problems.append(f"{width}: discard or save not visible")
            if d is None or s is None or b is None:
                problems.append(f"{width}: savebar buttons missing")
            else:
                if abs(d["height"] - 48) > 1 or abs(s["height"] - 48) > 1:
                    problems.append(f"{width}: buttons not 48 px ({d['height']:.0f}, {s['height']:.0f})")
                if abs(d["top"] - s["top"]) > 1:
                    problems.append(f"{width}: buttons wrap onto two rows")
                if s["left"] - d["right"] < 12:
                    problems.append(f"{width}: buttons closer than 12 px")
                if not d["left"] < s["left"]:
                    problems.append(f"{width}: discard is not left of save")
                if s["right"] > m["innerWidth"] - 12:
                    problems.append(f"{width}: save button leaves the viewport")
                if b["bottom"] > m["innerHeight"] + 1:
                    problems.append(f"{width}: savebar is below the viewport")
            if m["scrollWidth"] > m["innerWidth"]:
                problems.append(f"{width}: horizontal page scroll")
            if not m["ghostHidden"]:
                problems.append(f"{width}: Cancel link still shown next to Discard")
            if width == 390:
                page.screenshot(path=str(SHOT_DIR / "property-savebar-390.png"), full_page=False)
            context.close()
        browser.close()
    assert not problems, "; ".join(problems)
