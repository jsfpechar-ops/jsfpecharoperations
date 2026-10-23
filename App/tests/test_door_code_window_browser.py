"""Access disclosure: timing, progressive enhancement and measured design."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import auth, db, host_i18n, ttlock
from tests.test_property_navigation_browser import (  # noqa: F401
    base, chromium_launch_kwargs, host, sync_api,
)

expect = sync_api.expect

LANGS = ("en", "cs", "vi")
WIDTHS = (360, 390, 820, 1024, 1180, 1280)
NOTICE = "[data-door-code-window]:visible"


def _t(lang, key):
    return host_i18n.translate(lang, "door_code.window." + key)


@pytest.fixture(autouse=True)
def no_provider_calls(host, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Viewing access times must not contact TTLock")
    monkeypatch.setattr(ttlock, "_call", forbidden)
    monkeypatch.setattr(ttlock, "_post", forbidden)
    db.execute(
        "UPDATE apartment SET checkin_hour = 15, checkout_hour = 11 WHERE id = ?",
        (host["apartment"],),
    )


def _context(browser, base, host, width=390, js=True):
    context = browser.new_context(
        viewport={"width": width, "height": 1000},
        java_script_enabled=js, has_touch=820 <= width <= 1180,
    )
    context.add_cookies([{
        "name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE),
        "url": base + "/",
    }])
    return context


def _routes(host, lang):
    home = "/apartments/" + str(host["apartment"])
    return {
        "property-times": home + "?view=settings&section=property&lang=" + lang,
        "door-lock": home + "?view=settings&section=lock&lang=" + lang,
        "wizard-property": home + "/setup/property?lang=" + lang,
        "wizard-lock": home + "/setup/door_lock?lang=" + lang,
        "help": "/guide?lang=" + lang + "#door-codes",
    }


def _assert_times(page, lang, start="14:00", end="12:00", first_day="arrival", last_day="departure"):
    notice = page.locator(NOTICE)
    expect(notice).to_have_count(1)
    expect(notice.locator("[data-window-start]")).to_have_text(start + " · " + _t(lang, first_day))
    expect(notice.locator("[data-window-end]")).to_have_text(end + " · " + _t(lang, last_day))
    expect(notice.locator("[data-window-missing]")).to_be_hidden()
    return notice


def _geometry(notice):
    """Measure rendered text, containment, contrast and separation, not classes."""
    result = notice.evaluate("""el => {
      const box = el.getBoundingClientRect();
      const visible = node => node.getClientRects().length && getComputedStyle(node).display !== 'none';
      const nodes = [...el.querySelectorAll('p, dt, dd')].filter(visible);
      const overlap = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
      const rgba = color => (color.match(/[\\d.]+/g) || []).map(Number);
      const luminance = color => {
        const c = rgba(color).slice(0, 3).map(v => {
          v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
        });
        return c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722;
      };
      const contrast = node => {
        let parent = node, bg = 'rgb(255, 255, 255)';
        while (parent) {
          const candidate = getComputedStyle(parent).backgroundColor;
          const channels = rgba(candidate);
          if (channels.length === 3 || channels[3] === 1) { bg = candidate; break; }
          parent = parent.parentElement;
        }
        const fg = luminance(getComputedStyle(node).color), back = luminance(bg);
        return (Math.max(fg, back) + 0.05) / (Math.min(fg, back) + 0.05);
      };
      const rects = nodes.map(node => node.getBoundingClientRect());
      return {
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
        folded: !!el.closest('details, [role="tooltip"]'),
        clipped: nodes.some((node, i) =>
          node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1 ||
          rects[i].left < box.left - 1 || rects[i].right > box.right + 1 ||
          rects[i].top < box.top - 1 || rects[i].bottom > box.bottom + 1),
        overlapping: rects.some((a, i) => rects.slice(i + 1).some(b => overlap(a, b))),
        minContrast: Math.min(...nodes.map(contrast)),
        valueSizes: [...el.querySelectorAll('dd')].map(node => parseFloat(getComputedStyle(node).fontSize)),
        titleSize: parseFloat(getComputedStyle(el.querySelector('strong')).fontSize),
        decorativeBackground: getComputedStyle(el).backgroundColor,
        extraActions: el.querySelectorAll('button, a, input').length,
      };
    }""")
    assert not result["overflow"], result
    assert not result["folded"], result
    assert not result["clipped"], result
    assert not result["overlapping"], result
    assert result["minContrast"] >= 4.5, result
    assert result["titleSize"] >= 16, result
    assert all(size >= 15 for size in result["valueSizes"]), result
    assert result["decorativeBackground"] == "rgba(0, 0, 0, 0)", result
    assert result["extraActions"] == 0, result


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("lang", LANGS)
def test_disclosure_design_and_geometry_on_every_changed_page(host, base, engine, lang):
    with sync_api.sync_playwright() as playwright:
        launcher = getattr(playwright, engine)
        browser = launcher.launch(**(chromium_launch_kwargs() if engine == "chromium" else {}))
        for width in WIDTHS:
            context = _context(browser, base, host, width)
            page = context.new_page()
            for name, route in _routes(host, lang).items():
                response = page.goto(base + route)
                assert response and response.status == 200, (name, route)
                if name == "help":
                    section = page.locator("#door-codes")
                    expect(section.get_by_text(_t(lang, "example"), exact=True)).to_be_visible()
                    # Help remains one short explanation and one concrete example.
                    title = section.get_by_text(_t(lang, "title"), exact=True)
                    expect(title).to_be_visible()
                    assert title.evaluate("el => !el.closest('details')")
                    _geometry(section.locator("[data-door-code-disclosure]"))
                else:
                    _geometry(_assert_times(page, lang))
                shots = os.environ.get("UBYHOST_SHOTS_DIR")
                if shots and width == 390:
                    directory = Path(shots) / "door-code-access"
                    directory.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(directory / f"{engine}-{lang}-{name}.png"), full_page=True)
            context.close()
        browser.close()


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("lang", LANGS)
def test_live_preview_all_hours_missing_values_and_reflow(host, base, engine, lang):
    with sync_api.sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch(
            **(chromium_launch_kwargs() if engine == "chromium" else {})
        )
        context = _context(browser, base, host)
        page = context.new_page()
        for name in ("property-times", "wizard-property", "wizard-lock"):
            page.goto(base + _routes(host, lang)[name])
            _assert_times(page, lang)
            for hour in range(24):
                checkout = 23 - hour
                page.locator("#checkin_hour").select_option(str(hour))
                page.locator("#checkout_hour").select_option(str(checkout))
                _assert_times(
                    page, lang, f"{(hour - 1) % 24:02d}:00", f"{(checkout + 1) % 24:02d}:00",
                    "previous" if hour == 0 else "arrival",
                    "next" if checkout == 23 else "departure",
                )
            page.locator("#checkin_hour").select_option("")
            notice = page.locator(NOTICE)
            expect(notice.locator("[data-window-values]")).to_be_hidden()
            expect(notice.locator("[data-window-missing]")).to_be_visible()
            page.locator("#checkin_hour").select_option("15")
            page.locator("#checkout_hour").select_option("11")
            _assert_times(page, lang)
            # Larger user text must wrap without clipping or sideways scroll.
            page.add_style_tag(content="html { font-size: 200%; }")
            _geometry(page.locator(NOTICE))
        context.close()
        browser.close()


@pytest.mark.parametrize("connected", [False, True])
def test_disclosure_and_actual_hours_work_without_javascript_before_connecting(host, base, connected):
    if not connected:
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (host["owner"],))
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _context(browser, base, host, js=False)
        page = context.new_page()
        for name in ("door-lock", "wizard-lock"):
            page.goto(base + _routes(host, "en")[name])
            notice = _assert_times(page, "en")
            assert not notice.evaluate("el => !!el.closest('details')")
        context.close()
        browser.close()
