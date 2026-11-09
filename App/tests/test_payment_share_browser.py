"""0761: share page fits a phone."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, config, db, payment_links, payment_request, payments_consent
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as, mark_security_prompt_seen

OWNER = "payshare"
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0761"
LINK = "https://buy.stripe.com/test_share_long_link_1234567890"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM payment_request WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    mark_security_prompt_seen(auth.create_account(f"{OWNER}@example.test", "Share Host", username=OWNER))
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    db.insert("legal_entity", {"owner_user_id": oid, "name": "Share s.r.o.",
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


def test_payment_share_fits_a_phone(owner, stripe_env, monkeypatch):
    if REQUIRE_BROWSER:
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    now = db.utcnow()
    db.insert(
        "stripe_account",
        {
            "owner_user_id": owner,
            "stripe_account_id": "acct_share",
            "mode": config.STRIPE_MODE,
            "onboarding_state": "complete",
            "charges_enabled": 1,
            "payouts_enabled": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    rid = payment_request.create(
        owner, reason="cleaning", amount_czk=800, rail="card",
        expires_at="2026-11-27", guest_email="",
    )
    db.execute(
        "UPDATE payment_request SET stripe_payment_link_id = 'plink_x', status = 'sent' WHERE id = ?",
        (rid,),
    )
    monkeypatch.setattr(payment_links, "send", lambda _rid: LINK)

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
            page.goto(f"http://127.0.0.1:{port}/payments/requests/{rid}/share?lang=cs")
            assert page.locator("[data-payment-share] input").is_visible()
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 0
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / "share-390.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
