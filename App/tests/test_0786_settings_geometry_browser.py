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

from app import auth, config, db
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
    backDelta: back && h1 && h1.parentElement ? back.getBoundingClientRect().left - h1.parentElement.getBoundingClientRect().left : null,
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
                    if info["backDelta"] is None or not (0 <= info["backDelta"] < 32):
                        problems.append(f"{tag}: back button not at lane left (dx={info['backDelta']})")
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


# ---------------------------------------------------------------------------
# 0972 (B14): help beside its label, contextual help names, short H1, honest mail
# status, plural-aware activity copy and no duplicated Passkeys/Help labels.
# ---------------------------------------------------------------------------
import os
import re
from pathlib import Path

from app import config
from app.host_i18n import STRINGS as HOST_STRINGS_0972, translate_plural

SHOTS_0972 = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b14")
GROUPS_0972 = ("account", "security", "technical", "help")
VIEWS_0972 = [(lang, width) for lang in ("en", "cs") for width in (390, 768, 1280)]
NAME_PREFIX_0972 = {"en": "Help with ", "cs": "Nápověda: "}

PLACEMENT_JS_0972 = """
() => {
  const out = [];
  for (const btn of document.querySelectorAll('.help-tip-btn')) {
    if (!btn.getClientRects().length) continue;
    const name = btn.getAttribute('aria-label') || '';
    const anchor = btn.closest('.tip-label, h1, h2, h3, label, strong, .settings-toggle-label, .settings-value-label');
    if (!anchor) { out.push({name, problem: 'no label around the help button'}); continue; }
    const walker = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT);
    let last = null, node;
    while ((node = walker.nextNode())) {
      if (node.textContent.trim() && !node.parentElement.closest('.help-tip')) last = node;
    }
    if (!last) { out.push({name, problem: 'label has no text'}); continue; }
    const range = document.createRange();
    range.selectNodeContents(last);
    const rects = [...range.getClientRects()].filter(r => r.height > 0);
    const line = rects[rects.length - 1];
    const b = btn.getBoundingClientRect();
    const mid = b.top + b.height / 2;
    out.push({name, label: anchor.textContent.trim().slice(0, 40), problem: (mid >= line.top - 8 && mid <= line.bottom + 8) ? '' : 'help button is not on the last line of its label'});
  }
  return out;
}
"""

TIP_STATE_JS_0972 = """
(id) => {
  const body = document.getElementById(id);
  const btn = document.querySelector('[aria-controls="' + id + '"]');
  const r = body.getBoundingClientRect();
  const shown = getComputedStyle(body).display !== 'none' && r.width > 0;
  const cs = getComputedStyle(btn);
  return {
    shown, expanded: btn.getAttribute('aria-expanded'),
    left: r.left, right: r.right, top: r.top, bottom: r.bottom,
    vw: document.documentElement.clientWidth, vh: window.innerHeight,
    focusOnBtn: document.activeElement === btn,
    outlineStyle: cs.outlineStyle, outlineWidth: parseFloat(cs.outlineWidth) || 0,
    scrollW: document.documentElement.scrollWidth,
  };
}
"""


@pytest.fixture(scope="module")
def admin_0972():
    db.init_db()
    username = f"b14-0972-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "B14 0972", role="admin", username=username)
    apartment_id = int(db.insert("apartment", {
        "owner_user_id": owner_id, "internal_name": "B14 Flat", "created_at": db.utcnow(),
    }))
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "apartment": apartment_id}  # rows stay: other tests share the test DB


def _open_0972(playwright, base, admin, width, lang, path):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(viewport={"width": width, "height": 900})
    cookie = admin["client"].cookies.get(auth.SESSION_COOKIE)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    page = context.new_page()
    sep = "&" if "?" in path else "?"
    page.goto(f"{base}{path}{sep}lang={lang}")
    return browser, context, page


def _shot_0972(page, name):
    SHOTS_0972.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_0972 / f"{name}.png"), full_page=True)


def _h1_0972(html):
    match = re.search(r'<h1 class="airbnb-title">(.*?)</h1>', html, re.S)
    assert match, "no airbnb-title h1 on the page"
    return match.group(1)


# --- copy and markup tests (no browser needed, but run in the same module) ---

@pytest.mark.parametrize("lang", ("en", "cs"))
def test_0972_activity_copy_is_plural_aware(lang):
    one = translate_plural(lang, "settings.audit.recent", 1)
    many = translate_plural(lang, "settings.audit.recent", 5)
    zero = translate_plural(lang, "settings.audit.recent", 0)
    assert "(1 " in one and "(5 " in many and "(0 " in zero
    assert one != many
    if lang == "en":
        assert one.endswith("(1 event)") and many.endswith("(5 events)") and zero.endswith("(0 events)")
    else:
        assert one.endswith("(1 událost)") and translate_plural(lang, "settings.audit.recent", 3).endswith("(3 události)")
        assert many.endswith("(5 událostí)")


