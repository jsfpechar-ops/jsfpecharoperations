"""0830: the Airbnb pattern on the remaining host pages (parts B to F). Each page keeps one h1, back header on
detail and sub-pages, 44 px pills 12 px apart, 1 px bordered cards with 16 px inset text, 12 px between neighbours
and no fine print outside help bodies, at every width. Run one part with `-k partB` (ids carry the part letter)."""
from __future__ import annotations

import os
import secrets
from datetime import date
from pathlib import Path

import pytest

from app import db
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_0710_v2_mockup_match_browser import _launch, _open_app, _placeholders, base, dashboard_host, dashboard_rich_host
from tests.v2_mockup import WIDTHS, geometry_findings

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

# id -> path. {first_property}, {stay_id}, {invoice_id}, {submission_id} are filled in by `seeded`.
ROUTES = {
    "partB-overview": "/",
    "partB-menu": "/menu",
    "partC-properties": "/apartments",
    "partC-property-detail": "/apartments/{first_property}",
    "partD-reservations": "/reservations",
    "partD-stay-detail": "/reservations/{stay_id}",
    "partE-invoice-detail": "/invoices/{invoice_id}",
    "partE-invoice-form": "/invoices/new",  # the stay picker is a partial of this form
    "partE-submission-detail": "/submissions/{submission_id}",
    "partF-guest-questions": "/apartments/{first_property}/guide/questions",
    "partF-leon-settings": "/apartments/{first_property}/leon",
    "partF-cleaning-settings": "/cleaning/properties/{first_property}",
    "partF-subscription": "/predplatne",
}
# detail and sub-pages: the back header is required (its back goes to the list page)
BACK_PAGES = {name for name in ROUTES if name not in {"partB-overview", "partB-menu", "partC-properties", "partD-reservations"}}
SHOT_WIDTHS = (390, 768, 1280)
SHOTS_DIR = Path(__file__).resolve().parents[2] / "docs/tasks/screenshots-0830"  # UBYHOST_SHOTS_0830=1 writes PNGs
CASES = [(name, width) for name in ROUTES for width in WIDTHS]
IDS = [f"{name}-{width}" for name, width in CASES]

_SHELL_JS = """() => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  return {
    v2: document.body.classList.contains('v2'),
    h1: [...document.querySelectorAll('h1')].filter(visible).length,
  };
}"""

