"""0082: fee list and report detail under the shared host layout (order, visibility, geometry)."""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0082-evidence"
MONTH = "2026-08"
IBAN = "CZ3008000000192000781379"
ACCOUNT = "19-2000781379/0800"
SIGNATURE = "data:image/png;base64,AAAA"


@pytest.fixture(scope="module")
def fee_host():
    db.init_db()
    username = f"fee-nav-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Fee Nav QA", role="host", username=username)
    now = db.utcnow()
    entity_id = db.insert("legal_entity", {
        "name": "Fee Nav QA s.r.o.", "owner_user_id": owner_id, "created_at": now,
    })

    def prop(name, city, **extra):
        values = {
            "internal_name": name, "owner_user_id": owner_id, "legal_entity_id": entity_id,
            "addr_obec": city, "active": 1, "created_at": now,
        }
        values.update(extra)
        return db.insert("apartment", values)

    full = prop(
        "Synthetic Flat with a long property name for wrapping", "Praha 3",
        stay_fee_rate_czk=50, stay_fee_cadence="monthly", stay_fee_vs="123456",
        stay_fee_authority_name="Úřad městské části Praha 3 - odbor správních agend a místních poplatků",
        stay_fee_council_account=ACCOUNT, stay_fee_council_iban=IBAN,
    )
    incomplete = prop("Synthetic Incomplete Flat", "Brno", stay_fee_rate_czk=50, stay_fee_cadence="monthly")
    off = prop("Synthetic Rate-Off Flat", "Ostrava")
    full_guest = 0
    for apartment_id in (full, incomplete):
        reservation_id = db.insert("reservation", {
            "apartment_id": apartment_id, "uid": f"fee-nav-{apartment_id}",
            "date_from": "2026-08-10", "date_to": "2026-08-13", "status": "active",
            "created_at": now, "updated_at": now,
        })
        guest_id = db.insert("guest", {
            "reservation_id": reservation_id, "first_name": "Sample", "surname": "Guest",
            "birth_date": "01011990", "nationality": "DEU", "signature_png": SIGNATURE,
            "created_at": now, "updated_at": now,
        })
        if apartment_id == full:
            full_guest = guest_id
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    csrf = re.search(r'<meta name="csrf-token" content="([^"]+)"', client.get("/stay-fees").text).group(1)
    sealed = client.post(
        f"/stay-fees/{full}/finalize",
        data={"_csrf": csrf, "month": MONTH, "confirm_collected": "1", f"collected_{full_guest}": "150"},
        follow_redirects=False,
    )
    assert sealed.status_code == 303
    yield {"client": client, "full": full, "incomplete": incomplete, "off": off}


@pytest.fixture(scope="module")
def fee_base(fee_host):
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
        pytest.fail("the fee navigation test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _order(html: str, *ids: str) -> list[int]:
    return [html.index(f'id="{item}"') for item in ids]


def test_list_has_status_column_and_open_report_link(fee_host):
    page = fee_host["client"].get(f"/stay-fees?month={MONTH}").text
    assert 'id="fee-list-summary"' in page
    assert "2 of 3 properties set up" in page
    assert f'href="/stay-fees/{fee_host["full"]}?month={MONTH}"' in page
    assert "Open report" in page
    # Not set up shows a state and an action instead of blank totals; setup stays one
    # link, now straight to the one fee editor with the way back to this list (0077).
    assert (
        f'href="/apartments/{fee_host["off"]}?view=settings&amp;section=reporting'
        f'&amp;return_to=%2Fstay-fees%3Fmonth%3D{MONTH}#stay-fee-settings"'
    ) in page
    # No legacy fee-setup URL (0099: the shared setup notice may link /setup).
    assert not re.search(r"/stay-fees/\d+/setup", page)
    assert page.count("Not set up") >= 1


def test_blockers_come_right_after_totals_and_keep_fix_link(fee_host):
    incomplete = fee_host["incomplete"]
    page = fee_host["client"].get(f"/stay-fees/{incomplete}?month={MONTH}").text
    assert 'id="fee-blockers"' in page
    assert (
        f'href="/apartments/{incomplete}?view=settings&amp;section=reporting'
        f'&amp;return_to=%2Fstay-fees%2F{incomplete}%3Fmonth%3D{MONTH}#stay-fee-settings"'
    ) in page
    assert page.index('class="stay-metrics') < page.index('id="fee-blockers"') < page.index('id="guests"')
    assert page.index('id="guests"') < page.index('id="fee-adjust"')
    # Save stays disabled while blocked; the adjustment and decision forms keep their action and CSRF.
    assert f'action="/stay-fees/{incomplete}/adjustment"' in page
    assert "<details" not in page[page.index('id="guests"'):]


def test_frozen_report_order_and_forms(fee_host):
    full = fee_host["full"]
    page = fee_host["client"].get(f"/stay-fees/{full}?month={MONTH}").text
    assert 'id="fee-blockers"' not in page
    assert 'id="fee-adjust"' not in page
    assert _order(page, "fee-send", "payment", "guests") == sorted(_order(page, "fee-send", "payment", "guests"))
    assert f'href="/stay-fees/{full}/pdf?month={MONTH}"' in page
    assert f'href="/stay-fees/{full}/csv?month={MONTH}"' in page
    # Manual records are labelled as the host's own, and keep their forms.
    assert "Your records" in page
    for action in ("sent", "paid"):
        assert re.search(rf'action="/stay-fees/{full}/filings/\d+/{action}"', page)
    # The variable-symbol hint is a ? help, wired to the input.
    assert 'aria-describedby="fee-vs-help"' in page and 'id="fee-vs-help"' in page
    # No folded decision form and no data-box shortcut.
    assert "<details" not in page[page.index('id="guests"'):]
    assert "mojedatovaschranka" not in page


def _browser(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for fee navigation geometry coverage")


def test_fee_pages_fit_and_keep_one_lane(fee_host, fee_base):
    cookie = fee_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    capture = os.environ.get("UBYHOST_CAPTURE_0082") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    pages = {
        "list": f"/stay-fees?month={MONTH}",
        "detail-blocked": f"/stay-fees/{fee_host['incomplete']}?month={MONTH}",
        "detail-saved": f"/stay-fees/{fee_host['full']}?month={MONTH}",
    }
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": fee_base + "/"}])
        page = context.new_page()
        for locale in ("en", "cs"):
            for width in (360, 390, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                for key, path in pages.items():
                    page.goto(f"{fee_base}{path}&lang={locale}")
                    page.wait_for_load_state("networkidle")
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (key, width, locale)
                    for control in page.locator(".host-workspace main a.btn, .host-workspace main button.btn").all():
                        if not control.is_visible():
                            continue
                        box = control.bounding_box()
                        assert box and box["x"] >= -1 and box["x"] + box["width"] <= width + 1, (key, width)
                    if key != "list":
                        left = page.locator(".page-header").bounding_box()
                        stats = page.locator(".stay-metrics").bounding_box()
                        assert abs(left["x"] - stats["x"]) <= 40, (key, width)
                    if key == "detail-saved":
                        assert page.locator("#guests details").count() == 0
                    if capture:
                        page.screenshot(path=str(EVIDENCE / f"{key}-{locale}-{width}.png"), full_page=True)
        context.close()
        browser.close()
