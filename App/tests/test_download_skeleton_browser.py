"""Click host download controls; the navigation skeleton must stay hidden.

Regression for 2026-10-06: attachment URLs without a classic extension blanked
the page for up to 15 seconds. Every control from task 0002 §6 is exercised here.
"""
from __future__ import annotations

import base64
import secrets
import socket
import threading
import time
from datetime import date

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import auth, claim, db, invoices, passport_photos
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from starlette.datastructures import FormData
from tests.conftest import login_as

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)
SIGNATURE = "data:image/png;base64,AAAA"

sync_api = pytest.importorskip("playwright.sync_api")


def _purge_download_owner(owner_id: int) -> None:
    for guest in db.query(
        "SELECT g.id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
        "WHERE r.apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
        (owner_id,),
    ):
        passport_photos.delete_photo(int(guest["id"]))
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
    db.execute(
        "DELETE FROM submission WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id = ?)",
        (owner_id,),
    )
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _session_cookie(username: str) -> str:
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    return token


def _skeleton_visible(page) -> bool:
    return page.evaluate(
        """() => {
          const el = document.querySelector('[data-page-skeleton]');
          return !!(el && !el.hidden);
        }"""
    )


@pytest.fixture(scope="function")
def base():
    db.init_db()
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


@pytest.fixture(scope="function")
def host_world(monkeypatch):
    db.init_db()
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'dl-sk%'"):
        _purge_download_owner(int(row["id"]))
    username = f"dl-sk{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "DL", role="host", username=username)
    entity = db.insert(
        "legal_entity",
        {"name": "DL s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()},
    )
    apartment = db.insert(
        "apartment",
        {
            "internal_name": "DL loft",
            "owner_user_id": owner,
            "legal_entity_id": entity,
            "stay_fee_rate_czk": 50,
            "stay_fee_vs": "123456",
            "stay_fee_authority_name": "Městský úřad",
            "stay_fee_council_account": "19-2000781379/0800",
            "stay_fee_council_iban": "CZ3008000000192000781379",
            "stay_fee_cadence": "monthly",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    now = db.utcnow()
    rid = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": f"dl-{secrets.token_hex(3)}",
            "date_from": "2026-08-10",
            "date_to": "2026-08-14",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest = db.insert(
        "guest",
        {
            "reservation_id": rid,
            "first_name": "Ada",
            "surname": "Guest",
            "birth_date": "01011990",
            "nationality": "DEU",
            "purpose": "10",
            "signature_png": SIGNATURE,
            "created_at": now,
            "updated_at": now,
        },
    )
    passport_photos.save_photo(guest, PNG_BYTES, "image/png")
    submission = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "state": "ok",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 receipt").decode(),
            "error_pdf": base64.b64encode(b"%PDF-1.4 errors").decode(),
            "request_xml": "<request>ok</request>",
            "response_xml": "<response>ok</response>",
            "pseudo_stamp": "STAMP",
        },
    )
    db.update("guest", guest, {"submission_id": submission, "receipt_submission_id": submission})
    db.execute(
        "UPDATE legal_entity SET registry_entry = ?, seat = ? WHERE id = ?",
        ("Zapsán v živnostenském rejstříku", "Praha 1", entity),
    )
    entity_row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity,))
    draft = invoices.build_draft(
        entity_row,
        FormData(
            [
                ("buyer_name", "Buyer"),
                ("item_description", "Stay"),
                ("item_quantity", "1"),
                ("item_unit_price", "100"),
            ]
        ),
        "en",
        today=date.today(),
    )
    draft["legal_entity_id"] = entity
    draft["owner_user_id"] = owner
    invoice_id = invoices.issue(draft, owner)
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    client = TestClient(app)
    login_as(client, username, follow_redirects=False)
    page = client.get(f"/stay-fees/{apartment}?month=2026-08&lang=en", follow_redirects=True)
    assert page.status_code == 200
    token = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
    client.post(
        f"/stay-fees/{apartment}/finalize",
        data={
            "_csrf": token,
            "month": "2026-08",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{guest}": "200",
        },
        follow_redirects=True,
    )
    page = client.get(f"/stay-fees/{apartment}?month=2026-08&lang=en")
    token = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
    client.post(
        f"/stay-fees/{apartment}/adjustment",
        data={
            "_csrf": token,
            "month": "2026-08",
            "direction": "add",
            "mode": "people",
            "people": "2",
            "nights": "3",
            "reason": "Walk-in",
        },
        follow_redirects=True,
    )
    return {
        "username": username,
        "apartment": apartment,
        "guest": guest,
        "submission": submission,
        "invoice": invoice_id,
    }


def _click_download(page, selector: str) -> None:
    page.wait_for_selector(selector, timeout=15000)
    link = page.locator(selector).first
    try:
        with page.expect_download(timeout=8000):
            link.click()
    except sync_api.TimeoutError:
        link.click()
    time.sleep(0.6)
    assert not _skeleton_visible(page), selector


@pytest.fixture(autouse=True)
def _cleanup_download_data(host_world):
    yield
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (host_world["username"],))
    if row:
        _purge_download_owner(int(row["id"]))


def test_every_host_download_button_keeps_the_page_visible(base, host_world):
    session = _session_cookie(host_world["username"])
    apt = host_world["apartment"]
    sub = host_world["submission"]
    inv = host_world["invoice"]
    guest = host_world["guest"]

    clicks = [
        (f"{base}/stay-fees/{apt}?month=2026-08&lang=en", 'a[href*="/pdf"]'),
        (f"{base}/stay-fees/{apt}?month=2026-08&lang=en", 'a[href*="/csv"]'),
        (f"{base}/invoices/{inv}?lang=en", f'a[href="/invoices/{inv}.pdf"]'),
        (f"{base}/submissions/{sub}?lang=en", f'a[href="/submissions/{sub}/receipt.pdf"]'),
        (f"{base}/submissions/{sub}?lang=en", f'a[href="/submissions/{sub}/errors.pdf"]'),
        (f"{base}/submissions?lang=en", 'a[href="/submissions/receipts.zip"]'),
        (f"{base}/guests/{guest}?lang=en", f'a[href="/guests/{guest}/form.pdf"]'),
        (f"{base}/guests/{guest}?lang=en", f'a[href="/guests/{guest}/export.json"]'),
    ]

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()

        for url, selector in clicks:
            page.goto(url, wait_until="networkidle")
            _click_download(page, selector)

        for which in ("request.xml", "response.xml"):
            page.goto(f"{base}/submissions/{sub}?lang=en", wait_until="networkidle")
            href = f"/submissions/{sub}/{which}"
            page.evaluate(
                """(path) => {
                  const details = document.querySelector('details.panel.technical');
                  if (details) details.open = true;
                  const link = document.querySelector(`a[href="${path}"]`);
                  if (!link) throw new Error('missing ' + path);
                  link.click();
                }""",
                href,
            )
            time.sleep(0.6)
            assert not _skeleton_visible(page), href

        # Normal navigation must still work.
        page.goto(f"{base}/?lang=en", wait_until="networkidle")
        page.locator('a[href="/reservations"]').first.click()
        page.wait_for_url("**/reservations**", timeout=15000)
        assert not _skeleton_visible(page)

        context.close()
        browser.close()