# returns one string per problem; isBack says whether the page must show the back header
_AUDIT_JS = """(isBack) => {
  const out = [];
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const doc = document.documentElement;
  if (doc.scrollWidth > doc.clientWidth + 1) out.push(`horizontal scroll: ${doc.scrollWidth} px page in a ${doc.clientWidth} px viewport`);
  const root = document.querySelector('main') || document.body;
  const h1 = [...document.querySelectorAll('h1')].filter(vis)[0];

  const back = [...document.querySelectorAll('.airbnb-back')].filter(vis)[0];
  if (isBack) {
    if (!back) out.push('detail or sub-page has no visible .airbnb-back');
    else {
      const b = back.getBoundingClientRect();
      if (b.width < 40 || b.height < 40) out.push(`back button is ${b.width.toFixed(0)}x${b.height.toFixed(0)} px, need >= 40`);
      if (h1) {
        const a = h1.getBoundingClientRect();
        if (!(b.right <= a.left + 0.5 || b.bottom <= a.top + 0.5)) out.push('back button is neither left of nor above the h1');
      }
    }
  }

  // gap between two non-nested boxes that share a row or a column; null when they overlap or sit diagonally
  const gap = (a, b) => {
    const horiz = Math.max(b.left - a.right, a.left - b.right);
    const vert = Math.max(b.top - a.bottom, a.top - b.bottom);
    const overlapY = a.top < b.bottom && b.top < a.bottom;
    const overlapX = a.left < b.right && b.left < a.right;
    if (overlapX && overlapY) return null;
    if (overlapY) return horiz;
    if (overlapX) return vert;
    return null;
  };

  const groups = new Map();
  for (const p of [...document.querySelectorAll('.settings-pill')].filter(vis)) {
    const k = p.parentElement;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(p);
  }
  for (const items of groups.values()) {
    const current = items.filter(p => p.hasAttribute('aria-current')).length;
    if (current !== 1) out.push(`pill group has ${current} pills with aria-current, need exactly 1`);
    for (const p of items) {
      const h = p.getBoundingClientRect().height;
      if (h < 44) out.push(`pill "${p.textContent.trim().slice(0, 20)}" is ${h.toFixed(0)} px tall, need >= 44`);
    }
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      const g = gap(items[i].getBoundingClientRect(), items[j].getBoundingClientRect());
      if (g !== null && g < 11.5) out.push(`pills "${items[i].textContent.trim().slice(0, 15)}" and "${items[j].textContent.trim().slice(0, 15)}" are ${g.toFixed(0)} px apart, need >= 12`);
    }
  }

  // value cards and list cards: .card is the generic card, so a wrapper card is checked too
  const cards = [...new Set([...root.querySelectorAll('.settings-value-card, .card')])].filter(vis);
  for (const card of cards) {
    const cs = getComputedStyle(card);
    const cr = card.getBoundingClientRect();
    const label = card.textContent.trim().replace(/\\s+/g, ' ').slice(0, 30);
    const widths = [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth];
    if (widths.some(w => w !== '1px')) out.push(`card "${label}" border is ${widths.join(' ')}, need 1px`);
    if (!(parseFloat(cs.borderTopLeftRadius) >= 12)) out.push(`card "${label}" radius is ${cs.borderTopLeftRadius}, need >= 12px`);
    const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent.trim()) continue;
      const el = node.parentElement;
      if (!el || el.closest('.help-tip-body, .help-tip, script, style, summary')) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
      if (!rects.length) continue;
      const left = Math.min(...rects.map(r => r.left));
      const right = Math.max(...rects.map(r => r.right));
      if (left < cr.left + 16 - 0.5 || right > cr.right - 16 + 0.5) {
        out.push(`card "${label}": text "${node.textContent.trim().slice(0, 30)}" is within 16 px of the card edge`);
        break;
      }
    }
  }

  // 12 px between neighbouring interactive or text boxes in the main lane
  const SEL = 'a[href], button, input:not([type=hidden]), select, textarea, .settings-pill, .settings-value-card, .airbnb-index-row, h1, h2, h3, h4, p, label, li';
  const boxes = [...root.querySelectorAll(SEL)].filter(el => vis(el) &&
    !el.closest('.help-tip-body, .help-tip, summary, details:not([open]), table, .ui-table-stack, script, style, .row-menu, nav, .stays-links'));
  const describe = el => (el.tagName.toLowerCase() + ': ' + el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 20));
  let pairs = 0;
  for (let i = 0; i < boxes.length && pairs < 8; i++) for (let j = i + 1; j < boxes.length && pairs < 8; j++) {
    const a = boxes[i], b = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const g = gap(a.getBoundingClientRect(), b.getBoundingClientRect());
    if (g !== null && g < 11.5) {
      out.push(`${describe(a)} and ${describe(b)} are ${g.toFixed(0)} px apart, need >= 12`);
      pairs += 1;
    }
  }

  // no fine print: any visible element (any tag) whose OWN text (its direct text nodes, not its children) is longer
  // than 60 characters, outside help bodies, open help panels, headings, input labels, table cells and form fields
  const SKIP_FINE = 'h1, h2, h3, h4, h5, h6, label, td, th, table, textarea, input, select, option, script, style';
  // .env-banner is the shell's practice-mode safety alert (base.html, _env_banner.html), shown only when UBYPORT_ENV is mock
  const HELP_PANEL = '.help-tip-body, .help-tip, .env-banner, details[open].ui-how, details[open].page-help, details[open].stays-how, details[open].help-panel';
  for (const el of [root, ...root.querySelectorAll('*')]) {
    if (el.matches(SKIP_FINE) || el.closest(SKIP_FINE + ', ' + HELP_PANEL)) continue;
    if (!vis(el)) continue;
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').trim().replace(/\\s+/g, ' ');
    if (own.length > 60) out.push(`fine print of ${own.length} characters outside a help body: "${own.slice(0, 40)}..."`);
  }
  return out;
}"""


def _launch_ctx():
    from tests.test_host_quiet_dashboard_browser import sync_api

    return sync_api.sync_playwright()


