"""0099: one shared list-page layout for Stays, Properties, Invoices and Stay fees.

Owner decision 2026-10-13. Every list page renders, in this DOM order:
notices (environment banner, setup banner), the title row (title left,
actions right, meta under them), the section's sub-page tabs (where the
section has sub-pages), the toolbar, then one list panel. Title, actions,
tabs and toolbar share one left edge and one vertical rhythm at 760, 1024,
1280 and 1440 px, rail expanded and collapsed, EN and CS. Tabs are plain
links with aria-current on the open page. Every list row, Dashboard stay rows
included, opens on click and on Enter; controls inside a row keep their own
action. Empty states use the shared component.

Screenshots: ``UBYHOST_CAPTURE_0099=1`` writes docs/tasks/0099-evidence/
<page>-<390|1280>-<en|cs>.png (synthetic data).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from app import host_i18n
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_ux_acceptance import (  # noqa: F401  (fixtures and helpers)
    _client, _context, _dismiss_prompt, _settle, _with_lang, acc, base, sync_api,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0099-evidence"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0099") == "1"
STRINGS = host_i18n.STRINGS
LISTS = {
    "stays": "/reservations?range=all",
    "properties": "/apartments",
    "invoices": "/invoices",
    "fees": "/stay-fees",
}
# The tab labels each list shows, in order (Stay fees has no sub-pages: fee
# settings live per property, so there is no one page to link).
TABS = {
    "stays": ["nav.stays", "tabs.stays.reports", "tabs.stays.register"],
    "properties": ["nav.properties", "host.business", "properties.shared.lock"],
    "invoices": ["nav.invoices", "host.invoice_settings"],
    "fees": [],
}
FILLED = ".btn.primary, .btn.accent, .btn.send-all, .ui-btn-primary"

_LAYOUT_JS = """(filled) => {
  const one = sel => document.querySelector(sel);
  const box = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height}; };
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const env = one('.env-banner');
  const notices = one('[data-list-notices]');
  const title = one('[data-list-title-row]');
  const h1 = title && title.querySelector('h1');
  const actions = one('[data-list-actions]');
  const meta = one('[data-list-meta]');
  const tabs = one('[data-sub-tabs]');
  const toolbar = one('[data-list-toolbar]');
  const panel = one('.stays-view, .list-cards, .ui-body-list');
  const order = [env, notices, title, tabs, toolbar, panel].filter(Boolean);
  let ordered = true;
  for (let i = 1; i < order.length; i++) {
    if (!(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING)) ordered = false;
  }
  const buttons = actions ? [...actions.querySelectorAll('.btn, .ui-btn')].filter(visible) : [];
  const tabLinks = tabs ? [...tabs.querySelectorAll('a')] : [];
  return {
    ordered, hasEnv: !!env, hasTitle: !!title, hasToolbar: !!toolbar, hasPanel: !!panel,
    title: box(title), h1: box(h1), actions: box(actions), meta: box(meta), tabs: box(tabs),
    firstTab: box(tabLinks[0]), toolbar: box(toolbar), panel: box(panel), notices: box(notices),
    tabTexts: tabLinks.map(a => a.textContent.trim()),
    current: tabLinks.filter(a => a.getAttribute('aria-current') === 'page').map(a => a.textContent.trim()),
    filled: buttons.filter(b => b.matches(filled)).length,
    heights: buttons.map(b => Math.round(b.getBoundingClientRect().height)),
    scroll: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth,
  };
}"""


def _near(a, b, tol=1.0):
    return abs(a - b) <= tol


def test_list_pages_share_order_edges_and_rhythm(acc, base):
    failures = []
    gaps = {"tabs": set(), "toolbar": set()}
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
                page.evaluate("window.scrollTo(0, 0)")
                r = page.evaluate(_LAYOUT_JS, FILLED)
                label = (name, lang, width, "collapsed" if collapsed else "expanded")
                if not (r["hasTitle"] and r["hasToolbar"] and r["hasPanel"]):
                    failures.append((label, "missing block", r["hasTitle"], r["hasToolbar"], r["hasPanel"]))
                    continue
                if not r["ordered"]:
                    failures.append((label, "DOM order is not notices, title, tabs, toolbar, panel"))
                if not r["hasEnv"]:
                    failures.append((label, "no environment notice in mock mode"))
                if r["scroll"] > r["vw"] + 1:
                    failures.append((label, "page wider than viewport", r["scroll"], r["vw"]))
                left = r["title"]["left"]
                edges = {"h1": r["h1"], "toolbar": r["toolbar"], "panel": r["panel"]}
                if r["notices"]:
                    edges["notices"] = r["notices"]
                expected = [STRINGS[lang][key] for key in TABS[name]]
                if expected:
                    edges["tabs"] = r["tabs"]
                    edges["first tab"] = r["firstTab"]
                    if r["tabTexts"] != expected:
                        failures.append((label, "tabs", r["tabTexts"], expected))
                    if r["current"] != [expected[0]]:
                        failures.append((label, "current tab", r["current"]))
                    gap = round(r["tabs"]["top"] - r["title"]["bottom"])
                    gaps["tabs"].add(gap)
                    gaps["toolbar"].add(round(r["toolbar"]["top"] - r["tabs"]["bottom"]))
                else:
                    if r["tabs"]:
                        failures.append((label, "unexpected tabs", r["tabTexts"]))
                    gaps["toolbar"].add(round(r["toolbar"]["top"] - r["title"]["bottom"]))
                for edge, b in edges.items():
                    if not b or not _near(b["left"], left):
                        failures.append((label, f"{edge} not on the title's left edge", b and b["left"], left))
                if r["actions"]:
                    if r["filled"] > 1:
                        failures.append((label, "more than one filled action", r["filled"]))
                    if r["heights"] and max(r["heights"]) - min(r["heights"]) > 1:
                        failures.append((label, "actions differ in height", r["heights"]))
                    # Right-aligned beside the title; at 760 px and below the
                    # shared header stacks, actions under the title on its edge.
                    if width > 760 and not _near(r["actions"]["right"], r["title"]["right"]):
                        failures.append((label, "actions not right-aligned", r["actions"]["right"], r["title"]["right"]))
                    if width <= 760 and not (_near(r["actions"]["left"], left) and r["actions"]["top"] >= r["h1"]["bottom"] - 1):
                        failures.append((label, "stacked actions not under the title", r["actions"], left))
                    if r["meta"] and r["meta"]["top"] < r["actions"]["bottom"] - 1:
                        failures.append((label, "meta not under the actions", r["meta"], r["actions"]))
                if CAPTURE and not collapsed and width == 1280:
                    _shot(page, name, width, lang)
            context.close()
        browser.close()
    # One vertical rhythm: the same gap above the tabs and above the toolbar
    # on every page, width, rail state and language.
    for kind, values in gaps.items():
        if values and max(values) - min(values) > 1:
            failures.append(("rhythm", kind, sorted(values)))
    assert not failures, failures


def _shot(page, name, width, lang):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(EVIDENCE / f"{name}-{width}-{lang}.png"), full_page=True)


def test_tabs_are_links_that_mark_the_open_page(acc):
    client = acc["client"]
    cases = [
        ("/reservations", "nav.stays"), ("/submissions", "tabs.stays.reports"),
        ("/housebook", "tabs.stays.register"), ("/apartments", "nav.properties"),
        ("/smart-locks", "properties.shared.lock"), ("/invoices", "nav.invoices"),
        (f"/entities?edit={acc['e1']}&next=/apartments", "host.business"),
        (f"/entities?edit={acc['e1']}&next=/invoices/new", "host.invoice_settings"),
    ]
    for path, key in cases:
        html = client.get(_with_lang(path, "en")).text
        nav = re.search(r'<nav class="(?:sub-tabs host-local-nav|ui-tabs)"[^>]*data-sub-tabs[^>]*>(.*?)</nav>', html, re.S)
        assert nav, path
        current = re.findall(r'<a class="(?:sub-tab|ui-tab)" href="[^"]+" aria-current="page">([^<]+)</a>', nav.group(1))
        assert current == [STRINGS["en"][key].replace("&", "&amp;")], (path, current)
        # Tabs sit directly under the title row, never above it.
        assert html.index("</h1>") < nav.start(), path
        assert "<button" not in nav.group(1) and "<form" not in nav.group(1), path
    # Two businesses: Business & legal details opens the list, never one record.
    assert re.search(r'<a class="(?:sub-tab|ui-tab)" href="/entities"', client.get("/apartments").text)
    # 0101: Invoice settings with two businesses opens the list to pick one.
    invoices = client.get("/invoices").text
    assert re.search(r'<a class="(?:sub-tab|ui-tab)" href="/entities"', invoices) and "/invoices/settings" not in invoices
    # Stay fees has no sub-pages (fee settings live in each property).
    assert "data-sub-tabs" not in client.get("/stay-fees").text
    # Property pages keep their own local tabs, not the section tabs.
    assert "data-sub-tabs" not in client.get(f"/apartments/{acc['p1']}").text


def test_empty_states_use_the_shared_component(acc):
    none = _client(acc["none"]["username"])
    for path in ("/reservations", "/apartments", "/stay-fees", "/invoices"):
        html = none.get(_with_lang(path, "en")).text
        assert html.count("data-empty-state") == 1, path
        block = html[html.index("data-empty-state"):]
        block = block[:block.index("\n  </div>")]
        assert len(re.findall(r'<a class="(?:btn|ui-btn)[^"]*"', block)) == 1, (path, block)
        assert "<p>" in block or "<h2>" in block, path
    filtered = acc["client"].get("/invoices?q=zzzz-no-such-invoice&lang=en").text
    assert filtered.count("data-empty-state") == 1
    assert STRINGS["en"]["filter.no_results"] in filtered


ROWS = {
    "dashboard": ("/", ".dashboard-row.clickable-row"),
    "stays": ("/reservations?range=all", ".stays-view tr.clickable-row"),
    "properties": ("/apartments", ".properties-table tr.clickable-row"),
    "property-summary": ("/apartments", ".property-summary-table tr.clickable-row"),
    "invoices": ("/invoices", ".lc-invoices tr.clickable-row"),
    "fees": ("/stay-fees", ".lc-fees tr.clickable-row"),
}

_SPOT_JS = """(sel) => {
  const row = document.querySelector(sel);
  if (!row) return null;
  row.scrollIntoView({block: 'center'});
  const r = row.getBoundingClientRect();
  const skip = 'a, button, input, select, textarea, label, form, summary, .row-menu, .row-actions, .dashboard-row-actions';
  for (let y = r.top + 6; y < r.bottom - 4; y += 6) {
    for (let x = r.left + 6; x < r.right - 6; x += 8) {
      const hit = document.elementFromPoint(x, y);
      if (hit && row.contains(hit) && !hit.closest(skip)) {
        return {x, y, href: row.getAttribute('data-href'), tab: row.tabIndex,
                ring: getComputedStyle(row).cursor};
      }
    }
  }
  return {x: null, href: row.getAttribute('data-href')};
}"""


def test_every_row_opens_on_click_and_enter_and_inner_controls_do_not(acc, base):
    failures = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _context(browser, base, acc["cookie"], width=1280, height=900)
        page = context.new_page()
        for name, (path, sel) in ROWS.items():
            page.goto(base + _with_lang(path, "en"))
            _settle(page)
            _dismiss_prompt(page)
            spot = page.evaluate(_SPOT_JS, sel)
            if not spot:
                failures.append((name, "no clickable row"))
                continue
            if spot.get("tab") != 0 or spot.get("ring") != "pointer":
                failures.append((name, "row not focusable or no pointer", spot))
            href = spot["href"]
            if spot["x"] is None:
                failures.append((name, "no plain spot in the row"))
            else:
                with page.expect_navigation():
                    page.mouse.click(spot["x"], spot["y"])
                if not page.url.endswith(href):
                    failures.append((name, "click opened", page.url, href))
            page.goto(base + _with_lang(path, "en"))
            _settle(page)
            _dismiss_prompt(page)
            row = page.locator(sel).first
            row.focus()
            outline = page.evaluate(
                "(sel) => { const s = getComputedStyle(document.querySelector(sel)); return s.outlineStyle + ' ' + s.outlineWidth; }",
                sel,
            )
            if outline.startswith("none") or outline.endswith(" 0px"):
                failures.append((name, "no focus ring", outline))
            with page.expect_navigation():
                page.keyboard.press("Enter")
            if not page.url.endswith(href):
                failures.append((name, "Enter opened", page.url, href))
            # A control inside the row keeps its own action.
            page.goto(base + _with_lang(path, "en"))
            _settle(page)
            _dismiss_prompt(page)
            before = page.url
            inner = page.locator(sel).first.locator(".row-menu-trigger, [data-copy]").first
            if inner.count():
                inner.click()
                page.wait_for_timeout(300)
                if page.url != before:
                    failures.append((name, "inner control navigated", page.url))
                page.keyboard.press("Escape")
            elif name not in ("invoices", "fees"):
                failures.append((name, "no inner control found"))
            if CAPTURE and name in ("dashboard",):
                for lang in ("en", "cs"):
                    for width in (390, 1280):
                        page.set_viewport_size({"width": width, "height": 900})
                        page.goto(base + _with_lang(path, lang))
                        _settle(page)
                        _dismiss_prompt(page)
                        _shot(page, name, width, lang)
                page.set_viewport_size({"width": 1280, "height": 900})
        context.close()
        browser.close()
    assert not failures, failures


def test_capture_list_pages_at_phone_width(acc, base):
    """Evidence only (UBYHOST_CAPTURE_0099=1): the four lists at 390 px, EN/CS."""
    if not CAPTURE:
        return
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _context(browser, base, acc["cookie"], width=390, height=844)
        page = context.new_page()
        for name, path in LISTS.items():
            for lang in ("en", "cs"):
                page.goto(base + _with_lang(path, lang))
                _settle(page)
                _dismiss_prompt(page)
                _shot(page, name, 390, lang)
        context.close()
        browser.close()
