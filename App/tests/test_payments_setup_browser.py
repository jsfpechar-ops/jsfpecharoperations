"""0729: guided payments setup fits a phone."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, config, db, payments_consent
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

OWNER = "paysetup"
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0729"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Setup Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    db.insert("legal_entity", {"owner_user_id": oid, "name": "Setup s.r.o.",
                               "contact_email": f"{OWNER}@example.test",
                               "created_at": db.utcnow()})
    payments_consent.record(oid)
    try:
        yield oid
    finally:
        _cleanup()


@pytest.fixture
def stripe_env(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_local")


# --- browser: 390 px geometry + screenshot (rule 7) ----------------------------

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_payments_setup_fits_a_phone(owner, stripe_env):
    if REQUIRE_BROWSER:
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    try:
        login = TestClient(app)
        login_as(login, OWNER, url="/login?lang=cs", follow_redirects=False)
        token = login.cookies.get(auth.SESSION_COOKIE)
        with sync_api.sync_playwright() as pw:
            browser = pw.chromium.launch(**chromium_launch_kwargs())
            context = browser.new_context(viewport={"width": 390, "height": 844})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": token,
                                  "url": f"http://127.0.0.1:{port}"}])
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/payments?lang=cs")
            assert page.locator("[data-payments-setup] li").count() == 4
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 0
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / "payments-setup-390.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
