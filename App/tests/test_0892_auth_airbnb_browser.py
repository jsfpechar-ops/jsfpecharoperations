"""0892: the auth pages (login, magic link, 2FA) keep the Airbnb shell at six widths.

One big bold title, help under a small "?", no fine print, 12 px between neighbours,
44 px tap targets, and the login form still works with JavaScript off.
"""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path

import pyotp
import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

sync_api = pytest.importorskip("playwright.sync_api")

WIDTHS = (320, 390, 768, 1024, 1280, 1440)
PAGE_NAMES = (
    "login",
    "login_sent",
    "login_link_expired",
    "two_factor_login",
    "two_factor_setup",
    "two_factor_recovery",
)
SHOTS_ON = os.environ.get("UBYHOST_SHOTS_0892") == "1"
SHOTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0892"

CHECK_JS = r"""
() => {
  const problems = [];
  const all = s => [...document.querySelectorAll(s)];
  const vis = el => {
    const d = el.closest('details');
    if (d && d !== el && !d.open && !el.closest('summary')) return false;
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const h1s = all('h1').filter(vis);
  if (h1s.length !== 1) problems.push(`visible h1 count ${h1s.length}`);
  if (h1s.length) {
    const cs = getComputedStyle(h1s[0]);
    if (parseFloat(cs.fontSize) < 28) problems.push(`h1 font ${cs.fontSize}`);
    if (parseInt(cs.fontWeight, 10) < 700) problems.push(`h1 weight ${cs.fontWeight}`);
  }
  if (document.documentElement.scrollWidth > window.innerWidth) {
    problems.push(`horizontal scroll ${document.documentElement.scrollWidth} > ${window.innerWidth}`);
  }

  // Text sizes: 14 px floor for all visible text, 16 px for p, li and .small outside the legal lines and alerts.
  const ownText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim() !== '');
  const exempt16 = el => el.closest('.auth-acceptance, .auth-foot-legal, [role=alert], [role=status]');
  for (const el of all('body *')) {
    if (!ownText(el) || !vis(el)) continue;
    if (el.closest('.auth-q > summary')) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    const label = (el.textContent || '').trim().slice(0, 40);
    if (fs < 14) problems.push(`text ${fs}px: ${label}`);
    if (el.matches('p, li, .small') && fs < 16 && !exempt16(el)) problems.push(`${fs}px ${el.tagName}: ${label}`);
  }

  // The "?" next to the title: 18 px square, on the h1's last line, 6 to 10 px from the text (or the h1 box edge).
  const summary = all('.auth-q > summary').filter(vis)[0];
  if (summary && h1s.length) {
    const r = summary.getBoundingClientRect();
    const h = h1s[0].getBoundingClientRect();
    if (Math.abs(r.width - 18) > 1 || Math.abs(r.height - 18) > 1) problems.push(`? box ${r.width}x${r.height}`);
    const range = document.createRange();
    range.selectNodeContents(h1s[0]);
    const lines = [...range.getClientRects()].filter(x => x.width > 0);
    const last = lines[lines.length - 1];
    if (last && r.bottom > last.top && r.top < last.bottom) {
      const gapText = r.left - last.right;
      const gapBox = r.left - h.right;
      const okText = gapText >= 6 && gapText <= 10;
      const okBox = gapBox >= 6 && gapBox <= 10;
      if (!okText && !okBox) problems.push(`? gap from title text ${gapText.toFixed(1)} / box ${gapBox.toFixed(1)}`);
    } else {
      problems.push('? not on the h1 last line');
    }
  }

  // 12 px between neighbours (the "?" to title gap is the 8 px exception).
  const sel = ['h1', '.auth-q > summary', '.auth-field', '.auth-submit', '.auth-help > summary',
    '.auth-acceptance', '.auth-foot a', '.auth-codes', '.auth-codes-actions .btn']
    .map(s => '.auth-card ' + s).join(', ');
  const boxes = [...new Set([...all(sel), ...all('.auth-lang-switch button')])].filter(vis);
  const items = boxes.map(el => ({el, r: el.getBoundingClientRect(),
    name: (el.tagName + ' ' + (typeof el.className === 'string' ? el.className : '') + ' ' + (el.textContent || '').trim().slice(0, 20)).trim()}));
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const A = a.r, B = b.r;
      const ox = Math.min(A.right, B.right) - Math.max(A.left, B.left);
      const oy = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
      if (ox > 0.5 && oy > 0.5) { problems.push(`overlap ${a.name} / ${b.name}`); continue; }
      let gap = null;
      if (oy > 0) gap = Math.max(B.left - A.right, A.left - B.right);
      else if (ox > 0) gap = Math.max(B.top - A.bottom, A.top - B.bottom);
      if (gap === null || gap < 0) continue;
      const titleHelp = (a.el.tagName === 'H1' && b.el.matches('.auth-q > summary'))
        || (b.el.tagName === 'H1' && a.el.matches('.auth-q > summary'));
      const need = titleHelp ? 7.5 : 12;
      if (gap < need) problems.push(`gap ${gap.toFixed(1)} < ${need}: ${a.name} / ${b.name}`);
    }
  }

  // Tap targets: buttons, inputs and language buttons at least 44 px tall.
  const taps = all('.auth-card button, .auth-card input:not([type=hidden]), .auth-card a.auth-submit, '
    + '.auth-card .btn, .auth-lang-switch button').filter(vis);
  for (const el of taps) {
    const h = el.getBoundingClientRect().height;
    if (h < 43.5) problems.push(`tap target ${h.toFixed(0)}px: ${(el.textContent || el.id || '').trim().slice(0, 30)}`);
  }

  // Card: 1 px border and radius 12 or more from 1024 up, no border below.
  const card = document.querySelector('.auth-card');
  if (card) {
    const cs = getComputedStyle(card);
    const bw = parseFloat(cs.borderTopWidth) || 0;
    const rad = parseFloat(cs.borderTopLeftRadius) || 0;
    if (window.innerWidth >= 1024) {
      if (bw !== 1 || rad < 12) problems.push(`card border ${bw}px radius ${rad}px at desktop`);
    } else if (bw !== 0) {
      problems.push(`card border ${bw}px below 1024`);
    }
  }
  return {problems};
}
"""