def test_0972_technical_page_uses_the_plural_form_for_its_count(admin_0972):
    html = admin_0972["client"].get("/settings/technical?lang=en").text
    match = re.search(r"Recent activity \((\d+) (event|events)\)", html)
    assert match, "recent-activity heading not found"
    assert match.group(2) == ("event" if match.group(1) == "1" else "events")


def test_0972_h1_is_the_short_title_only(admin_0972):
    client = admin_0972["client"]
    for group, title in (("account", "Account"), ("security", "Security"), ("technical", "Technical"), ("help", "Help")):
        h1 = _h1_0972(client.get(f"/settings/{group}?lang=en").text)
        assert h1.strip() == title, (group, h1)
    h1 = _h1_0972(client.get(f"/apartments/{admin_0972['apartment']}?lang=en").text)
    assert "page-help" not in h1 and "<details" not in h1 and "<ol" not in h1, h1
    assert h1.strip() == "B14 Flat", h1


def test_0972_property_help_is_a_sibling_of_the_h1(admin_0972):
    html = admin_0972["client"].get(f"/apartments/{admin_0972['apartment']}?lang=en").text
    after = html.split("</h1>", 1)[1]
    assert after.lstrip().startswith('<details class="page-help"'), after[:200]


def test_0972_every_settings_help_button_has_its_own_name(admin_0972):
    client = admin_0972["client"]
    for lang, prefix in NAME_PREFIX_0972.items():
        for group in GROUPS_0972:
            html = client.get(f"/settings/{group}?lang={lang}").text
            names = re.findall(r'class="help-tip-btn" aria-label="([^"]*)"', html)
            assert names, (group, lang)
            assert all(n.startswith(prefix) and len(n) > len(prefix) for n in names), (group, lang, names)
            assert len(set(names)) == len(names), (group, lang, names)


def test_0972_passkeys_and_help_labels_are_not_repeated(admin_0972):
    client = admin_0972["client"]
    security = client.get("/settings/security?lang=en").text
    assert security.count(">Passkeys<") == 1
    assert ">Registered<" in security
    helppage = client.get("/settings/help?lang=en").text
    assert ">User guide<" in helppage and ">Open user guide<" in helppage
    assert 'href="/guide" aria-label=' not in helppage
    cs = client.get("/settings/help?lang=cs").text
    assert ">Otevřít příručku<" in cs


@pytest.mark.parametrize("backend", ("disabled", "console", "ses"))
@pytest.mark.parametrize("lang", ("en", "cs"))
def test_0972_mail_status_reports_the_runtime_backend(admin_0972, monkeypatch, backend, lang):
    monkeypatch.setattr(config, "MAIL_BACKEND", backend)
    html = admin_0972["client"].get(f"/settings/technical?lang={lang}").text
    assert f'data-mail-backend="{backend}"' in html
    assert HOST_STRINGS_0972[lang][f"settings.mail.status.{backend}"] in html
    for other in {"disabled", "console", "ses"} - {backend}:
        assert HOST_STRINGS_0972[lang][f"settings.mail.status.{other}"] not in html
    assert "Staging uses the console backend" not in html and "Production stays disabled" not in html


# --- Chromium: placement, keyboard, viewport, H1, mail status ---

@pytest.mark.parametrize("lang,width", VIEWS_0972)
def test_0972_help_stays_beside_its_label_with_a_contextual_name(admin_0972, base, lang, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        for group in GROUPS_0972:
            browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, f"/settings/{group}")
            for item in page.evaluate(PLACEMENT_JS_0972):
                if item["problem"]:
                    problems.append(f"{group} {lang} {width}: {item['problem']}: {item.get('label') or item['name']}")
                if not item["name"].startswith(NAME_PREFIX_0972[lang]):
                    problems.append(f"{group} {lang} {width}: generic help name {item['name']!r}")
            if page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth"):
                problems.append(f"{group} {lang} {width}: page scrolls sideways")
            _shot_0972(page, f"settings-{group}-{lang}-{width}")
            context.close()
            browser.close()
    assert not problems, "\n".join(problems[:30])


