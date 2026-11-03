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

@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440, 1920], ids=lambda w: f"w{w}")
def test_fee_pay_step2_geometry(host, browser_base, width):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id); _finalize(client, apartment_id)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": browser_base}])
        page = context.new_page()
        page.goto(f"{browser_base}/stay-fees?month=2026-08&lang=en", wait_until="networkidle")
        failures = page.evaluate(CHECK_JS, f"fee-pay-{apartment_id}")
        if os.environ.get("UBYHOST_SHOTS_0896") == "1" and width in (390, 1280):
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"0896-stay-fees-pay-{width}.png"), full_page=True)
        browser.close()
    assert failures == [], failures