@pytest.fixture(scope="module")
def base():
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
        pytest.fail("the 0892 test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        chromium = playwright.chromium.launch(**chromium_launch_kwargs())
        yield chromium
        chromium.close()


def _name(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(4)}"


def _csrf(client: TestClient, path: str) -> str:
    text = client.get(path).text
    match = re.search(r'name="_csrf" value="([^"]+)"', text)
    assert match, text[:300]
    return match.group(1)


def _host_client() -> TestClient:
    db.init_db()
    username = _name("geo0892")
    auth.create_account(f"{username}@example.test", "Geometry 0892", role="host", username=username)
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def _second_factor_html() -> str:
    db.init_db()
    username = _name("geo0892")
    user_id = auth.create_account(f"{username}@example.test", "Geometry 0892", username=username)
    auth.enable_totp(user_id, auth.new_totp_secret(), auth.new_recovery_codes())
    client = TestClient(app)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    challenge = login_as(client, username, follow_redirects=False)
    assert challenge.status_code == 200, challenge.text[:300]
    return challenge.text


def _recovery_html() -> str:
    client = _host_client()
    setup = client.get("/account/2fa/setup")
    match = re.search(r'<code id="totp-setup-key">([^<]+)</code>', setup.text)
    assert match, setup.text[:300]
    secret = match.group(1).replace(" ", "")
    page = client.post("/account/2fa/setup", data={"code": pyotp.TOTP(secret).now()}, follow_redirects=False)
    assert page.status_code == 200, page.text[:300]
    return page.text


@pytest.fixture(scope="module")
def pages():
    db.init_db()
    client = TestClient(app)
    token = _csrf(client, "/login?lang=en")
    sent = client.post(
        "/login",
        data={"_csrf": token, "email": f"{_name('geo0892')}@example.test", "next": ""},
        follow_redirects=True,
    )
    assert sent.status_code == 200, sent.text[:300]
    return {
        "login": TestClient(app).get("/login?lang=en").text,
        "login_sent": sent.text,
        "login_link_expired": TestClient(app).get("/login/link?t=nope&lang=en").text,
        "two_factor_login": _second_factor_html(),
        "two_factor_setup": _host_client().get("/account/2fa/setup").text,
        "two_factor_recovery": _recovery_html(),
    }


def _open(browser, base: str, html_text: str, width: int, javascript: bool = True):
    context = browser.new_context(
        viewport={"width": width, "height": 900}, java_script_enabled=javascript
    )
    page = context.new_page()
    page.goto(base + "/login?lang=en")
    page.set_content(html_text)
    return context, page


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("page_name", PAGE_NAMES)
def test_auth_shell_geometry(browser, base, pages, page_name, width):
    context, page = _open(browser, base, pages[page_name], width)
    try:
        problems = page.evaluate(CHECK_JS)["problems"]
        assert not problems, f"{page_name} at {width}: " + " | ".join(problems)
        if SHOTS_ON and width in (390, 1280):
            SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS_DIR / f"{page_name}-{width}.png"), full_page=True)
    finally:
        context.close()


def test_login_works_without_javascript(browser, base, pages):
    context, page = _open(browser, base, pages["login"], 390, javascript=False)
    try:
        assert page.locator("form[action='/login']").first.get_attribute("action") == "/login"
        assert page.locator("#email").is_visible()
        assert page.locator("form button, form input[type=submit]").first.is_visible()
        page.locator(".auth-q > summary").click()
        assert page.locator(".auth-q[open]").count() == 1
        assert page.locator(".auth-q > .auth-lede").is_visible()
    finally:
        context.close()
