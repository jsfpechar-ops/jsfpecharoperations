"""0893: the three admin pages (home, customers, customer detail) keep the Airbnb geometry rules.

Checked at 320, 390, 768, 1024, 1280 and 1440 px, en:
1. body.v2, one visible h1 of at least 28 px, no horizontal overflow;
2. pill tabs are at least 44 px tall and 12 px apart, one current tab;
3. stat and value cards: 1 px border, radius of at least 12 px, text at least 16 px from the edge;
4. the round back button on the customer page is 40 px and sits above or left of the h1;
5. each "?" in a title sits on the title's last line;
6. no fine print, and every vertical or horizontal gap between neighbours is at least 12 px.
"""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as, mark_security_prompt_seen

sync_api = pytest.importorskip("playwright.sync_api")

WIDTHS = (320, 390, 768, 1024, 1280, 1440)
SHOT_WIDTHS = (390, 1280)
SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0893"

PAGE_NAMES = ("admin_home", "admin_customers", "admin_customer")

VISIBLE_JS = """
const vis = el => {
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0';
};
"""

FINE_PRINT_JS = VISIBLE_JS + """
() => {
  const out = [];
  const inTip = el => !!el.closest('.help-tip-body');
  const body = document.querySelector('.ui-body');
  if (body) {
    for (const el of body.querySelectorAll('*')) {
      if (inTip(el) || !vis(el)) continue;
      const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (!hasText) continue;
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < 14) out.push(`text ${fs}px ${el.tagName}.${el.className}: ${el.textContent.trim().slice(0, 40)}`);
    }
  }
  for (const el of document.querySelectorAll('p, small, .ui-sub')) {
    if (inTip(el) || !vis(el)) continue;
    const t = el.textContent.trim();
    if (t.length > 60) out.push(`fine print over 60 chars: ${t.slice(0, 40)}`);
  }
  const sel = 'h2, .ui-btn, .ui-input, label, .ui-sub, .ui-stat, .settings-value-card, .ui-tab';
  const els = [...document.querySelectorAll('.ui-page *')].filter(e =>
    e.matches(sel) && vis(e) && !inTip(e) && !e.closest('td, th'));
  for (let i = 0; i < els.length; i++) {
    for (let j = i + 1; j < els.length; j++) {
      const a = els[i], b = els[j];
      if (a.contains(b) || b.contains(a)) continue;
      const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
      const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
      const oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
      if (ox > 0 && oy > 0) continue;
      let gap = null;
      if (ox > 0) gap = ra.bottom <= rb.top ? rb.top - ra.bottom : ra.top - rb.bottom;
      else if (oy > 0) gap = ra.right <= rb.left ? rb.left - ra.right : ra.left - rb.right;
      if (gap !== null && gap >= 0 && gap < 11.5) {
        out.push(`gap ${gap.toFixed(1)}px: ${a.textContent.trim().slice(0, 25)} / ${b.textContent.trim().slice(0, 25)}`);
      }
    }
  }
  return out.slice(0, 20);
}
"""