@pytest.mark.parametrize("lang,width", [("en", 390), ("en", 768), ("en", 1280), ("cs", 390)])
def test_0972_help_opens_by_pointer_and_keyboard_and_stays_in_the_viewport(admin_0972, base, lang, width):
    problems = []
    with sync_api.sync_playwright() as playwright:
        for group in GROUPS_0972:
            browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, f"/settings/{group}")
            buttons = [b for b in page.locator(".help-tip-btn").all() if b.is_visible()]
            assert buttons, f"{group}: no visible help button"
            for pick, btn in (("first", buttons[0]), ("last", buttons[-1])):
                tip_id = btn.get_attribute("aria-controls")
                where = f"{group} {lang} {width} {pick} ({tip_id})"
                btn.evaluate("e => e.scrollIntoView({block: 'center'})")
                # pointer
                btn.click()
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if not (state["shown"] and state["expanded"] == "true"):
                    problems.append(f"{where}: click did not open the help")
                if state["left"] < -0.5 or state["right"] > state["vw"] + 0.5:
                    problems.append(f"{where}: popover leaves the viewport sideways ({state['left']:.0f}..{state['right']:.0f} of {state['vw']})")
                if state["top"] < -0.5 or state["bottom"] > state["vh"] + 0.5:
                    problems.append(f"{where}: popover leaves the viewport vertically ({state['top']:.0f}..{state['bottom']:.0f} of {state['vh']})")
                if group == "security" and pick == "first" and lang == "en" and width == 390:
                    _shot_0972(page, "help-open-pointer-security-390")
                page.keyboard.press("Escape")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["shown"] or state["expanded"] != "false":
                    problems.append(f"{where}: Escape did not close the help")
                if not state["focusOnBtn"]:
                    problems.append(f"{where}: focus did not return to the help button after Escape")
                # keyboard: reach the button with Tab, so :focus-visible applies
                page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
                reached = False
                for _ in range(150):
                    page.keyboard.press("Tab")
                    if page.evaluate("(id) => document.activeElement && document.activeElement.getAttribute('aria-controls') === id", tip_id):
                        reached = True
                        break
                if not reached:
                    problems.append(f"{where}: Tab never reached the help button")
                    continue
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["outlineStyle"] == "none" or state["outlineWidth"] < 1:
                    problems.append(f"{where}: focus ring not visible on the help button")
                page.keyboard.press("Enter")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if not (state["shown"] and state["expanded"] == "true"):
                    problems.append(f"{where}: Enter did not open the help")
                if state["left"] < -0.5 or state["right"] > state["vw"] + 0.5:
                    problems.append(f"{where}: keyboard-opened popover leaves the viewport sideways")
                page.keyboard.press("Escape")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["shown"] or not state["focusOnBtn"]:
                    problems.append(f"{where}: keyboard Escape did not close and return focus")
                page.keyboard.press("Enter")
                page.keyboard.press("Tab")
                state = page.evaluate(TIP_STATE_JS_0972, tip_id)
                if state["shown"] or state["focusOnBtn"]:
                    problems.append(f"{where}: Tab did not move on and close the help")
            context.close()
            browser.close()
    assert not problems, "\n".join(problems[:30])


@pytest.mark.parametrize("lang,width", VIEWS_0972)
def test_0972_property_h1_stays_short_while_its_help_is_open(admin_0972, base, lang, width):
    path = f"/apartments/{admin_0972['apartment']}"
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, path)
        summary = page.locator(".airbnb-header > .page-help > summary").first
        if not summary.count():
            problems.append("no .airbnb-header > .page-help > summary beside the property H1")
        else:
            summary.click()
            h1 = page.evaluate("() => document.querySelector('h1.airbnb-title').textContent.trim()")
            if h1 != "B14 Flat":
                problems.append(f"H1 text is {h1!r}")
            if page.evaluate("() => !!document.querySelector('h1.airbnb-title details, h1.airbnb-title .page-help-body')"):
                problems.append("help content sits inside the H1")
            box = page.evaluate("""() => { const r = document.querySelector('.page-help-body').getBoundingClientRect();
                return {left: r.left, right: r.right, vw: document.documentElement.clientWidth}; }""")
            if box["left"] < -0.5 or box["right"] > box["vw"] + 0.5:
                problems.append(f"page help leaves the viewport sideways: {box}")
            _shot_0972(page, f"property-help-open-{lang}-{width}")
        context.close()
        browser.close()
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("lang,width", VIEWS_0972)
def test_0972_mail_status_with_mail_disabled_in_the_browser(admin_0972, base, monkeypatch, lang, width):
    monkeypatch.setattr(config, "MAIL_BACKEND", "disabled")
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open_0972(playwright, base, admin_0972, width, lang, "/settings/technical")
        status = page.locator("#settings-mail-status")
        assert status.is_visible()
        assert status.inner_text().strip() == HOST_STRINGS_0972[lang]["settings.mail.status.disabled"]
        assert page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        status.scroll_into_view_if_needed()
        _shot_0972(page, f"technical-mail-disabled-{lang}-{width}")
        context.close()
        browser.close()
