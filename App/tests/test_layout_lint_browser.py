"""Layout lint (0900): every host page, seven widths, rules geometry tests miss.

Rules live in layout_lint.js: word-per-line wrapping, squeezed labels, stranded
badges, clipped or truncated text, overlapping text, elements outside the
viewport, empty buttons and boxes, stray duplicate icons, mixed stylesheets, and a help "?"
that is not on the same line as its heading or label (help-stranded).

Host pages must have zero findings. Guest and public pages are report-only.
Screenshots at 390/768/1280 of every host page go to UBYHOST_SHOTS_DIR/layout-lint
(CI uploads that folder as the browser-shots artifact), and the JSON report is
written next to them. Look at them: see AGENTS.md "UX gate".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from test_design_guardrails_browser import ROUTES
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures re-created here)
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

LINT = (Path(__file__).parent / "layout_lint.js").read_text()
WIDTHS = (320, 390, 768, 1024, 1280, 1440, 1920)
SHOT_WIDTHS = (390, 768, 1280)
# Report-only: guest and public pages are not changed by the UX passes.
PUBLIC_ROUTES = {
    "public-login": "/login",
    "public-pricing": "/pricing",
    "public-home": "/",
    "guest-form": "/g/{token}",
}
# Known findings the lint must not hide: every entry needs a reason and an owner decision.
ALLOW: dict[tuple[str, str], str] = {}


def _out_dir() -> Path:
    base = os.environ.get("UBYHOST_SHOTS_DIR")
    return Path(base) / "layout-lint" if base else Path("/tmp/ubyhost-layout-lint")


def test_every_host_page_passes_the_layout_lint(wide_host, wide_base):
    cookie = wide_host["cookie"]
    subst = dict(
        invoice_id=wide_host["invoice"], entity_id=wide_host["entity"],
        reservation_id=wide_host["reservations"][0], submission_id=wide_host["submission"],
        property_id=wide_host["apartments"][0],
        unconfigured_apartment=wide_host["unconfigured_apartment"],
        configured_apartment=wide_host["configured_apartment"],
        today=wide_host["today"], housebook_end=wide_host["housebook_end"],
    )
    routes = {key: path.format(**subst) for key, path in ROUTES.items()}
    out = _out_dir()
    out.mkdir(parents=True, exist_ok=True)
    findings: list[dict] = []
    report_only: list[dict] = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the layout lint")
        for width in WIDTHS:
            context = browser.new_context(viewport={"width": width, "height": 1000})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
            page = context.new_page()
            for name, path in routes.items():
                sep = "&" if "?" in path else "?"
                response = page.goto(f"{wide_base}{path}{sep}lang=en")
                assert response and response.status < 400, f"{name}/{width}: HTTP {response.status if response else 'none'}"
                _wait_for_host_layout(page)
                _dismiss_optional_security_prompt(page)
                page.evaluate("window.scrollTo(0, 0)")
                for item in page.evaluate(LINT):
                    if (name, item[0]) in ALLOW:
                        continue
                    findings.append({"route": name, "width": width, "finding": item})
                if width in SHOT_WIDTHS:
                    page.screenshot(path=str(out / f"{name}-{width}.png"), full_page=True)
            context.close()
        # Report-only crawl of guest and public pages (signed out).
        for width in (390, 1280):
            context = browser.new_context(viewport={"width": width, "height": 1000})
            page = context.new_page()
            for name, path in PUBLIC_ROUTES.items():
                if "{token}" in path:
                    continue
                response = page.goto(f"{wide_base}{path}?lang=en")
                if not response or response.status >= 400:
                    continue
                page.wait_for_load_state("load")
                for item in page.evaluate(LINT):
                    report_only.append({"route": name, "width": width, "finding": item})
            context.close()
        # Turbo moves between pages keep one stylesheet family in the head.
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": wide_base + "/"}])
        page = context.new_page()
        for name, path in routes.items():
            page.goto(f"{wide_base}/reservations?lang=en")
            _wait_for_host_layout(page)
            if not page.evaluate("typeof Turbo !== 'undefined'"):
                continue
            page.evaluate("(p) => Turbo.visit(p)", path)
            page.wait_for_timeout(700)
            _wait_for_host_layout(page)
            for item in page.evaluate(
                "() => { const n=[...document.querySelectorAll('link[rel=stylesheet]')].map(l=>(l.getAttribute('href')||'').split('?')[0].split('/').pop());"
                " const bad=[]; if (n.includes('app2.css') && n.includes('app.css')) bad.push(['mixed-stylesheets','head','after Turbo visit: app2.css and app.css together']); return bad; }"
            ):
                findings.append({"route": f"{name} (turbo)", "width": 1280, "finding": item})
        context.close()
        browser.close()
    (out / "layout-lint-report.json").write_text(json.dumps(
        {"host": findings, "report_only_public": report_only}, indent=1))
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["finding"][0]] = counts.get(f["finding"][0], 0) + 1
    unique: dict[str, list[str]] = {}
    for f in findings:
        unique.setdefault(json.dumps(f["finding"][:2]), []).append(f"{f['route']}@{f['width']}")
    lines = [f"{key} on {', '.join(pages[:4])}{' ...' if len(pages) > 4 else ''} ({len(pages)}x)"
             for key, pages in list(unique.items())[:60]]
    assert not findings, f"{len(findings)} layout-lint findings {counts}\n" + "\n".join(lines)


BAD_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<link rel=stylesheet href="/static/app2.css"><link rel=stylesheet href="/static/app.css">
<style>body{font:14px sans-serif;margin:0;width:390px}
.row{display:flex;gap:12px;align-items:center;width:360px}
.sq{width:56px}.btn{width:240px;height:36px}
.clip{display:inline-block;width:60px;overflow:hidden;white-space:nowrap}
.a{position:absolute;top:300px;left:10px}.b{position:absolute;top:304px;left:20px}
.badge{display:inline-block;width:20px}.wide{display:flex;gap:80px}</style></head><body>
<div class=row><span class=sq>Stay fee for the council</span><button class=btn>Confirm all ready</button></div>
<div class=wide><span class=badge>1</span><span>Send the report</span></div>
<span class=clip>CLOSED - 14 nights</span>
<button class=btn></button>
<p class=a>Overlapping name one</p><p class=b>Overlapping name two</p>
<div style="position:absolute;left:380px;top:200px">Past the edge text</div>
<div style="margin-top:420px;width:200px"><b>Guest form access</b></div>
<span class=help-tip><button class=help-tip-btn style="width:18px;height:18px;padding:0">?</button></span>
<div style="width:300px"><b>Inline label</b><span class=help-tip style="margin-left:6px"><button class=help-tip-btn style="width:18px;height:18px;padding:0">?</button></span></div>
<span id=icons><svg width=10 height=10><path d="M0 0h10v10z"/></svg><svg width=10 height=10><path d="M0 0h10v10z"/></svg></span>
</body></html>"""


def test_the_lint_catches_the_known_regressions(wide_base):
    """The lint must fail on the #748-style mistakes, or it protects nothing."""
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the layout lint")
        page = browser.new_page(viewport={"width": 390, "height": 800})
        page.goto(wide_base + "/healthz")
        page.set_content(BAD_PAGE)
        found = page.evaluate(LINT)
        rules = {item[0] for item in found}
        stranded = [item for item in found if item[0] == "help-stranded"]
        browser.close()
    expected = {"word-per-line", "label-squeezed", "badge-stranded", "clipped-text",
                "text-overlap", "outside-viewport", "empty-control", "duplicate-icon", "help-stranded"}
    assert expected <= rules, f"lint missed {sorted(expected - rules)}; saw {sorted(rules)}"
    # The "?" under its heading is caught; the one right after its label is not.
    assert len(stranded) == 1 and "Guest form access" not in stranded[0][1], stranded
