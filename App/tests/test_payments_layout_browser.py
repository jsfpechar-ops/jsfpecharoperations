"""0908: /payments and /payments/new fit a phone in every state.

Browser checks (Chromium, 0 skipped with UBYHOST_REQUIRE_BROWSER=1):
no horizontal scroll, no element outside the viewport, 44 px targets at
390 px and below, at most one primary button per group. Screenshots at 390 px
go to docs/tasks/screenshots-0908/.
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

from app import auth, config, db, payment_request, payment_services, payments_consent
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as
from test_payments_dashboard import _set_state

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0908"
REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
WIDTHS = (320, 390, 768, 1024, 1280, 1440)
PAGES = (("/payments", "payments"), ("/payments/new", "payments-new"))

OVERFLOW_JS = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
OUTSIDE_JS = """() => {
  const W = document.documentElement.clientWidth; const out = [];
  for (const el of document.querySelectorAll('.ui-body *')) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && (r.right > W + 1 || r.left < -1)) {
      out.push(el.tagName.toLowerCase() + '.' + String(el.className).slice(0, 40) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
    }
  }
  return out;
}"""
SMALL_TARGETS_JS = """() => {
  const out = [];
  const sel = '.ui-body a, .ui-body button, .ui-body select, .ui-body .ui-chip, .ui-body input:not([type=radio]):not([type=checkbox])';
  for (const el of document.querySelectorAll(sel)) {
    if (el.offsetParent === null || el.classList.contains('sr-only')) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.height < 44) {
      out.push(((el.textContent || el.name || el.tagName).trim().slice(0, 40)) + ' ' + Math.round(r.height));
    }
  }
  return out;
}"""
BODY_PRIMARY_JS = "document.querySelectorAll('.ui-body .ui-btn-primary').length"
HEADER_PRIMARY_JS = "document.querySelectorAll('[data-list-actions] .ui-btn-primary').length"


def _cleanup(username):
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if not row:
        return
    oid = row["id"]
    for table in ("payment_request", "payment_service", "legal_entity", "stripe_account", "audit"):
        try:
            db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (oid,))
        except Exception:
            pass
    try:
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))
    except Exception:
        pass


def _make_owner(state):
    username = f"paylay{secrets.token_hex(3)}"
    db.init_db()
    auth.create_account(f"{username}@example.test", "Layout Host", username=username)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"]
    db.insert("legal_entity", {"owner_user_id": oid, "name": "Layout s.r.o.",
                               "contact_email": f"{username}@example.test",
                               "created_at": db.utcnow()})
    payments_consent.record(oid)
    if state in ("complete", "rows"):
        _set_state(oid, "complete")
    if state == "rows":
        payment_services.add(oid, "Úklid navíc", 800)
        payment_request.create(oid, reason="damage", amount_czk=2500, rail="card",
                               expires_at="2026-12-27")
    return username


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize("state", ["setup", "complete", "rows"])
def test_payments_pages_fit_every_width(state, monkeypatch):
    if REQUIRE_BROWSER:
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")
    username = _make_owner(state)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    problems = []
    try:
        login = TestClient(app)
        login_as(login, username, url="/login?lang=cs", follow_redirects=False)
        token = login.cookies.get(auth.SESSION_COOKIE)
        with sync_api.sync_playwright() as pw:
            browser = pw.chromium.launch(**chromium_launch_kwargs())
            context = browser.new_context(viewport={"width": 390, "height": 844})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": token,
                                  "url": f"http://127.0.0.1:{port}"}])
            page = context.new_page()
            SHOTS.mkdir(parents=True, exist_ok=True)
            for path, slug in PAGES:
                for width in WIDTHS:
                    page.set_viewport_size({"width": width, "height": 844})
                    page.goto(f"http://127.0.0.1:{port}{path}?lang=cs")
                    where = f"{state} {path} {width}"
                    if page.evaluate(OVERFLOW_JS) > 0:
                        problems.append(f"{where}: horizontal scroll")
                    outside = page.evaluate(OUTSIDE_JS)
                    if outside:
                        problems.append(f"{where}: element outside the viewport: {outside[:3]}")
                    if width <= 390:
                        small = page.evaluate(SMALL_TARGETS_JS)
                        if small:
                            problems.append(f"{where}: targets under 44 px: {small[:5]}")
                    if page.evaluate(BODY_PRIMARY_JS) > 1:
                        problems.append(f"{where}: more than one primary button in the body")
                    if page.evaluate(HEADER_PRIMARY_JS) > 1:
                        problems.append(f"{where}: more than one primary button in the header")
                    if width == 390:
                        page.screenshot(path=str(SHOTS / f"{slug}-{state}-390.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        _cleanup(username)
    assert not problems, "\n".join(problems)
