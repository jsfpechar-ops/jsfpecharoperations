"""1051: compact month filter on Stay fees list and detail (owner decision 2026-11-09).

Default is the current month; a grid pick or an arrow navigates without Apply; 390 px fits.
Screenshots: ``UBYHOST_CAPTURE_1051=1`` writes PNGs to $UBYHOST_SHOTS_DIR/stayfees-filter/.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from tests.browser_support import chromium_launch_kwargs
from tests.test_host_ux_acceptance import (  # noqa: F401  (fixtures and helpers)
    _context, _dismiss_prompt, _settle, acc, base, sync_api,
)

OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "stayfees-filter"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_1051") == "1"

_STATE_JS = """() => {
  const doc = document.documentElement;
  const form = document.querySelector('form.list-filter--compact');
  const box = el => el ? el.getBoundingClientRect() : null;
  const trigger = form && form.querySelector('[data-month-trigger]');
  const steps = form ? [...form.querySelectorAll('.month-step')].map(el => box(el).height) : [];
  const apply = form && form.querySelector('.filter-apply');
  const t = box(trigger);
  return {
    sideways: doc.scrollWidth > doc.clientWidth + 1,
    value: form ? form.querySelector('[data-month-native]').value : null,
    triggerHeight: t ? t.height : 0,
    triggerCentre: t ? Math.abs((t.left + t.width / 2) - (box(form).left + box(form).width / 2)) : 999,
    stepHeights: steps,
    applyVisible: !!(apply && apply.offsetParent),
    nextDisabled: !!(form && form.querySelector('[data-month-next]').disabled),
    toolbarToggle: !!document.querySelector('[data-filter-toggle][aria-controls="list-filter-panel"]:not([hidden])'),
  };
}"""


def _prev(key: str) -> str:
    year, month = int(key[:4]), int(key[5:7])
    return f"{year - 1}-12" if month == 1 else f"{year}-{month - 1:02d}"


def _open(browser, base, acc, path, width):
    context = _context(browser, base, acc["cookie"], width=width, height=900)
    page = context.new_page()
    page.goto(base + path)
    _settle(page)
    _dismiss_prompt(page)
    return context, page


def test_compact_month_filter_navigates_without_apply(acc, base):
    current = acc["month"]
    previous = _prev(current)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context, page = _open(browser, base, acc, "/stay-fees", 1280)
        state = page.evaluate(_STATE_JS)
        assert state["value"] == current, state  # default = current month
        assert state["nextDisabled"], state  # future months stay disabled
        assert not state["applyVisible"], state
        assert not state["toolbarToggle"], state
        assert state["triggerCentre"] < 2, state

        page.click("form.list-filter--compact [data-month-prev]")
        page.wait_for_url(re.compile(r"/stay-fees\?month=" + previous + r"$"))
        _settle(page)
        assert page.evaluate(_STATE_JS)["value"] == previous

        page.click("form.list-filter--compact [data-month-next]")
        page.wait_for_url(re.compile(r"/stay-fees\?month=" + current + r"$"))
        _settle(page)

        page.click("form.list-filter--compact [data-month-trigger]")
        panel = page.locator("form.list-filter--compact [data-month-grid-panel]")
        assert panel.is_visible()
        assert page.locator("form.list-filter--compact [data-month-choice]").count() == 12
        choice = page.locator("form.list-filter--compact [data-month-choice]:not([disabled]):not(.selected)").first
        target = choice.get_attribute("data-month-choice")
        choice.click()
        page.wait_for_url(re.compile(r"/stay-fees\?month=" + target + r"$"))
        _settle(page)
        assert page.evaluate(_STATE_JS)["value"] == target
        assert not page.locator("form.list-filter--compact [data-month-grid-panel]").is_visible()
        context.close()

        context, page = _open(browser, base, acc, f"/stay-fees/{acc['p1']}?month={current}", 1280)
        page.click("form.list-filter--compact [data-month-prev]")
        page.wait_for_url(re.compile(rf"/stay-fees/{acc['p1']}\?month={previous}$"))
        context.close()

        failures = []
        if CAPTURE:
            OUT.mkdir(parents=True, exist_ok=True)
        for name, path in (("list", "/stay-fees"), ("detail", f"/stay-fees/{acc['p1']}?month={current}")):
            for width in (390, 768, 1280):
                context, page = _open(browser, base, acc, path, width)
                state = page.evaluate(_STATE_JS)
                if state["sideways"]:
                    failures.append((name, width, "sideways scroll"))
                if width < 1024 and (state["triggerHeight"] < 44 or min(state["stepHeights"] or [0]) < 44):
                    failures.append((name, width, "touch target under 44 px", state))
                if state["applyVisible"]:
                    failures.append((name, width, "Apply visible with JS"))
                if CAPTURE:
                    page.screenshot(path=str(OUT / f"stayfees-{name}-{width}.png"), full_page=True)
                    if name == "list" and width == 390:
                        page.click("form.list-filter--compact [data-month-trigger]")
                        page.screenshot(path=str(OUT / "stayfees-list-390-grid-open.png"))
                context.close()
        browser.close()
    assert not failures, failures
