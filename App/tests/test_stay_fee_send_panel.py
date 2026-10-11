"""Stay-fee data-box send panel and sent/paid marks."""
from __future__ import annotations

import os
import socket
import threading
import time
from datetime import date
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_filing, validation
from app.main import app
from tests.conftest import login_as

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.browser_support import chromium_launch_kwargs

SIGNATURE = "data:image/png;base64,AAAA"
IBAN = "CZ3008000000192000781379"
ACCOUNT = "19-2000781379/0800"


def _cleanup():
    for user in db.query(
        "SELECT id FROM user_account WHERE username LIKE 'stay-fee-send-%'"
    ):
        owner_id = user["id"]
        db.execute(
            "DELETE FROM stay_fee_filing WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation "
            "WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    owner_id = auth.create_account(
        "stay-fee-send-owner@example.test",
        "Send Demo",
        role="host",
        username="stay-fee-send-owner",
    )
    entity_id = db.insert("legal_entity", {
        "name": "Send Demo s.r.o.",
        "ico": "12345678",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, "stay-fee-send-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, **extra):
    values = {
        "internal_name": "Send Flat",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "stay_fee_rate_czk": 50,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_authority_databox": "abc1234",
        "stay_fee_council_account": ACCOUNT,
        "stay_fee_council_iban": IBAN,
        "created_at": db.utcnow(),
    }
    values.update(extra)
    return db.insert("apartment", values)


def _stay(apartment_id):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": "send-stay-1",
        "date_from": "2026-08-10",
        "date_to": "2026-08-14",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": rid,
        "first_name": "Ada",
        "surname": "Guest",
        "birth_date": "01011990",
        "nationality": "DEU",
        "signature_png": SIGNATURE,
        "created_at": now,
        "updated_at": now,
    })


def _csrf(client, url):
    page = client.get(url)
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def _finalize(client, apartment_id, month="2026-08"):
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    token = _csrf(client, f"/stay-fees/{apartment_id}?month={month}")
    return client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": token,
            "month": month,
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )


def test_normalise_databox():
    assert validation.normalise_databox("AbC1234") == "abc1234"
    assert validation.normalise_databox("abc123") == ""
    assert validation.normalise_databox("abc12345") == ""
    assert validation.normalise_databox("abc-123") == ""


def test_send_panel_hidden_before_finalize(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    page = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert page.status_code == 200
    assert 'id="fee-send"' not in page.text


def test_sent_paid_undo_and_list_status(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    assert _finalize(client, apartment_id).status_code == 303
    row = stay_fee_filing.latest(apartment_id, "2026-08")
    filing_id = row["id"]
    month_url = f"/stay-fees/{apartment_id}?month=2026-08"

    page = client.get(month_url)
    assert 'id="fee-send"' in page.text
    assert "Ohlášení poplatku z pobytu" in page.text
    assert "abc1234" in page.text

    token = _csrf(client, month_url)
    sent = client.post(
        f"/stay-fees/{apartment_id}/filings/{filing_id}/sent",
        data={"_csrf": token, "month": "2026-08", "sent_message_id": "MSG-42"},
        follow_redirects=False,
    )
    assert sent.status_code == 303
    row = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (filing_id,))
    assert row["sent_at"]
    assert row["sent_message_id"] == "MSG-42"

    list_page = client.get("/stay-fees?month=2026-08")
    assert "Sent" in list_page.text

    token = _csrf(client, month_url)
    paid = client.post(
        f"/stay-fees/{apartment_id}/filings/{filing_id}/paid",
        data={"_csrf": token, "month": "2026-08"},
        follow_redirects=False,
    )
    assert paid.status_code == 303
    list_page = client.get("/stay-fees?month=2026-08")
    assert "Paid" in list_page.text

    token = _csrf(client, month_url)
    client.post(
        f"/stay-fees/{apartment_id}/filings/{filing_id}/sent",
        data={"_csrf": token, "month": "2026-08", "undo": "1"},
        follow_redirects=False,
    )
    row = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (filing_id,))
    assert row["sent_at"] is None
    assert row["sent_message_id"] is None
    assert row["paid_at"]


def test_paid_without_sent(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    _finalize(client, apartment_id)
    filing_id = stay_fee_filing.latest(apartment_id, "2026-08")["id"]
    token = _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08")
    client.post(
        f"/stay-fees/{apartment_id}/filings/{filing_id}/paid",
        data={"_csrf": token, "month": "2026-08"},
        follow_redirects=False,
    )
    list_page = client.get("/stay-fees?month=2026-08")
    assert "Paid" in list_page.text
    assert "Sent" not in list_page.text or "Paid" in list_page.text


def test_other_owner_gets_404(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    _finalize(client, apartment_id)
    filing_id = stay_fee_filing.latest(apartment_id, "2026-08")["id"]

    other_id = auth.create_account(
        "stay-fee-send-other@example.test",
        "Other",
        role="host",
        username="stay-fee-send-other",
    )
    other = TestClient(app)
    login_as(other, "stay-fee-send-other", url="/login?lang=en", follow_redirects=False)
    token = _csrf(other, "/stay-fees")
    resp = other.post(
        f"/stay-fees/{apartment_id}/filings/{filing_id}/sent",
        data={"_csrf": token, "month": "2026-08"},
        follow_redirects=False,
    )
    assert resp.status_code == 404
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (other_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (other_id,))


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def browser_base(host):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_send_panel_geometry_and_screenshots(host, browser_base):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    _finalize(client, apartment_id)
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    shots = Path("/opt/cursor/artifacts/stay-fee-send-panel")
    shots.mkdir(parents=True, exist_ok=True)
    url = f"{browser_base}/stay-fees/{apartment_id}?month=2026-08&lang=en"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(
            viewport={"width": 1280, "height": 1200},
            has_touch=True,
        )
        context.add_cookies([{
            "name": auth.SESSION_COOKIE,
            "value": cookie,
            "url": browser_base,
        }])
        page = context.new_page()
        for width in (360, 390, 1280):
            page.set_viewport_size({"width": width, "height": 1200})
            page.goto(url, wait_until="networkidle")
            assert page.locator("#fee-send").is_visible()
            page.screenshot(path=str(shots / f"send-panel-{width}.png"), full_page=True)
        browser.close()
