"""The Ctrl/Cmd K palette is styled on every host page (old and v2 shells).

command.css carries its look; v2 pages load only app2.css, so before it existed
the palette showed as a raw input and plain buttons there. Screenshots of the
open palette go to UBYHOST_SHOTS_DIR/command-palette (UX gate: look at them).
"""
from __future__ import annotations

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

SHOT_PAGES = ("dashboard", "cleaning", "settings-account")
CHECK = """() => {
  const d = document.getElementById('command-dialog');
  const input = d.querySelector('[data-command-input]');
  const opt = d.querySelector('.command-option');
  const dc = getComputedStyle(d), ic = getComputedStyle(input);
  return {
    open: d.open, width: d.getBoundingClientRect().width, vw: innerWidth,
    dialogBorder: parseFloat(dc.borderTopWidth), inputBorder: parseFloat(ic.borderTopWidth),
    optionBorder: opt ? parseFloat(getComputedStyle(opt).borderTopWidth) : 0,
    options: d.querySelectorAll('.command-option').length,
  };
}"""


def _out_dir() -> Path:
    base = os.environ.get("UBYHOST_SHOTS_DIR")
    return Path(base) / "command-palette" if base else Path("/tmp/ubyhost-command-palette")


def test_palette_is_styled_on_every_host_page(wide_host, wide_base):
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
    problems: list[str] = []
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception:
            if REQUIRE_BROWSER:
                raise
            pytest.skip("Chromium is required for the palette check")
        for width in (390, 768, 1280):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/"}])
            page = context.new_page()
            for name, path in routes.items():
                if width != 1280 and name not in SHOT_PAGES:
                    continue
                sep = "&" if "?" in path else "?"
                response = page.goto(f"{wide_base}{path}{sep}lang=en")
                if not response or response.status >= 400:
                    continue
                if not page.query_selector("#command-dialog"):
                    continue
                _wait_for_host_layout(page)
                _dismiss_optional_security_prompt(page)
                page.keyboard.press("Control+k")
                page.wait_for_selector("#command-dialog .command-option", timeout=5000)
                page.wait_for_timeout(300)
                got = page.evaluate(CHECK)
                if not (got["open"] and got["width"] <= min(641, got["vw"])
                        and got["dialogBorder"] >= 1 and got["inputBorder"] == 0
                        and got["optionBorder"] == 0 and got["options"] > 0):
                    problems.append(f"{name}/{width}: {got}")
                if name in SHOT_PAGES:
                    page.screenshot(path=str(out / f"palette-{name}-{width}.png"))
                page.evaluate("document.getElementById('command-dialog').close()")
            context.close()
    assert not problems, "\n".join(problems)