GEOMETRY_JS = VISIBLE_JS + """
() => {
  const out = [];
  const h1s = [...document.querySelectorAll('h1')].filter(vis);
  if (h1s.length !== 1) out.push(`visible h1 count ${h1s.length}`);
  else if (parseFloat(getComputedStyle(h1s[0]).fontSize) < 28) out.push('h1 under 28px');
  if (document.documentElement.scrollWidth > document.documentElement.clientWidth) out.push('horizontal overflow ' + [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).slice(0, 3).map(e => e.tagName + '.' + e.className).join(' | '));
  if (!document.body.classList.contains('v2')) out.push('body is not v2');
  const navs = [...document.querySelectorAll('nav.ui-tabs')].filter(vis);
  if (navs.length === 0) out.push('no nav.ui-tabs');
  for (const nav of navs) {
    const tabs = [...nav.querySelectorAll('.ui-tab')].filter(vis);
    for (const t of tabs) {
      const r = t.getBoundingClientRect();
      if (r.height < 43.5) out.push(`tab ${r.height.toFixed(1)}px tall: ${t.textContent.trim()}`);
    }
    for (let i = 0; i + 1 < tabs.length; i++) {
      const a = tabs[i].getBoundingClientRect(), b = tabs[i + 1].getBoundingClientRect();
      const dx = Math.max(b.left - a.right, a.left - b.right);
      const dy = Math.max(b.top - a.bottom, a.top - b.bottom);
      const gap = Math.max(dx, dy);
      if (gap < 11.5) out.push(`tab gap ${gap.toFixed(1)}px`);
    }
  }
  const current = [...document.querySelectorAll('.ui-tab[aria-current="page"]')].filter(vis);
  if (navs.length && current.length !== 1) out.push(`aria-current count ${current.length}`);
  for (const card of [...document.querySelectorAll('.ui-stat, .settings-value-card')].filter(vis)) {
    const cs = getComputedStyle(card);
    if (cs.borderTopWidth !== '1px' || cs.borderLeftWidth !== '1px') out.push(`card border ${cs.borderTopWidth}`);
    if (parseFloat(cs.borderTopLeftRadius) < 12) out.push(`card radius ${cs.borderTopLeftRadius}`);
    const box = card.getBoundingClientRect();
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        const d = Math.min(r.left - box.left, box.right - r.right, r.top - box.top, box.bottom - r.bottom);
        if (d < 15.5) out.push(`card text ${d.toFixed(1)}px from edge: ${node.textContent.trim().slice(0, 30)}`);
      }
    }
  }
  for (const btn of document.querySelectorAll('h1 .help-tip-btn, h2 .help-tip-btn')) {
    if (!vis(btn)) continue;
    const h = btn.closest('h1, h2');
    const r = btn.getBoundingClientRect();
    const cy = r.top + r.height / 2;
    const w = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
    let last = null, n;
    while ((n = w.nextNode())) {
      if (!n.textContent.trim() || (n.parentElement && n.parentElement.closest('.help-tip-body'))) continue;
      const rr = document.createRange();
      rr.selectNodeContents(n);
      for (const q of rr.getClientRects()) { if (!last || q.bottom > last.bottom) last = q; }
    }
    if (last && (cy < last.top - 4 || cy > last.bottom + 4)) out.push(`help ? off the last line: ${h.tagName} cy=${cy.toFixed(1)} line=${last.top.toFixed(1)}-${last.bottom.toFixed(1)}`);
  }
  return out;
}
"""

BACK_JS = VISIBLE_JS + """
() => {
  const b = [...document.querySelectorAll('.ui-ph-back')].find(vis);
  const h1 = document.querySelector('.ui-ph h1');
  if (!b) return ['back button not visible'];
  const r = b.getBoundingClientRect();
  const out = [];
  if (Math.abs(r.width - 40) > 1 || Math.abs(r.height - 40) > 1) out.push(`back button ${r.width}x${r.height}`);
  if (h1) {
    const t = h1.getBoundingClientRect();
    if (!(r.bottom <= t.top + 1 || r.right <= t.left + 1)) out.push('back button overlaps h1');
  }
  return out;
}
"""


def fine_print_and_gap_findings(page):
    """Return the fine print and gap problems on the page (empty list when clean)."""
    return page.evaluate(FINE_PRINT_JS)


def shoot(page, name, width):
    """Save a full-page screenshot at 390 and 1280 px when UBYHOST_SHOTS_0893=1."""
    if os.environ.get("UBYHOST_SHOTS_0893") != "1" or width not in SHOT_WIDTHS:
        return
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / f"{name}-{width}.png"), full_page=True)


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"admin-0893-{secrets.token_hex(4)}"
    owner_id = mark_security_prompt_seen(auth.create_account(f"{username}@example.test", "Admin 0893", role="host", username=username))
    db.execute("UPDATE user_account SET role = 'admin' WHERE id = ?", (owner_id,))
    # the one-time security prompt (base.html) is not part of the admin look: mark it as already shown
    db.execute("UPDATE user_account SET two_factor_prompted_at = ? WHERE id = ?", (db.utcnow(), owner_id))
    customer_name = f"{username}-customer"
    customer = mark_security_prompt_seen(auth.create_account(f"{customer_name}@example.test", "Customer 0893", role="host", username=customer_name))
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "customer": customer}  # rows stay: other tests share the test DB


@pytest.fixture(scope="module")
def base(host):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the 0893 test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("name", PAGE_NAMES)
def test_admin_airbnb_geometry(host, base, name, width):
    paths = {
        "admin_home": "/admin",
        "admin_customers": "/admin/customers",
        "admin_customer": f"/admin/customers/{host['customer']}",
    }
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}{paths[name]}?lang=en")
        tag = f"{name} {width}"
        problems = [f"{tag}: {item}" for item in page.evaluate(GEOMETRY_JS)]
        problems += [f"{tag}: {item}" for item in fine_print_and_gap_findings(page)]
        if name == "admin_customer":
            problems += [f"{tag}: {item}" for item in page.evaluate(BACK_JS)]
        shoot(page, name, width)
        browser.close()
    assert not problems, "\n".join(problems)
