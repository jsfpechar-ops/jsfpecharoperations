"""1053: Stay fee card rows: the rate input and the period select share one top line,
and every help "?" sits tight after its label text (1280 and 768 px); on wide screens the
whole property editor is one column centred beside the sidebar (1440 and 1800 px)."""
from __future__ import annotations

import os
from pathlib import Path

from app import config
from tests.property_host_fixture import host  # noqa: F401
from tests.test_property_navigation_browser import _context, base, chromium_launch_kwargs, sync_api  # noqa: F401

SHOTS = os.environ.get("UBYHOST_SHOTS_1053")

_FACTS = """() => {
  const sec = document.getElementById('sec-fee');
  const top = (el) => el ? Math.round(el.getBoundingClientRect().top) : null;
  const gaps = [];
  for (const btn of sec.querySelectorAll('.help-tip-btn')) {
    const r = btn.getBoundingClientRect();
    if (!r.width || !r.height || btn.closest('dialog')) continue;
    const wrap = btn.closest('.help-tip') || btn;
    const host = wrap.closest('label, legend') || wrap.parentElement;
    // the right edge of the label text that comes before the button
    const range = document.createRange();
    let textRight = null, textMid = null;
    const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (wrap.contains(n) || !n.textContent.trim()) continue;
      if (wrap.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_FOLLOWING) continue;
      range.selectNodeContents(n);
      const rects = [...range.getClientRects()].filter(x => x.width);
      if (!rects.length) continue;
      const last = rects[rects.length - 1];
      textRight = last.right; textMid = (last.top + last.bottom) / 2;
    }
    if (textRight === null) continue;
    gaps.push({id: btn.getAttribute('aria-controls') || host.textContent.trim().slice(0, 30),
               gap: Math.round(r.left - textRight), dy: Math.round((r.top + r.bottom) / 2 - textMid)});
  }
  const main = document.querySelector('main').getBoundingClientRect();
  const col = document.getElementById('property-settings-form').closest('.ui-body-detail').getBoundingClientRect();
  const glyphs = [...document.querySelectorAll('#stay-fee-settings .help-tip-btn')].filter(b => !b.querySelector('svg')).map(b => b.getAttribute('aria-controls'));
  return {glyphs, gapLeft: Math.round(col.left - main.left), gapRight: Math.round(main.right - col.right), rate: top(document.getElementById('stay_fee_rate_czk')), period: top(document.getElementById('stay_fee_cadence')),
          from: top(document.getElementById('stay_fee_rate_from')), gaps};
}"""


def test_stay_fee_rows_align_and_help_sits_after_label(host, base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        for width in (1280, 768, 390, 1440, 1800):
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(f"{base}/apartments/{host['apartment']}?view=settings&lang=en")
            page.locator('nav.prop-strip a[href="#sec-fee"]').click()
            page.wait_for_selector("#stay_fee_rate_czk", state="visible")
            page.evaluate("document.getElementById('stay_fee_collect').checked = true")
            facts = page.evaluate(_FACTS)
            if SHOTS:
                # a tall viewport keeps the fixed phone tab bar below the card
                page.set_viewport_size({"width": width, "height": 2600})
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                page.locator("#sec-fee").screenshot(path=str(Path(SHOTS) / f"stayfee-card-{width}.png"))
                if width >= 1440:
                    page.set_viewport_size({"width": width, "height": 1000})
                    page.screenshot(path=str(Path(SHOTS) / f"editor-page-{width}.png"))
                    page.set_viewport_size({"width": width, "height": 2600})
                page.evaluate("() => { for (const c of document.querySelectorAll('#sec-fee input[name=stay_fee_guest_rails]')) c.checked = true;"
                              " document.querySelector('#sec-fee details.fee-more').open = true; }")
                page.locator("#sec-fee").screenshot(path=str(Path(SHOTS) / f"stayfee-card-{width}-all-open.png"))
                page.evaluate("() => { for (const c of document.querySelectorAll('#sec-fee input[name=stay_fee_guest_rails]')) c.checked = false;"
                              " document.querySelector('#sec-fee details.fee-more').open = false; }")
                page.set_viewport_size({"width": width, "height": 1000})
            if facts["glyphs"]:
                problems.append((width, "help mark without the SVG icon", facts["glyphs"]))
            if width == 390:
                continue
            if width >= 1440 and abs(facts["gapLeft"] - facts["gapRight"]) > 24:
                problems.append((width, "editor column not centred", facts["gapLeft"], facts["gapRight"]))
            if facts["rate"] != facts["period"]:
                problems.append((width, "rate and period tops differ", facts["rate"], facts["period"]))
            for g in facts["gaps"]:
                if not 0 <= g["gap"] <= 12 or abs(g["dy"]) > 3:
                    problems.append((width, "help ? not tight after its label", g))
        browser.close()
    assert not problems, problems
