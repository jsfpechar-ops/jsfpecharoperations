"""0800: the remaining host pages (wizard, onboarding, new property, guest guide, help guide, Havel, cleaning
sub-pages) are on the v2 shell and keep their layout at every width (320/390/768/1024/1280/1440)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.test_0710_v2_mockup_match_browser import _launch, _open_app, _path, base, dashboard_host, dashboard_rich_host
from tests.v2_mockup import DESKTOP, WIDTHS, geometry_findings

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

# name -> path ({first_property} is the rich host's first property). One row per page; a brief owns its rows.
ROUTES = {
    "property-new": "/apartments/new",  # 0800
    "onboarding": "/onboarding",  # 0800
    "setup-property": "/apartments/{first_property}/setup/property",  # 0801
    "setup-calendar": "/apartments/{first_property}/setup/calendar",  # 0801
    "setup-police": "/apartments/{first_property}/setup/police",  # 0801
    "setup-guest-link": "/apartments/{first_property}/setup/guest_link",  # 0801
    "setup-stay-fee": "/apartments/{first_property}/setup/stay_fee",  # 0801
    "setup-done": "/apartments/{first_property}/setup/done",  # 0801
    "guest-guide": "/apartments/{first_property}/guide",  # 0802
    "guest-guide-quick": "/apartments/{first_property}/guide/quick",  # 0802
    "guide": "/guide",  # 0803
    "havel": "/havel",  # 0803
    "cleaning-new": "/cleaning/new",  # 0804
    "cleaning-shares": "/cleaning/shares",  # 0804
    "cleaning-properties": "/cleaning/properties",  # 0804
}
SHOTS_DIR = Path(__file__).resolve().parents[2] / "docs/tasks/screenshots-0800"  # UBYHOST_SHOTS_0800=1 writes one PNG per case
CASES = [(name, width) for name in ROUTES for width in WIDTHS]
IDS = [f"{name}-{width}" for name, width in CASES]

_SHELL_JS = """() => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  return {
    v2: document.body.classList.contains('v2'),
    h1: [...document.querySelectorAll('h1')].filter(visible).length,
    side: !!document.querySelector('.side') && visible(document.querySelector('.side')),
    tabs: !!document.querySelector('.tabs') && visible(document.querySelector('.tabs')),
  };
}"""


@pytest.mark.parametrize("name,width", CASES, ids=IDS)
def test_v2_remaining_page(name, width, base, dashboard_rich_host):
    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with _launch_ctx() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, _path({"path": ROUTES[name]}, dashboard_rich_host), width)
        shell = page.evaluate(_SHELL_JS)
        findings = geometry_findings(page, width)
        url = page.url
        if os.environ.get("UBYHOST_SHOTS_0800") == "1":
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS_DIR / f"{name}-{width}.png"), full_page=True)
        context.close()
        browser.close()
    problems = []
    if not shell["v2"]:
        problems.append("body is not on the v2 shell (set v2 = true in the template)")
    if shell["h1"] != 1:
        problems.append(f"{shell['h1']} visible h1 elements, expected exactly 1")
    if width >= DESKTOP and not shell["side"]:
        problems.append("no visible v2 sidebar (.side) from 1024 px")
    if width < DESKTOP and not (shell["tabs"] or shell["side"]):
        problems.append("no visible v2 navigation (.tabs or .side) below 1024 px")
    problems += findings
    assert not problems, f"{name} ({url}) at {width} px:\n" + "\n".join(problems)


def _launch_ctx():
    from tests.test_host_quiet_dashboard_browser import sync_api

    return sync_api.sync_playwright()


def _measure(name: str, width: int, base, host, script: str):
    """Open ROUTES[name] at width and return what script (a JS arrow function) computes."""
    from app import auth

    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with _launch_ctx() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, _path({"path": ROUTES[name]}, host), width)
        result = page.evaluate(script)
        context.close()
        browser.close()
    return result


# 0808 step a: a "?" that belongs to a field label sits on the label's line, after its text.
_HELP_TIP_JS = """() => {
  const out = [];
  for (const btn of document.querySelectorAll('.help-tip-btn')) {
    const tip = btn.closest('.help-tip');
    const box = tip && tip.parentElement;
    if (!box) continue;
    const label = [...box.children].find(el => el.tagName === 'LABEL') ||
      (tip.previousElementSibling && tip.previousElementSibling.tagName === 'LABEL' ? tip.previousElementSibling : null);
    const b = btn.getBoundingClientRect();
    if (!label || !b.width) continue;
    const rg = document.createRange();
    rg.selectNodeContents(label);
    const t = rg.getBoundingClientRect();
    if (!t.width) continue;
    out.push({label: label.textContent.trim().slice(0, 40), dy: Math.abs((t.top + t.bottom) / 2 - (b.top + b.bottom) / 2), dx: b.left - t.right});
  }
  return out;
}"""
HELP_TIP_ROUTES = ["property-new", "setup-property", "setup-calendar", "setup-stay-fee"]


@pytest.mark.parametrize("width", [390, 1280])
@pytest.mark.parametrize("name", HELP_TIP_ROUTES)
def test_help_tip_sits_beside_its_label(name, width, base, dashboard_rich_host):
    tips = _measure(name, width, base, dashboard_rich_host, _HELP_TIP_JS)
    assert tips, f"{name} at {width} px has no label with a help tip to check"
    bad = [t for t in tips if t["dy"] > 4 or t["dx"] < 0 or t["dx"] > 16]
    assert not bad, f"{name} at {width} px: help tip not beside its label: {bad}"


# 0808 step b: the onboarding card's action group stays on one line per control and 16 px from the text.
_ONBOARDING_GROUP_JS = """() => {
  const out = [];
  for (const step of document.querySelectorAll('.onboarding-step')) {
    const copy = step.querySelector('.onboarding-step-copy');
    const group = step.querySelector('.onboarding-step-group');
    if (!copy || !group) continue;
    const cr = copy.getBoundingClientRect(), gr = group.getBoundingClientRect();
    const kids = [...group.children].filter(k => k.getBoundingClientRect().width > 0);
    const summary = group.querySelector('summary');
    const rowGaps = [];
    for (let i = 0; i + 1 < kids.length; i++) {
      const a = kids[i].getBoundingClientRect(), c = kids[i + 1].getBoundingClientRect();
      if (Math.abs(a.top - c.top) < 4) rowGaps.push(c.left - a.right);
    }
    const below = gr.top >= cr.bottom - 1;
    out.push({
      summaryH: summary ? summary.getBoundingClientRect().height : 0,
      summaryLines: summary ? new Set([...(() => { const rg = document.createRange(); rg.selectNodeContents(summary); return rg.getClientRects(); })()].map(r => Math.round(r.top))).size : 0,
      summaryNowrap: summary ? getComputedStyle(summary).whiteSpace === 'nowrap' : false,
      rowGaps,
      textGap: below ? gr.top - cr.bottom : gr.left - cr.right,
    });
  }
  return out;
}"""


@pytest.mark.parametrize("width", [390, 1280])
def test_onboarding_step_actions_are_one_grouped_row(width, base, dashboard_rich_host):
    steps = _measure("onboarding", width, base, dashboard_rich_host, _ONBOARDING_GROUP_JS)
    assert steps, "no onboarding step card with an action group"
    problems = []
    for i, s in enumerate(steps):
        if s["summaryLines"] > 1:
            problems.append(f"step {i}: Learn why wraps onto {s['summaryLines']} lines")
        if s["summaryH"] and not s["summaryNowrap"]:
            problems.append(f"step {i}: Learn why may wrap (white-space is not nowrap)")
        problems += [f"step {i}: gap between controls {g:.0f} px (want 8-16)" for g in s["rowGaps"] if not 8 <= g <= 16]
        if s["textGap"] < 16:
            problems.append(f"step {i}: text to action group gap {s['textGap']:.0f} px (want >= 16)")
    assert not problems, f"onboarding at {width} px:\n" + "\n".join(problems)


# 0808 step c: no text touches the edge of a help card (16 px inside, 20-24 px at 1024 and up).
_GUIDE_PADDING_JS = """() => {
  const out = [];
  for (const card of document.querySelectorAll('.guide-section, .guide-page .ui-section')) {
    const c = card.getBoundingClientRect();
    if (!c.width) continue;
    for (const el of card.children) {
      if (!el.textContent.trim()) continue;
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      out.push({text: el.textContent.trim().slice(0, 30), left: r.left - c.left, right: c.right - r.right});
    }
  }
  return out;
}"""
GUIDE_PADDING_ROUTES = ["guide", "guest-guide"]


@pytest.mark.parametrize("width", [390, 1280])
@pytest.mark.parametrize("name", GUIDE_PADDING_ROUTES)
def test_help_card_text_has_inner_padding(name, width, base, dashboard_rich_host):
    kids = _measure(name, width, base, dashboard_rich_host, _GUIDE_PADDING_JS)
    assert kids, f"{name} at {width} px has no text in a card"
    bad = [k for k in kids if k["left"] < 16 or k["right"] < 16]
    assert not bad, f"{name} at {width} px: text closer than 16 px to its card edge: {bad[:5]}"


# 0808 step d: Havel is a chat column: one message per row, topic buttons a vertical list.
_HAVEL_JS = """() => {
  const msgs = [...document.querySelectorAll('.havel-thread > .havel-msg, .havel-thread .havel-msg')]
    .filter(m => m.getBoundingClientRect().width > 0)
    .map(m => { const r = m.getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; });
  const chips = [...document.querySelectorAll('.havel-topics .havel-chips > .havel-chip')]
    .map(c => { const r = c.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height}; });
  return {msgs, chips};
}"""


@pytest.mark.parametrize("width", [390, 1280])
def test_havel_is_a_stacked_chat_with_a_topic_list(width, base, dashboard_rich_host):
    data = _measure("havel", width, base, dashboard_rich_host, _HAVEL_JS)
    assert len(data["chips"]) >= 2, "Havel shows fewer than two topic buttons"
    problems = []
    xs = [c["x"] for c in data["chips"]]
    if max(xs) - min(xs) > 1:
        problems.append(f"topic buttons do not share one x: {xs}")
    for prev, nxt in zip(data["chips"], data["chips"][1:]):
        if nxt["y"] <= prev["y"]:
            problems.append("topic buttons are not stacked top to bottom")
    if any(c["w"] > 421 for c in data["chips"]):
        problems.append(f"topic button wider than 420 px: {[c['w'] for c in data['chips']]}")
    for prev, nxt in zip(data["msgs"], data["msgs"][1:]):
        if nxt["top"] < prev["bottom"] - 1:
            problems.append("two messages share a row")
    assert not problems, f"havel at {width} px:\n" + "\n".join(problems)
