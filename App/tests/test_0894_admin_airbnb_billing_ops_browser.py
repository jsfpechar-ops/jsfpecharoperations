"""0894: admin billing and operations in the Airbnb pattern (geometry, fine print, gaps)."""

import os
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.conftest import mark_security_prompt_seen
from tests.test_0893_admin_airbnb_browser import (  # noqa: F401
    GEOMETRY_JS,
    base,
    chromium_launch_kwargs,
    fine_print_and_gap_findings,
    host,
)

WIDTHS = [320, 390, 768, 1024, 1280, 1440]
SHOT_WIDTHS = {390, 1280}
SHOT_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0894"
PAGES = {
    "admin_billing": "/admin/fakturace",
    "admin_operations": "/admin/operations",
}


def shoot(page, name, width):
    """Save a full-page screenshot at 390 and 1280 px when UBYHOST_SHOTS_0893=1."""
    if os.environ.get("UBYHOST_SHOTS_0893") != "1" or width not in SHOT_WIDTHS:
        return
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOT_DIR / f"0894-{name}-{width}.png"), full_page=True)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("name", list(PAGES))
def test_admin_billing_ops_geometry(host, base, name, width):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        page = context.new_page()
        page.goto(f"{base}{PAGES[name]}?lang=en")
        tag = f"{name} {width}"
        problems = [f"{tag}: {item}" for item in page.evaluate(GEOMETRY_JS)]
        problems += [f"{tag}: {item}" for item in fine_print_and_gap_findings(page)]
        shoot(page, name, width)
        browser.close()
    assert not problems, "\n".join(problems)


# ---- 0974 (B16): operator Customers and Billing layouts ----------------------------
import tempfile  # noqa: E402

from app import db  # noqa: E402

B16_WIDTHS = [390, 768, 1280]
B16_LANGS = ["en", "cs"]
B16_SHOTS = Path(os.environ.get("UBYHOST_SHOTS_DIR") or tempfile.gettempdir())
B16_LONG = "Synthetic-long-name-" + "x" * 90


def _b16_shot(page, name):
    B16_SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(B16_SHOTS / f"{name}.png"), full_page=True)


def _b16_open(playwright, host, base, width):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(viewport={"width": width, "height": 900})
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    return browser, context.new_page()


B16_CUSTOMERS_JS = """
() => {
  const out = [];
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const cards = [...document.querySelectorAll('.customers-metrics .ui-stat')].filter(vis);
  if (cards.length !== 6) out.push('metric cards ' + cards.length);
  const rows = {};
  for (const c of cards) { const r = c.getBoundingClientRect(); (rows[Math.round(r.top)] = rows[Math.round(r.top)] || []).push(r); }
  const counts = Object.values(rows).map((r) => r.length);
  if (new Set(counts).size > 1) out.push('uneven metric rows ' + counts.join(','));
  const widths = cards.map((c) => c.getBoundingClientRect().width);
  if (widths.length && Math.max(...widths) - Math.min(...widths) > 1.5) out.push('metric card widths differ');
  const want = window.innerWidth >= 768 ? 3 : 2;
  if (counts.length && counts[0] !== want) out.push('metric columns ' + counts[0] + ' want ' + want);
  const section = document.querySelector('#create-host');
  if (!section) { out.push('no #create-host'); return out; }
  if (section.closest('nav')) out.push('create-host sits inside a nav');
  const lane = document.querySelector('.ui-body').getBoundingClientRect();
  const s = section.getBoundingClientRect();
  if (Math.abs(s.left - lane.left) > 2) out.push('create-host not at the lane left edge');
  if (s.width > 561) out.push('create-host wider than 560: ' + s.width);
  if (s.width < Math.min(lane.width, 560) - 2) out.push('create-host narrower than its lane: ' + s.width);
  const primaries = section.querySelectorAll('.ui-btn-primary');
  if (primaries.length !== 1) out.push('create-host primary buttons ' + primaries.length);
  for (const i of section.querySelectorAll('input:not([type=hidden])')) if (i.getBoundingClientRect().height < (window.innerWidth >= 1024 ? 39.5 : 43.5)) out.push('create-host input under control height: ' + i.id);
  if (document.documentElement.scrollWidth > document.documentElement.clientWidth) out.push('horizontal overflow');
  return out;
}
"""