@pytest.fixture(scope="module")
def seeded(dashboard_rich_host):
    """One invoice and one submission on the rich host's stay (the property, the stay and the rest come from it)."""
    row = db.query_one(
        "SELECT a.id AS apartment_id, a.legal_entity_id AS entity_id, a.owner_user_id AS owner_id "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (dashboard_rich_host["ready"],),
    )
    now = db.utcnow()
    today = date.today()
    seq = 900000 + secrets.randbelow(90000)
    invoice_id = db.insert("invoice", {
        "legal_entity_id": row["entity_id"], "apartment_id": row["apartment_id"],
        "reservation_id": dashboard_rich_host["ready"], "kind": "invoice", "seq_year": today.year,
        "seq_no": seq, "number": f"{today.year}-{seq:04d}-{secrets.token_hex(2)}",
        "vs": f"{today.year}{seq:04d}", "lang": "en", "vat_status": "non_payer",
        "issue_date": today.isoformat(), "seller_name": "0830 Fixture s.r.o.", "seller_seat": "Praha 1",
        "buyer_name": "Synthetic Buyer", "total_haler": 300000, "owner_user_id": row["owner_id"], "created_at": now,
    })
    submission_id = db.insert("submission", {
        "apartment_id": row["apartment_id"], "created_at": now, "state": "ok",
        "request_xml": "<request/>", "response_xml": "<response/>",
    })
    yield {"invoice_id": invoice_id, "submission_id": submission_id}
    # the rich host's teardown deletes its apartment, so these rows must go first (foreign keys)
    db.execute("DELETE FROM invoice WHERE id = ?", (invoice_id,))
    db.execute("DELETE FROM submission WHERE id = ?", (submission_id,))


@pytest.fixture
def leon_on(dashboard_rich_host, monkeypatch):
    """The Leon settings page is a 404 while AI features are off and redirects to setup while Leon is off or the terms
    are stale. Same switches as test_0396's leon_offered fixture, plus Leon on with current terms for the first property;
    the apartment's Leon columns are restored afterwards."""
    from app import config, leon

    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset())
    apartment = _placeholders(dashboard_rich_host)["first_property"]
    before = db.query_one("SELECT leon_enabled, leon_terms_version FROM apartment WHERE id = ?", (apartment,))
    db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = ? WHERE id = ?", (leon.LEON_TERMS_VERSION, apartment))
    yield apartment
    db.execute("UPDATE apartment SET leon_enabled = ?, leon_terms_version = ? WHERE id = ?",
               (before["leon_enabled"], before["leon_terms_version"], apartment))


def _path(name, host, seeded_ids):
    values = {**_placeholders(host), **seeded_ids}
    return ROUTES[name].format(**values)


@pytest.mark.parametrize("name,width", CASES, ids=IDS)
def test_0830_airbnb_page(name, width, base, dashboard_rich_host, seeded, monkeypatch, request):
    from app import auth, config

    if name == "partF-subscription":
        # /predplatne redirects to /settings while billing is off (routes/billing.py), so switch it on for this page
        monkeypatch.setattr(config, "BILLING_ENABLED", True)
    if name == "partF-leon-settings":
        request.getfixturevalue("leon_on")
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    path = _path(name, dashboard_rich_host, seeded)
    with _launch_ctx() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, path, width)
        shell = page.evaluate(_SHELL_JS)
        findings = geometry_findings(page, width)
        audit = page.evaluate(_AUDIT_JS, name in BACK_PAGES)
        url = page.url
        if os.environ.get("UBYHOST_SHOTS_0830") == "1" and width in SHOT_WIDTHS:
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS_DIR / f"{name}-{width}.png"), full_page=True)
        context.close()
        browser.close()
    problems = []
    if not shell["v2"]:
        problems.append("body is not on the v2 shell (set v2 = true in the template)")
    if shell["h1"] != 1:
        problems.append(f"{shell['h1']} visible h1 elements, expected exactly 1")
    problems += findings
    problems += audit
    assert not problems, f"{name} ({url}) at {width} px:\n" + "\n".join(problems)


