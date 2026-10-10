"""Mixed-status guest-link actions and shared dashboard row-menu coverage."""
from __future__ import annotations

import os
import secrets
import socket
import threading
from datetime import timedelta
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, claim, db, demo, reporting
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


@pytest.fixture(scope="module")
def stay_actions_host():
    db.init_db()
    username = f"stay-actions-{secrets.token_hex(4)}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Stay Actions QA", role="host", username=username
    )
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": "Stay Actions QA s.r.o.", "seat": "Praha", "ico": "12345678",
        "contact_email": "actions@example.test", "owner_user_id": owner_id,
        "created_at": now,
    })

    def apartment(name, token, mode="manual"):
        return db.insert("apartment", {
            "legal_entity_id": entity_id, "owner_user_id": owner_id,
            "internal_name": name, "permalink_token": token,
            "permalink_pin": "123456", "automation_mode": mode,
            "submit_after_hours": 24, "active": 1, "created_at": now,
        })

    valid_apartment = apartment("Actions Flat", f"actions{secrets.token_hex(5)}")
    missing_apartment = apartment("No Link Flat", None)
    preview_apartment = apartment(demo.DEMO_APARTMENT, f"preview{secrets.token_hex(4)}")
    scheduled_apartment = apartment("Scheduled Flat", f"scheduled{secrets.token_hex(4)}", "scheduled")
    today = claim.prague_today()
    ids = {}

    def stay(key, apartment_id=valid_apartment, offset=1, expected=1):
        ids[key] = db.insert("reservation", {
            "apartment_id": apartment_id, "source": "manual",
            "uid": f"actions-{key}-{secrets.token_hex(4)}",
            "date_from": (today + timedelta(days=offset)).isoformat(),
            "date_to": (today + timedelta(days=offset + 2)).isoformat(),
            "status": "active", "expected_guests_override": expected,
            "created_at": now, "updated_at": now,
        })
        return ids[key]

    def guest(reservation_id, key, submit_state=reporting.PENDING):
        db.insert("guest", {
            "reservation_id": reservation_id, "surname": "SAMPLE", "first_name": key.upper(),
            "birth_date": "01011990", "nationality": "GBR", "doc_number": f"P-{key}",
            "res_street": "Street 1", "res_city": "London", "res_country": "GBR",
            "purpose": "10", "is_lead": 1, "entered_by": "host",
            "signature_png": reporting.IMPORTED_SIGNATURE, "signed_at": now,
            "identity_verified_at": now, "submit_state": submit_state,
            "submitted_at": now if submit_state == reporting.SENT else None,
            "created_at": now, "updated_at": now,
        })

    stay("waiting", expected=None)
    stay("incomplete", offset=3)
    for key, submit_state in (
        ("ready", reporting.PENDING),
        ("reported", reporting.SENT),
        ("failed", reporting.ERROR),
    ):
        reservation_id = stay(key, offset=5 + len(ids))
        guest(reservation_id, key, submit_state)
    preview_id = stay("preview", apartment_id=preview_apartment, offset=13)
    guest(preview_id, "preview")
    scheduled_id = stay("scheduled", apartment_id=scheduled_apartment, offset=14)
    guest(scheduled_id, "scheduled")
    stay("missing-token", apartment_id=missing_apartment, offset=15, expected=None)

    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "entity": entity_id,
           "apartments": (valid_apartment, missing_apartment, preview_apartment, scheduled_apartment), "ids": ids}
    db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN (?, ?, ?, ?))", (valid_apartment, missing_apartment, preview_apartment, scheduled_apartment))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (?, ?, ?, ?)", (valid_apartment, missing_apartment, preview_apartment, scheduled_apartment))
    db.execute("DELETE FROM apartment WHERE id IN (?, ?, ?, ?)", (valid_apartment, missing_apartment, preview_apartment, scheduled_apartment))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def stay_actions_base(stay_actions_host):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    import time
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the stay-action test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _browser(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for stay action geometry coverage")


def test_stays_guest_link_copy_is_status_independent_and_token_guarded(stay_actions_host, stay_actions_base):
    shots = Path(__file__).resolve().parents[2] / "generated_images" / "0041-evidence"
    shots.mkdir(parents=True, exist_ok=True)
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    valid_ids = {key: value for key, value in stay_actions_host["ids"].items() if key != "missing-token"}
    expected_statuses = {
        "waiting": "awaiting_guest", "incomplete": "incomplete", "ready": "ready",
        "reported": "reported", "failed": "failed", "preview": "demo_preview",
        "scheduled": "ready_scheduled",
    }
    expected_tones = {
        "waiting": "teal", "incomplete": "amber", "ready": "blue",
        "reported": "green", "failed": "red", "preview": "grey", "scheduled": "blue",
    }
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        context.add_init_script("""
          window.__copyWrites = [];
          Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
            writeText: value => { window.__copyWrites.push(value); return Promise.resolve(); }
          }});
        """)
        page = context.new_page()
        for locale in ("en", "cs"):
            for width in (360, 390, 1280, 1920):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(f"{stay_actions_base}/reservations?range=all&lang={locale}")
                page.wait_for_load_state("networkidle")
                for key, reservation_id in valid_ids.items():
                    row = page.locator(f'tr[data-href^="/reservations/{reservation_id}?"]')
                    assert row.count() == 1
                    status_pill = row.locator("td.stay-col-reporting .pill")
                    assert status_pill.count() == 1
                    assert f"pill {expected_tones[key]}" in (status_pill.get_attribute("class") or ""), (key, expected_statuses[key], status_pill.get_attribute("class"))
                    copy = row.locator('button[data-copy]')
                    assert copy.count() == 1, f"Copy missing on {key} ({expected_statuses[key]}) {locale}/{width}"
                    source_id = copy.get_attribute("data-copy")
                    source_value = page.locator(f"#{source_id}").input_value()
                    guest_link = row.locator(f'a[href^="/l/"][target="_blank"]')
                    assert guest_link.count() == 1
                    assert source_value.endswith(guest_link.get_attribute("href")) or guest_link.get_attribute("href") in source_value
                    assert "/l/" in source_value and source_value.endswith(f"/{reservation_id}")
                no_token = page.locator(f'tr[data-href^="/reservations/{stay_actions_host["ids"]["missing-token"]}?"]')
                assert no_token.count() == 1
                assert no_token.locator('button[data-copy]').count() == 0
                assert no_token.locator('a[href^="/l/"][target="_blank"]').count() == 0

                ready_row = page.locator(f'tr[data-href^="/reservations/{stay_actions_host["ids"]["ready"]}?"]')
                send = ready_row.locator(".row-action-send")
                copy = ready_row.locator('button[data-copy]')
                trigger = ready_row.locator(".row-menu-trigger")
                assert send.is_visible()
                boxes = [control.bounding_box() for control in (send, copy, trigger)]
                expected_height = 44 if width <= 390 else 42
                assert all(abs(box["height"] - expected_height) <= 1 for box in boxes), boxes
                assert max(box["y"] for box in boxes) - min(box["y"] for box in boxes) <= 2, boxes
                assert all(box["x"] >= -1 and box["x"] + box["width"] <= width + 1 for box in boxes), boxes
                for left, right in zip(boxes, boxes[1:]):
                    assert left["x"] + left["width"] <= right["x"] + 1, boxes
                if locale == "en" and width == 360:
                    ready_source = page.locator(f"#{copy.get_attribute('data-copy')}")
                    ready_link = ready_row.locator('a[href^="/l/"][target="_blank"]').get_attribute("href")
                    page.evaluate("window.scrollTo(0, 0)")
                    copy.click()
                    page.wait_for_function("window.__copyWrites.length === 1")
                    assert page.evaluate("window.__copyWrites[0]") == ready_source.input_value()
                    assert page.evaluate("window.__copyWrites[0]").endswith(ready_link)
                    page.locator("body").click(position={"x": 20, "y": 20})

                ready_row.locator("td.row-actions").screenshot(path=str(shots / f"stays-actions-{locale}-{width}.png"))
        context.close()
        browser.close()