B16_BILLING_JS = """
() => {
  const out = [];
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const forms = [...document.querySelectorAll('form.admin-controls')].filter(vis);
  if (forms.length < 3) out.push('admin-controls forms ' + forms.length);
  const want = window.innerWidth >= 1024 ? 40 : 44;
  for (const f of forms) {
    for (const field of f.querySelectorAll('.ui-field')) {
      const l = field.querySelector('label').getBoundingClientRect();
      const i = field.querySelector('input,select').getBoundingClientRect();
      if (l.bottom > i.top + 1) out.push('label not above its field: ' + field.querySelector('label').textContent.trim());
      if (Math.abs(l.left - i.left) > 2) out.push('label not aligned with its field');
      if (Math.abs(i.height - want) > 0.6) out.push('field height ' + i.height + ' want ' + want);
    }
    for (const b of f.querySelectorAll('.ui-btn')) if (Math.abs(b.getBoundingClientRect().height - want) > 0.6) out.push('button height ' + b.getBoundingClientRect().height + ' want ' + want);
    if (f.scrollWidth > f.clientWidth + 1) out.push('form overflows');
  }
  if (document.documentElement.scrollWidth > document.documentElement.clientWidth) out.push('horizontal overflow');
  return out;
}
"""


@pytest.fixture(scope="module")
def b16_long_customer(host):
    """One synthetic customer with a very long name (rows stay: other tests share the test DB)."""
    username = f"b16-long-{host['owner']}"
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (username,)):
        mark_security_prompt_seen(auth.create_account(f"{username}@example.test", B16_LONG, role="host", username=username))
    return username


@pytest.mark.parametrize("lang", B16_LANGS)
@pytest.mark.parametrize("width", B16_WIDTHS)
@pytest.mark.parametrize("state", ["populated", "empty"])
def test_b16_customers_layout(host, base, b16_long_customer, state, width, lang):
    query = "Synthetic-long-name" if state == "populated" else "no-such-customer-zzz"
    with sync_api.sync_playwright() as playwright:
        browser, page = _b16_open(playwright, host, base, width)
        page.goto(f"{base}/admin/customers?lang={lang}&q={query}")
        problems = page.evaluate(B16_CUSTOMERS_JS)
        if state == "populated":
            assert page.locator("tr[data-customer-id]").count() >= 1
        _b16_shot(page, f"customers-{state}-{lang}-{width}")
        browser.close()
    assert not problems, "\n".join(f"customers {state} {lang} {width}: {p}" for p in problems)


def test_b16_create_host_empty_submit_creates_nothing(host, base):
    before = db.query_one("SELECT COUNT(*) AS n FROM user_account")["n"]
    posts = []
    with sync_api.sync_playwright() as playwright:
        browser, page = _b16_open(playwright, host, base, 390)
        page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
        page.goto(f"{base}/admin/customers?lang=en")
        page.locator("#create-host button[type=submit]").click()
        invalid = page.evaluate("document.querySelector('#email').validity.valueMissing")
        url = page.url
        _b16_shot(page, "customers-create-empty-submit-en-390")
        browser.close()
    assert invalid, "the empty e-mail must be refused in the browser"
    assert not posts, f"no POST may be sent: {posts}"
    assert "/admin/customers" in url
    assert db.query_one("SELECT COUNT(*) AS n FROM user_account")["n"] == before


@pytest.mark.parametrize("lang", B16_LANGS)
@pytest.mark.parametrize("width", B16_WIDTHS)
def test_b16_billing_controls(host, base, width, lang):
    with sync_api.sync_playwright() as playwright:
        browser, page = _b16_open(playwright, host, base, width)
        page.goto(f"{base}/admin/fakturace?lang={lang}&q={B16_LONG}")
        page.evaluate("document.querySelector('#reports').open = true")
        problems = page.evaluate(B16_BILLING_JS)
        month = page.locator("#month form.admin-controls")
        assert month.locator(".ui-btn-primary").count() == 1
        export = month.locator("a.ui-btn-secondary[download]")
        assert export.count() == 1 and "/admin/fakturace/export?mesic=" in export.get_attribute("href")
        assert page.locator("#portfolio a.ui-btn-secondary[download]").count() == 1
        _b16_shot(page, f"billing-{lang}-{width}")
        browser.close()
    assert not problems, "\n".join(f"billing {lang} {width}: {p}" for p in problems)
