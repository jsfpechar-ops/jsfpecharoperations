"""0203: pay steps on the fee list at 390, 1280 and 2000 px in en, cs, vi.

Screenshots: ``UBYHOST_CAPTURE_0203=1`` writes PNGs to $UBYHOST_SHOTS_DIR/stay-fee-steps/.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app import db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_ux_acceptance import (  # noqa: F401  (fixtures and helpers)
    _context, _dismiss_prompt, _settle, _with_lang, acc, base, sync_api,
)

OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "stay-fee-steps"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0203") == "1"

_CHECK_JS = """() => {
  const doc = document.documentElement;
  const steps = [...document.querySelectorAll('.fee-step')];
  return {sideways: doc.scrollWidth > doc.clientWidth + 1, steps: steps.length,
          primaries: Math.max(0, ...[...document.querySelectorAll('.fee-pay')].map(s => s.querySelectorAll('.ui-btn-primary').length))};
}"""


def test_pay_steps_fit_every_width_and_language(acc, base):
    failures = []
    if CAPTURE:
        OUT.mkdir(parents=True, exist_ok=True)
    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            for state in ("before", "after"):
                for lang in ("en", "cs", "vi"):
                    for width in (390, 1280, 2000):
                        context = _context(browser, base, acc["cookie"], width=width, height=900)
                        page = context.new_page()
                        page.goto(base + _with_lang("/stay-fees", lang))
                        _settle(page)
                        _dismiss_prompt(page)
                        if state == "after" and lang == "en" and width == 390:
                            button = page.locator(".fee-step form button.ui-btn-primary")
                            if button.count():
                                button.first.click()
                                _settle(page)
                        result = page.evaluate(_CHECK_JS)
                        label = (state, lang, width)
                        if result["sideways"]:
                            failures.append((label, "page scrolls sideways"))
                        if result["steps"] == 0:
                            failures.append((label, "no pay steps"))
                        if result["primaries"] > 1:
                            failures.append((label, "more than one primary"))
                        if CAPTURE:
                            page.screenshot(path=str(OUT / f"stay-fees-{state}-{lang}-{width}.png"), full_page=True)
                        context.close()
            browser.close()
    finally:
        db.execute("DELETE FROM stay_fee_filing WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (acc["owner"],))
    assert not failures, failures
