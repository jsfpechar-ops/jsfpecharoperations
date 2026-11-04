"""0762: saved services on /payments (name + price) and the one-tap request prefill."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, config, db, payment_services, payments_consent
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

OWNER = "payservices"
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0762"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM settings WHERE key = ?", (f"payment_services:{oid}",))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Service Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    db.insert("legal_entity", {"owner_user_id": oid, "name": "Services s.r.o.",
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


@pytest.fixture
def client(owner, stripe_env):
    c = TestClient(app)
    login_as(c, OWNER, url="/login?lang=cs", follow_redirects=False)
    return c


def test_add_list_remove(owner):
    payment_services.add(owner, "  Úklid   navíc ", 800)
    items = payment_services.list_for(owner)
    assert [i["name"] for i in items] == ["Úklid navíc"]
    assert payment_services.remove(owner, items[0]["id"]) is True
    assert payment_services.list_for(owner) == []


def test_add_rejects_bad_input(owner):
    with pytest.raises(ValueError):
        payment_services.add(owner, "   ", 500)
    with pytest.raises(ValueError):
        payment_services.add(owner, "Úklid", 0)
    for n in range(payment_services.MAX_SERVICES):
        payment_services.add(owner, f"Služba {n}", 100)
    with pytest.raises(ValueError):
        payment_services.add(owner, "Další", 100)


def test_route_add_and_prefill(owner, client):
    r = client.post("/payments/services", data={"name": "Pozdní odjezd", "amount_czk": "500"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "msg=" in r.headers["location"]
    sid = payment_services.list_for(owner)[0]["id"]
    page = client.get(f"/payments?service={sid}")
    assert page.status_code == 200
    assert 'value="500"' in page.text
    assert 'value="Pozdní odjezd"' in page.text
    assert " checked" in page.text


def test_route_delete(owner, client):
    sid = payment_services.add(owner, "Úklid", 800)["id"]
    r = client.post(f"/payments/services/{sid}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert payment_services.list_for(owner) == []
    r = client.post("/payments/services/ffffffff/delete", follow_redirects=False)
    assert r.status_code == 303


def test_service_delete_requires_confirm(owner, client):
    """0762: removing a saved service must not fire on a single click."""
    sid = payment_services.add(owner, "Úklid", 800)["id"]
    page = client.get("/payments?lang=en")
    assert page.status_code == 200
    form = page.text[page.text.index(f'/payments/services/{sid}/delete'):][:400]
    assert "data-confirm" in form
    assert "data-confirm-message=" in form
    assert "Remove this service from your list?" in page.text


# --- browser: 390 px geometry + screenshot (rule 7) ----------------------------

def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_services_fit_a_phone(owner, stripe_env):
    if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
        import playwright.sync_api as sync_api
    else:
        sync_api = pytest.importorskip("playwright.sync_api")
    payment_services.add(owner, "Úklid navíc", 800)
    sid = payment_services.add(owner, "Pozdní odjezd", 500)["id"]
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
            page.goto(f"http://127.0.0.1:{port}/payments?lang=cs&service={sid}#new-request")
            assert page.locator("[data-payment-services] li").count() == 2
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth")
            assert overflow <= 0
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / "services-390.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
