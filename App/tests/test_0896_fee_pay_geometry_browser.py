"""0896: Stay fees step 2 (send the PDF and pay): geometry at seven widths."""
from __future__ import annotations
import os
from pathlib import Path
import pytest
from tests.test_stay_fee_send_panel import (  # noqa: F401  (fixtures and helpers)
    _finalize, _property, _stay, auth, browser_base, chromium_launch_kwargs, host, sync_api,
)
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0896"
CHECK_JS = """(id) => {
  const f = [], doc = document.documentElement, card = document.getElementById(id), r = e => e.getBoundingClientRect();
  if (doc.scrollWidth > doc.clientWidth + 1) f.push('page scrolls sideways');
  if (!card || card.dataset.feeStep !== '2') return f.concat('no step-2 card');
  const box = card.querySelector('.fee-send-pay'), vis = e => { const b = r(e); return b.width > 1 && b.height > 1 && !e.closest('.sr-only'); };
  if (r(box).width > 1000) f.push('content wider than 1000px: ' + r(box).width);
  const img = box.querySelector('.fee-qr-panel img'); if (!img) f.push('no QR'); else if (r(img).left < 0 || r(img).right > doc.clientWidth) f.push('QR outside viewport');
  [...box.querySelectorAll('.btn')].filter(vis).forEach(b => { if (r(b).height < 43.5) f.push('button under 44px: ' + b.textContent.trim()); });
  const red = [...card.querySelectorAll('.btn')].filter(vis).filter(b => getComputedStyle(b).backgroundColor === 'rgb(208, 69, 45)');
  if (red.length !== 1 || !(red[0].href || '').includes('mojedatovaschranka')) f.push('red buttons: ' + red.length);
  box.querySelectorAll('*').forEach(e => {
    if (!vis(e) || ![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    if (parseFloat(getComputedStyle(e).fontSize) < 14) f.push('text under 14px: ' + e.textContent.trim().slice(0, 30));
  });
  box.querySelectorAll('.fee-qr-val').forEach(e => { const cs = getComputedStyle(e), lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
    if (r(e).height >= 1.6 * lh) f.push('value wraps: ' + e.textContent.trim()); });
  const items = [...box.querySelectorAll('.fee-tasks > li, .fee-tasks strong, .btn, .fee-qr-panel > *, .fee-qr-meta > div, .fee-qr-meta dt, .fee-qr-val')].filter(vis);
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
    const a = items[i], b = items[j]; if (a.contains(b) || b.contains(a)) continue;
    if (a.matches('dt') && b.matches('.fee-qr-val') && a.parentElement === b.closest('div')) continue;  // label + value = one row
    const p = r(a), q = r(b), gap = Math.max(q.left - p.right, p.left - q.right, q.top - p.bottom, p.top - q.bottom);
    if (gap < 11.5) f.push('gap ' + gap.toFixed(1) + 'px: ' + (a.className || a.tagName) + ' / ' + (b.className || b.tagName));
  }
  return f;
}"""

TASKS_JS = """(id) => {
  const f = [], r = e => e.getBoundingClientRect(), W = window.innerWidth, card = document.getElementById(id);
  const lis = card ? [...card.querySelectorAll('.fee-tasks li')].filter(e => { const b = r(e); return b.width > 1 && b.height > 1; }) : [];
  if (!lis.length) return ['no visible .fee-tasks li'];
  lis.forEach((li, idx) => {
    const tag = 'task ' + idx + ' (' + li.textContent.trim().slice(0, 24) + '): ';
    const cs = getComputedStyle(li), lb = r(li), strong = li.querySelector('strong');
    if (!strong) { f.push(tag + 'no strong label'); return; }
    const sb = r(strong), scs = getComputedStyle(strong);
    let lh = parseFloat(scs.lineHeight); if (!(lh > 0)) lh = parseFloat(scs.fontSize) * 1.2;
    // (1) label not wrapped per word
    const probe = strong.cloneNode(true);
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;width:max-content;left:0;top:0;';
    li.appendChild(probe);
    const oneLine = r(probe).width;
    probe.remove();
    const avail = lb.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    const tooLongAt320 = W <= 320 && oneLine > sb.width;  // label sits in its grid column, narrower than the li
    if (!tooLongAt320 && sb.height >= 1.7 * lh) f.push(tag + 'label wraps per word: height ' + sb.height.toFixed(1) + ' vs line-height ' + lh.toFixed(1));
    if (W >= 390) {
      if (sb.width < 100) f.push(tag + 'label narrower than 100px: ' + sb.width.toFixed(1));
    }
    // (2) label on the same row as the number badge
    if (W >= 1280) {
      const dy = Math.abs((sb.top + sb.height / 2) - (lb.top + lb.height / 2));
      if (dy > 24) f.push(tag + 'label centre off li centre by ' + dy.toFixed(1) + 'px');
    } else if (W >= 1024) {
      const bb = r(li.querySelector('button, .btn') || li);
      if (sb.bottom > bb.top + 1 || bb.left < sb.left - 1) f.push(tag + 'label not above its button');
    } else if (sb.top - lb.top > 20) {
      f.push(tag + 'label top ' + (sb.top - lb.top).toFixed(1) + 'px below li top');
    }
    // (3) button width
    const btn = li.querySelector('button, .btn');
    if (!btn) { f.push(tag + 'no button in li'); }
    else {
      const bw = r(btn).width;
      if (W >= 1024) { if (bw > 280) f.push(tag + 'button wider than 280px: ' + bw.toFixed(1)); }
      else {
        const content = avail;
        if (Math.abs(bw - content) > 1) f.push(tag + 'button ' + bw.toFixed(1) + 'px vs li content ' + content.toFixed(1) + 'px');
      }
    }
    // (4) no stale or conflicting padding on li
    if (cs.paddingLeft !== '0px') f.push(tag + 'padding-left is ' + cs.paddingLeft);
  });
  return f;
}"""

@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440, 1920], ids=lambda w: f"w{w}")
def test_fee_pay_step2_geometry(host, browser_base, width, lang):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id); _finalize(client, apartment_id)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": browser_base}])
        page = context.new_page()
        page.goto(f"{browser_base}/stay-fees?month=2026-08&lang={lang}", wait_until="networkidle")
        failures = page.evaluate(CHECK_JS, f"fee-pay-{apartment_id}")
        failures += page.evaluate(TASKS_JS, f"fee-pay-{apartment_id}")
        if os.environ.get("UBYHOST_SHOTS_0896") == "1" and width in (390, 1280):
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"0896-stay-fees-pay-{width}.png"), full_page=True)
        browser.close()
    assert failures == [], failures
