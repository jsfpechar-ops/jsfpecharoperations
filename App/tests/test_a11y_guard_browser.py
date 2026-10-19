"""Accessibility guard: WCAG 2.2 AA checks on every host page, en and cs (0166)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_design_guardrails_browser import (  # noqa: F401  (fixtures and helpers are re-used here)
    ROUTES,
    REQUIRE_BROWSER,
    sync_api,
    wide_host,
    wide_base,
    _wait_for_host_layout,
    _dismiss_optional_security_prompt,
    chromium_launch_kwargs,
    auth,
)

A11Y = (Path(__file__).parent / "a11y_guard.js").read_text()
GUARD = (Path(__file__).parent / "design_guard.js").read_text()

REFLOW_RULES = {"text-clipped", "spills-out-of-row", "past-right-edge", "under-rail"}
SPACING_RULES = {"text-clipped", "spills-out-of-row", "page-scroll", "past-right-edge", "buttons-misaligned"}
SPACING_CSS = (
    "* { line-height: 1.5 !important; letter-spacing: 0.12em !important; "
    "word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }"
)

FOCUS_JS = """() => {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 30);
  const label = el.tagName.toLowerCase() + '#' + (el.id || '') + ':' + text;
  const visible = r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  if (!visible) return {label: label, visible: false};
  const outlineOk = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2;
  const shadowOk = cs.boxShadow !== 'none';
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  const obscured = !!hit && hit !== el && !el.contains(hit) && !hit.contains(el);
  return {label: label, visible: true, outlineStyle: cs.outlineStyle, outlineWidth: cs.outlineWidth,
          boxShadow: cs.boxShadow, notVisible: !outlineOk && !shadowOk, obscured: obscured};
}"""


def _routes(wide_host):
    return {
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


def test_every_page_passes_the_page_checks(wide_host, wide_base):
    cookie = wide_host["cookie"]
    routes = _routes(wide_host)
    findings = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the accessibility guard")
        for lang in ("en", "cs"):
            for width in (390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 1000})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
                context.add_init_script(
                    "try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}"
                )
                page = context.new_page()
                for name, path in routes.items():
                    separator = "&" if "?" in path else "?"
                    response = page.goto(f"{wide_base}{path}{separator}lang={lang}")
                    assert response and response.status < 400, (
                        f"{name}/{lang}/{width}: HTTP {response.status if response else 'none'}"
                    )
                    _wait_for_host_layout(page)
                    _dismiss_optional_security_prompt(page)
                    for finding in page.evaluate(A11Y, lang):
                        findings.append((name, lang, width, finding))
                context.close()
        browser.close()
    Path("/tmp/ubyhost-a11y-page.json").write_text(json.dumps(
        [{"route": r, "lang": l, "width": w, "finding": f} for r, l, w, f in findings], indent=1))
    counts = {}
    for _r, _l, _w, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    lines = [f"{r} {l} {w}: {f}" for r, l, w, f in findings]
    assert not findings, f"{len(findings)} findings {counts}\n" + "\n".join(lines[:40])


def test_keyboard_focus_is_visible_and_not_covered(wide_host, wide_base):
    cookie = wide_host["cookie"]
    routes = _routes(wide_host)
    findings = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the accessibility guard")
        context = browser.new_context(viewport={"width": 1280, "height": 1000})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        context.add_init_script(
            "try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}"
        )
        page = context.new_page()
        for name, path in routes.items():
            separator = "&" if "?" in path else "?"
            response = page.goto(f"{wide_base}{path}{separator}lang=en")
            assert response and response.status < 400, (
                f"{name}: HTTP {response.status if response else 'none'}"
            )
            _wait_for_host_layout(page)
            _dismiss_optional_security_prompt(page)
            for _ in range(40):
                page.keyboard.press("Tab")
                info = page.evaluate(FOCUS_JS)
                if info is None:
                    break
                if not info["visible"]:
                    continue
                if info["notVisible"]:
                    findings.append((name, 1280, ["focus-not-visible", info["label"]]))
                if info["obscured"]:
                    findings.append((name, 1280, ["focus-obscured", info["label"]]))
        context.close()
        browser.close()
    Path("/tmp/ubyhost-a11y-focus.json").write_text(json.dumps(
        [{"route": r, "width": w, "finding": f} for r, w, f in findings], indent=1))
    counts = {}
    for _r, _w, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    lines = [f"{r} {w}: {f}" for r, w, f in findings]
    assert not findings, f"{len(findings)} findings {counts}\n" + "\n".join(lines[:40])


def test_pages_reflow_at_320_and_200_percent(wide_host, wide_base):
    cookie = wide_host["cookie"]
    routes = _routes(wide_host)
    findings = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the accessibility guard")
        for width in (320, 640):
            context = browser.new_context(viewport={"width": width, "height": 1000})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
            context.add_init_script(
                "try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}"
            )
            page = context.new_page()
            for name, path in routes.items():
                separator = "&" if "?" in path else "?"
                response = page.goto(f"{wide_base}{path}{separator}lang=en")
                assert response and response.status < 400, (
                    f"{name}/{width}: HTTP {response.status if response else 'none'}"
                )
                _wait_for_host_layout(page)
                _dismiss_optional_security_prompt(page)
                scroll_width = page.evaluate("document.documentElement.scrollWidth")
                if scroll_width > width + 1:
                    findings.append((name, width, ["page-scroll", scroll_width, width]))
                for finding in page.evaluate(GUARD, width < 1024):
                    if finding[0] in REFLOW_RULES:
                        findings.append((name, width, finding))
            context.close()
        browser.close()
    Path("/tmp/ubyhost-a11y-reflow.json").write_text(json.dumps(
        [{"route": r, "width": w, "finding": f} for r, w, f in findings], indent=1))
    counts = {}
    for _r, _w, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    lines = [f"{r} {w}: {f}" for r, w, f in findings]
    assert not findings, f"{len(findings)} findings {counts}\n" + "\n".join(lines[:40])


def test_pages_survive_wide_text_spacing(wide_host, wide_base):
    cookie = wide_host["cookie"]
    routes = _routes(wide_host)
    findings = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the accessibility guard")
        for width in (1280, 390):
            context = browser.new_context(viewport={"width": width, "height": 1000})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
            context.add_init_script(
                "try { localStorage.setItem('ubyhost-sidebar-collapsed', '0'); } catch (e) {}"
            )
            page = context.new_page()
            for name, path in routes.items():
                separator = "&" if "?" in path else "?"
                response = page.goto(f"{wide_base}{path}{separator}lang=en")
                assert response and response.status < 400, (
                    f"{name}/{width}: HTTP {response.status if response else 'none'}"
                )
                _wait_for_host_layout(page)
                _dismiss_optional_security_prompt(page)
                page.add_style_tag(content=SPACING_CSS)
                page.wait_for_timeout(100)
                for finding in page.evaluate(GUARD, width < 1024):
                    if finding[0] in SPACING_RULES:
                        findings.append((name, width, finding))
            context.close()
        browser.close()
    Path("/tmp/ubyhost-a11y-spacing.json").write_text(json.dumps(
        [{"route": r, "width": w, "finding": f} for r, w, f in findings], indent=1))
    counts = {}
    for _r, _w, f in findings:
        counts[f[0]] = counts.get(f[0], 0) + 1
    lines = [f"{r} {w}: {f}" for r, w, f in findings]
    assert not findings, f"{len(findings)} findings {counts}\n" + "\n".join(lines[:40])
