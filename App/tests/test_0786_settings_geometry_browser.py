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
WIDTHS = (390, 1280)
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
    if (prev && /^(H[1-6]|LABEL)$/.test(prev.tagName)) anchor = prev;
    const parent = tip.parentElement;
    if (!anchor && parent && parent.matches('h1,h2,h3,h4,h5,h6,label')) anchor = parent;
    if (!anchor && parent && parent.matches('.heading-with-tip')) anchor = parent.querySelector('h1,h2,h3,h4,h5,h6');
    if (!anchor) continue;
    const a = anchor.getBoundingClientRect(), b = btn.getBoundingClientRect();
    out.push({label: anchor.textContent.trim().slice(0, 40), sameLine: b.top < a.bottom && b.bottom > a.top});
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
                    if not item["sameLine"]:
                        problems.append(f"{tag}: help ? not on the heading line: {item['label']}")
                for item in page.evaluate(CARD_TEXT_JS):
                    if item["left"] < item["cardLeft"] + 16 - 0.5:
                        problems.append(f"{tag}: card text at the edge: {item['text']}")
                for item in page.evaluate(BUTTON_TEXT_JS):
                    problems.append(f"{tag}: text beside a button: {item['button']} / {item['text']}")
                for item in page.evaluate(ROW_JS):
                    if item["spread"] > 1:
                        problems.append(f"{tag}: row actions not on one centre line ({item['spread']:.1f} px) {item['detail']}")
                page.close()
            context.close()
        browser.close()
    assert not problems, "\n".join(problems[:40])
