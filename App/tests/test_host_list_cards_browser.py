"""0084 O2: list tables become compact labelled cards by panel width, never a sideways scroll.

Properties, Businesses, Invoices, Stay fees and Reports lists: at 760-1440 px,
rail expanded and collapsed, EN/CS, the list panel never scrolls sideways and
every row action sits inside the panel, visible without scrolling. The switch
follows the panel (container) width per list. At 1280 and 1440 px, rail
expanded or collapsed, EN/CS, every list is a table (long names included); at 760 px
every list is cards.

Screenshots: ``UBYHOST_CAPTURE_O2=1`` writes docs/tasks/0084-evidence/o2-*.png.
"""
from __future__ import annotations

import os
from pathlib import Path

from tests.browser_support import chromium_launch_kwargs
from tests.test_host_ux_acceptance import (  # noqa: F401  (fixtures and helpers)
    _context, _dismiss_prompt, _settle, _with_lang, acc, base, sync_api,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0084-evidence"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_O2") == "1"
LISTS = {
    "properties": "/apartments",
    "businesses": "/entities",
    "invoices": "/invoices",
    "fees": "/stay-fees",
}
# Per-list switch point (measured min-content width + ~40 px), in panel px.
THRESHOLDS = {"properties": 800, "businesses": 950, "invoices": 830, "fees": 940}

_LIST_JS = """() => {
  const panel = document.querySelector('.list-cards');
  if (!panel) return null;
  const pr = panel.getBoundingClientRect();
  const table = panel.querySelector('table');
  const cards = getComputedStyle(table.querySelector('thead')).display === 'none';
  const acts = [...panel.querySelectorAll('tbody td.row-actions a.btn, tbody td.row-actions .row-menu-trigger')]
    .filter(el => { const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1; })
    .map(el => { const r = el.getBoundingClientRect();
      return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, text: (el.textContent || '').trim().slice(0, 20)}; });
  const labels = [...panel.querySelectorAll('tbody tr:first-child td')].map(td => {
    const b = getComputedStyle(td, '::before'); return b.content;
  });
  const box = sel => { const el = document.querySelector(sel); if (!el) return null;
    const r = el.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom}; };
  const shown = sel => { const b = box(sel); return b && b.right > b.left ? b : null; };
  return {summary: box('#fee-list-summary'), filter: shown('#list-filter-panel') || shown('[data-filter-toolbar]'), panelTop: pr.top,
          scrollWidth: panel.scrollWidth, clientWidth: panel.clientWidth, panelLeft: pr.left, panelRight: pr.right,
          panelWidth: Math.round(pr.width), cards, acts, labels, rows: panel.querySelectorAll('tbody tr').length};
}"""


def test_list_panels_never_scroll_sideways_and_actions_stay_visible(acc, base):
    failures = []
    seen_cards = seen_table = 0
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        runs = [(lang, width, False) for lang in ("en", "cs") for width in (760, 1024, 1280, 1440)]
        runs += [(lang, width, True) for lang in ("en", "cs") for width in (1024, 1280, 1440)]
        for lang, width, collapsed in runs:
            context = _context(browser, base, acc["cookie"], width=width, height=900, collapsed=collapsed)
            page = context.new_page()
            for name, path in LISTS.items():
                page.goto(base + _with_lang(path, lang))
                _settle(page)
                _dismiss_prompt(page)
                result = page.evaluate(_LIST_JS)
                label = (name, lang, width, "collapsed" if collapsed else "expanded")
                if result is None:
                    failures.append((label, "no list panel"))
                    continue
                if result["scrollWidth"] > result["clientWidth"] + 1:
                    failures.append((label, "inner horizontal scroll", result["scrollWidth"], result["clientWidth"]))
                if result["cards"] != (result["panelWidth"] < THRESHOLDS[name]):
                    failures.append((label, "layout does not follow the panel width", result["panelWidth"], result["cards"]))
                if not result["acts"]:
                    failures.append((label, "no visible row action"))
                for act in result["acts"]:
                    if act["left"] < result["panelLeft"] - 1 or act["right"] > result["panelRight"] + 1:
                        failures.append((label, "action outside panel", act))
                    if act["right"] > width + 1:
                        failures.append((label, "action past viewport", act))
                if name == "fees":
                    # 0097: the month summary sits in the page lane, left-aligned
                    # with the filter row and the list panel, above the table.
                    summary, filt = result["summary"], result["filter"]
                    if not summary:
                        failures.append((label, "no fee summary line"))
                    else:
                        if abs(summary["left"] - result["panelLeft"]) > 1 or summary["right"] > result["panelRight"] + 1:
                            failures.append((label, "fee summary outside the content lane", summary, result["panelLeft"]))
                        if filt and abs(summary["left"] - filt["left"]) > 1:
                            failures.append((label, "fee summary not aligned with the filter row", summary, filt))
                        if summary["bottom"] > result["panelTop"] + 1:
                            failures.append((label, "fee summary not above the table", summary))
                if width >= 1280 and result["cards"]:
                    failures.append((label, "desktop width must keep the table", result["panelWidth"]))
                if width == 760 and not result["cards"]:
                    failures.append((label, "760 px must be cards", result["panelWidth"]))
                if result["cards"]:
                    seen_cards += 1
                    if not any(text not in ('none', 'normal', '""') for text in result["labels"]):
                        failures.append((label, "cards without labels", result["labels"]))
                else:
                    seen_table += 1
                if CAPTURE and not collapsed and width in (760, 1280):
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    page.evaluate("window.scrollTo(0, 0)")
                    page.screenshot(path=str(EVIDENCE / f"o2-{name}-{width}-{lang}.png"), full_page=True)
            context.close()
        browser.close()
    assert seen_cards and seen_table, (seen_cards, seen_table)
    assert not failures, failures