def test_0830C_properties_regressions(base, dashboard_rich_host, seeded):
    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    path = _path("partC-properties", dashboard_rich_host, seeded)
    problems = []
    with _launch_ctx() as playwright:
        browser = _launch(playwright)
        for width in (390, 1280):
            context, page = _open_app(browser, base, cookie, path, width)
            state = page.evaluate(
                """() => {
                    const visible = (e) => !!e && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0;
                    const sub = [...document.querySelectorAll('.props-head p.sub')].filter(visible).length;
                    const how = document.querySelector('details.page-help[data-how="properties"]');
                    const summary = how ? how.querySelector('summary') : null;
                    const body = how ? how.querySelector('.page-help-body') : null;
                    const thead = document.querySelector('.props-card thead');
                    const card = document.querySelector('.props-card');
                    return {
                        sub,
                        howOpen: how ? how.open : null,
                        bodyVisible: visible(body),
                        markers: summary ? getComputedStyle(summary).listStyleType : null,
                        chevrons: summary ? [...summary.querySelectorAll('svg.ui-how-chevron')].filter(visible).length : 0,
                        theadVisible: visible(thead) && [...thead.querySelectorAll('th')].some(th => { const c = getComputedStyle(th).backgroundColor; return c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent'; }),  // 0852: the desktop header row stays (screen readers, list-cards guard) but must not be beige
                        cardBorder: card ? getComputedStyle(card).borderTopWidth : null,
                    };
                }"""
            )
            context.close()
            if state["sub"] != 0:
                problems.append(f"{width}: fine print under the h1 is still visible")
            if state["howOpen"] is not False or state["bodyVisible"]:
                problems.append(f"{width}: the help box renders expanded by default")
            if state["markers"] != "none":
                problems.append(f"{width}: help summary still shows a native marker")
            if state["chevrons"] > 0:
                problems.append(f"{width}: help summary shows a chevron icon")
            if state["theadVisible"]:
                problems.append(f"{width}: beige table header is visible")
            if state["cardBorder"] != "1px":
                problems.append(f"{width}: list container has no 1 px border")
        browser.close()
    assert not problems, problems


def test_0831G_page_help(base, dashboard_rich_host, seeded):
    from playwright import sync_api

    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for path in ("/apartments", "/reservations"):
            for width in (390, 1280):
                context, page = _open_app(browser, base, cookie, path, width)
                if page.locator(".ui-how").count():
                    problems.append(f"{path} {width}: .ui-how is still on the page")
                button = page.locator(".page-help-dot, .stays-title-row .help-tip-btn").first
                if not button.is_visible():
                    problems.append(f"{path} {width}: the help ? is not visible")
                else:
                    box = button.bounding_box()
                    title = page.evaluate(
                        """() => {
                            const h1 = document.querySelector('h1');
                            const walker = document.createTreeWalker(h1, NodeFilter.SHOW_TEXT);
                            let node = null;
                            while ((node = walker.nextNode())) { if (node.textContent.trim()) break; }
                            const range = document.createRange();
                            range.selectNodeContents(node);
                            const r = range.getBoundingClientRect();
                            return {right: r.right, mid: (r.top + r.bottom) / 2};
                        }"""
                    )
                    if not 16 <= box["width"] <= 20:
                        problems.append(f"{path} {width}: ? is {box['width']} px wide")
                    if abs(box["y"] + box["height"] / 2 - title["mid"]) > 8:
                        problems.append(f"{path} {width}: ? is not centred on the h1 line")
                    gap = box["x"] - title["right"]
                    if not 6 <= gap <= 12:
                        problems.append(f"{path} {width}: ? sits {gap:.1f} px after the title")
                if page.locator(".page-help").count():
                    body = page.locator(".page-help-body").first
                    if body.is_visible():
                        problems.append(f"{path} {width}: help body is open by default")
                    before = page.evaluate("() => document.documentElement.scrollHeight")
                    page.locator(".page-help-btn").first.click()
                    settle_motion(page)
                    pb = body.bounding_box()
                    viewport = page.viewport_size
                    if not body.is_visible() or pb["x"] < 0 or pb["x"] + pb["width"] > viewport["width"]:
                        problems.append(f"{path} {width}: help body is not visible inside the viewport")
                    after = page.evaluate("() => document.documentElement.scrollHeight")
                    if after != before:
                        problems.append(f"{path} {width}: opening help moved the page")
                context.close()
        browser.close()
    assert not problems, problems


def test_0830D_stays_regressions():
    # Stays list with ZERO stays seeded: tabs are settings pills, one help control, index-row links.
    from tests.test_signed_in_chrome import empty_host as _empty_host

    gen = _empty_host.__wrapped__()
    host = next(gen)
    page = host.get("/reservations?lang=en").text
    assert page.count("<h1") == 1
    assert 'class="settings-pills"' in page or 'data-empty-state' in page
    assert 'class="chip ' not in page and 'class="chips' not in page
    assert page.count("ui-how-chevron") <= 1
