"""0786: the settings area pages keep Josef's phone geometry rules at 390 and 1280 px, en and cs.

1. a help ? sits on the same line as the heading or label it belongs to;
2. every visible text block in a card keeps 16 px from the card edge;
3. a button and the text after it do not share a line (8 px gap);
4. entity row actions and the row menu share one vertical centre.
"""
from __future__ import annotations

import secrets
import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

sync_api = pytest.importorskip("playwright.sync_api")

PAGES = ("/settings", "/entities", "/privacy-requests", "/settings/archived")
WIDTHS = (320, 390, 1280)
LANGS = ("en", "cs")

# text nodes inside a card: the text rectangle, not the box, so table cells and buttons count by their text
CARD_TEXT_JS = """
() => {
  const out = [];
  for (const card of document.querySelectorAll('.card')) {
    const cr = card.getBoundingClientRect();
    if (!cr.width) continue;
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent.trim()) continue;
      const el = node.parentElement;
      if (!el || el.closest('.help-tip-body, script, style, summary, .ui-table-stack td::before')) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
      if (!rects.length) continue;
      const left = Math.min(...rects.map(r => r.left));
      out.push({text: node.textContent.trim().slice(0, 40), left, cardLeft: cr.left});
    }
  }
  return out;
}
"""

HELP_JS = """
() => {
  const out = [];
  for (const btn of document.querySelectorAll('.help-tip-btn')) {
    if (!btn.getClientRects().length) continue;
    const tip = btn.closest('.help-tip');
    let anchor = null;
    const prev = tip.previousElementSibling;
    if (prev && /^(H[1-6]|LABEL|STRONG)$/.test(prev.tagName)) anchor = prev;
    const parent = tip.parentElement;
    if (!anchor && parent && parent.matches('h1,h2,h3,h4,h5,h6,label,strong')) anchor = parent;
    if (!anchor && parent && parent.matches('.heading-with-tip')) anchor = parent.querySelector('h1,h2,h3,h4,h5,h6');
    if (!anchor) continue;
    const a = anchor.getBoundingClientRect(), b = btn.getBoundingClientRect();
    const walker = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT);
    let last = null, node;
    while ((node = walker.nextNode())) { if (node.textContent.trim() && !node.parentElement.closest('.help-tip')) last = node; }
    let lastTop = a.top, lastBottom = a.bottom;
    if (last) {
      const rr = document.createRange();
      rr.selectNodeContents(last);
      const rs = [...rr.getClientRects()].filter(r => r.height > 0);
      if (rs.length) { lastTop = rs[rs.length - 1].top; lastBottom = rs[rs.length - 1].bottom; }
    }
    out.push({label: anchor.textContent.trim().slice(0, 40), sameLine: b.top < a.bottom && b.bottom > a.top, lastLine: b.top >= lastTop - 6 && b.top <= lastBottom});
  }
  return out;
}
"""

BUTTON_TEXT_JS = """
() => {
  const out = [];
  for (const btn of document.querySelectorAll('button:not(.help-tip-btn), .ui-btn')) {
    if (!btn.getClientRects().length || btn.closest('.help-tip-body')) continue;
    const next = btn.nextElementSibling;
    if (!next || /^(BUTTON|A|INPUT|SELECT|FORM|DETAILS)$/.test(next.tagName) || next.matches('.help-tip, .row-menu, details')) continue;
    const walker = document.createTreeWalker(next, NodeFilter.SHOW_TEXT);
    let node, text = null;
    while ((node = walker.nextNode())) { if (node.textContent.trim() && node.parentElement === next) { text = node; break; } }
    if (!text) continue;
    const range = document.createRange();
    range.selectNodeContents(text);
    const r = [...range.getClientRects()].filter(x => x.width > 0);
    if (!r.length) continue;
    const b = btn.getBoundingClientRect();
    const top = Math.min(...r.map(x => x.top));
    if (top >= b.top && top < b.bottom + 8) out.push({button: btn.textContent.trim().slice(0, 30), text: text.textContent.trim().slice(0, 40), gap: top - b.bottom});
  }
  return out;
}
"""

ROW_JS = """
() => {
  const out = [];
  for (const cell of document.querySelectorAll('.row-actions')) {
    if (!cell.getClientRects().length) continue;
    const items = [...cell.querySelectorAll('a.ui-btn, button.ui-btn, .row-menu > summary, .row-menu-btn, summary.ui-btn')].filter(e => e.getClientRects().length);
    if (items.length < 2) continue;
    const centres = items.map(e => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; });
    out.push({spread: Math.max(...centres) - Math.min(...centres), detail: items.map(e => e.className + ' ' + Math.round(e.getBoundingClientRect().height) + 'px').join(' | ')});
  }
  return out;
}
"""


# static sentences longer than 60 characters: only help popovers, table/list values, status/alert text and controls may hold them
LONG_TEXT_JS = """
() => {
  const out = [];
  const root = document.querySelector('main') || document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.trim();
    if (text.length <= 60) continue;
    const el = node.parentElement;
    if (!el || !el.getClientRects().length) continue;
    if (el.closest('.help-tip-body, .help-tip, .ui-empty, script, style, summary, td, th, dd, dt, .kv, .ui-table-stack, pre, code, button, a, label, select, textarea, option, input, [role=alert], [role=status], .alert, .flash, .err-text, .ui-btn')) continue;
    out.push(text.slice(0, 60));
  }
  return out;
}
"""


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"geometry-0786-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Geometry 0786", role="host", username=username)
    entity = db.insert("legal_entity", {
        "name": "Geometry s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "entity": entity}  # rows stay: other tests share the test DB


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
        pytest.fail("the 0786 test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("width", WIDTHS)
def test_settings_area_geometry_rules(host, base, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in LANGS:
            context = browser.new_context(viewport={"width": width, "height": 900})
            cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            for path in PAGES:
                page = context.new_page()
                sep = "&" if "?" in path else "?"
                page.goto(f"{base}{path}{sep}lang={lang}" if "entities" not in path else f"{base}{path}?edit={host['entity']}&lang={lang}")
                tag = f"{path} {lang} {width}"
                for item in page.evaluate(HELP_JS):
                    if not item["sameLine"] or not item["lastLine"]:
                        problems.append(f"{tag}: help ? not on the last heading line: {item['label']}")
                for item in page.evaluate(CARD_TEXT_JS):
                    if item["left"] < item["cardLeft"] + 16 - 0.5:
                        problems.append(f"{tag}: card text at the edge: {item['text']}")
                for item in page.evaluate(BUTTON_TEXT_JS):
                    problems.append(f"{tag}: text beside a button: {item['button']} / {item['text']}")
                for item in page.evaluate(ROW_JS):
                    if item["spread"] > 1:
                        problems.append(f"{tag}: row actions not on one centre line ({item['spread']:.1f} px) {item['detail']}")
                for text in page.evaluate(LONG_TEXT_JS):
                    problems.append(f"{tag}: static text outside the help tip: {text}")
                page.close()
            context.close()
        browser.close()
    assert not problems, "\n".join(problems[:40])


# 0787e: the help ? sits 8 px after the last word of its heading or label, not at the far right of the row
HELP_GAP_JS = """
() => {
  const out = [];
  for (const btn of document.querySelectorAll('.help-tip-btn')) {
    if (!btn.getClientRects().length) continue;
    const tip = btn.closest('.help-tip');
    let anchor = null;
    const prev = tip.previousElementSibling;
    if (prev && /^(H[1-6]|LABEL|STRONG)$/.test(prev.tagName)) anchor = prev;
    const parent = tip.parentElement;
    if (!anchor && parent && parent.matches('h1,h2,h3,h4,h5,h6,label,strong')) anchor = parent;
    if (!anchor && parent && parent.matches('.heading-with-tip')) anchor = parent.querySelector('h1,h2,h3,h4,h5,h6');
    if (!anchor) continue;
    const walker = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT);
    let last = null, node;
    while ((node = walker.nextNode())) { if (node.textContent.trim() && !node.parentElement.closest('.help-tip')) last = node; }
    if (!last) continue;
    const rr = document.createRange();
    rr.selectNodeContents(last);
    const rs = [...rr.getClientRects()].filter(r => r.width > 0 && r.height > 0);
    if (!rs.length) continue;
    const lastRight = Math.max(...rs.filter(r => Math.abs(r.top - rs[rs.length - 1].top) < 4).map(r => r.right));
    const b = btn.getBoundingClientRect();
    out.push({label: anchor.textContent.trim().slice(0, 40), gap: b.left - lastRight});
  }
  return out;
}
"""


@pytest.mark.parametrize("path", PAGES)
def test_help_tip_sits_after_last_word_390(host, base, path):
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 390, "height": 900})
        cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        sep = "&" if "?" in path else "?"
        page.goto(f"{base}{path}{sep}lang=en" if "entities" not in path else f"{base}{path}?edit={host['entity']}&lang=en")
        for item in page.evaluate(HELP_GAP_JS):
            if not 0 <= item["gap"] <= 16:
                problems.append(f"{path} 390: ? is {item['gap']:.1f} px after the last word of: {item['label']}")
        page.close()
        context.close()
        browser.close()
    assert not problems, "\n".join(problems[:20])


# 0788: every visible control in main and the page header keeps 12 px from its neighbour (8 px inside one compound field)
CONTROL_SELECTOR = (
    "button, a.ui-btn, a.btn, input:not([type=hidden]), select, textarea, .ui-badge, .ui-chip, .pill, "
    ".help-tip-btn, [role=tab], .tag, [class*=badge]"
)
CONTROLS_JS = """
() => {
  const SEL = '%s';
  const main = document.querySelector('main') || document.body;
  const header = document.querySelector('header, .page-head, .page-header, .ui-page-head, .settings-head, .entities-head');
  const scopes = [main];
  if (header && !main.contains(header)) scopes.push(header);
  const seen = new Set();
  const items = [];
  const skipped = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (n.matches('.help-tip-body, [popover], .tab-bar, .bottom-tabs, .help-fab, .fab-help, nav.tabbar, .ui-tabbar')) return true;
      if (getComputedStyle(n).position === 'fixed') return true;
    }
    return false;
  };
  for (const scope of scopes) {
    for (const el of scope.querySelectorAll(SEL)) {
      if (seen.has(el)) continue;
      seen.add(el);
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      if (skipped(el)) continue;
      items.push({el, r});
    }
  }
  const kept = items.filter(x => !items.some(y => y !== x && x.el.contains(y.el)));
  const label = (el) => {
    const cls = (typeof el.className === 'string' ? el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '');
    const txt = (el.textContent || el.value || el.placeholder || '').trim().slice(0, 24);
    return el.tagName.toLowerCase() + (cls ? '.' + cls : '') + ' "' + txt + '"';
  };
  const grp = (x) => x.el.closest('.operator-phone, .account-parts');
  const out = [];
  for (let i = 0; i < kept.length; i++) {
    for (let j = i + 1; j < kept.length; j++) {
      const A = kept[i], B = kept[j];
      const a = A.r, b = B.r;
      const need = (grp(A) && grp(A) === grp(B)) ? 8 : 12;
      const vOver = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      const hOver = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      let gap = null;
      if (vOver > 0) {
        gap = hOver > 0 ? -hOver : Math.max(a.left, b.left) - Math.min(a.right, b.right);
      } else if (hOver > 0) {
        gap = Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom);
      }
      if (gap !== null && gap < need) {
        out.push({a: label(A.el), b: label(B.el), gap: Math.round(gap * 10) / 10, need});
      }
    }
  }
  return out;
}
""" % CONTROL_SELECTOR

CONTROL_PAGES = ("/settings", "/entities", "/entities?edit={entity}", "/privacy-requests", "/settings/archived")


@pytest.mark.parametrize("width", WIDTHS)
def test_settings_controls_keep_12px_apart(host, base, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in LANGS:
            context = browser.new_context(viewport={"width": width, "height": 900})
            cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            for template in CONTROL_PAGES:
                path = template.format(entity=host["entity"])
                page = context.new_page()
                sep = "&" if "?" in path else "?"
                page.goto(f"{base}{path}{sep}lang={lang}")
                tag = f"{path} {lang} {width}"
                for item in page.evaluate(CONTROLS_JS):
                    problems.append(f"{tag}: {item['a']} / {item['b']} gap {item['gap']} px (need {item['need']})")
                page.close()
            context.close()
        browser.close()
    assert not problems, "\n".join(problems[:80])


# 0789: the Airbnb settings pattern at every width (390, 768, 1280), en and cs.
AIRBNB_WIDTHS = (390, 768, 1280)
AIRBNB_PAGES = ("/settings", "/settings/archived")

AIRBNB_JS = """
() => {
  const back = document.querySelector('.airbnb-back');
  const h1 = document.querySelector('h1');
  const rows = [...document.querySelectorAll('.airbnb-index-row')].map(r => {
    const b = r.getBoundingClientRect();
    const chev = r.querySelector('.airbnb-chevron');
    const cb = chev ? chev.getBoundingClientRect() : null;
    const label = (r.querySelector('.airbnb-label') || r).textContent.trim();
    return {height: b.height, label: label.slice(0, 60),
            chevCentreDelta: cb ? Math.abs((cb.top + cb.height / 2) - (b.top + b.height / 2)) : 999,
            hasIcon: !!r.querySelector('.airbnb-icon'), hasChevron: !!chev};
  });
  return {
    backX: back ? back.getBoundingClientRect().left : null,
    backW: back ? back.getBoundingClientRect().width : 0,
    backBottom: back ? back.getBoundingClientRect().bottom : 0,
    h1Top: h1 ? h1.getBoundingClientRect().top : 0,
    rows,
  };
}
"""


@pytest.mark.parametrize("width", AIRBNB_WIDTHS)
def test_0789_airbnb_settings_pattern_every_width(host, base, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang in LANGS:
            context = browser.new_context(viewport={"width": width, "height": 900})
            cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            for path in AIRBNB_PAGES:
                page = context.new_page()
                page.goto(f"{base}{path}?lang={lang}")
                tag = f"{path} {lang} {width}"
                info = page.evaluate(AIRBNB_JS)
                if info["backX"] is None:
                    problems.append(f"{tag}: no back button (.airbnb-back)")
                else:
                    if info["backX"] >= 32:
                        problems.append(f"{tag}: back button not top left (x={info['backX']})")
                    if info["backW"] < 40:
                        problems.append(f"{tag}: back button under 40 px ({info['backW']})")
                    if info["h1Top"] < info["backBottom"]:
                        problems.append(f"{tag}: h1 not below the back button")
                if path == "/settings":
                    if not info["rows"]:
                        problems.append(f"{tag}: no index rows (.airbnb-index-row)")
                    for row in info["rows"]:
                        if row["height"] < 56:
                            problems.append(f"{tag}: row under 56 px: {row['label']}")
                        if len(row["label"]) > 40:
                            problems.append(f"{tag}: row label over 40 characters: {row['label']}")
                        if not (row["hasIcon"] and row["hasChevron"]):
                            problems.append(f"{tag}: row without icon or chevron: {row['label']}")
                        elif row["chevCentreDelta"] > 1:
                            problems.append(f"{tag}: chevron not centred: {row['label']}")
                page.close()
            context.close()
        browser.close()
    assert not problems, "\n".join(problems[:40])
