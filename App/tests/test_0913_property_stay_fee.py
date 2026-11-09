"""0913: stay fee form stays in its card, council office inputs match, empty signature is one button."""

from __future__ import annotations

import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as, mark_security_prompt_seen

APP_ROOT = Path(__file__).resolve().parents[1]
USERNAME = "0913-stay-fee-host"
WIDTHS = (390, 768, 1280)
SHOTS_DIR = os.environ.get("UBYHOST_SHOTS_DIR", "")


def _read(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


# --- static checks -------------------------------------------------------

def test_council_office_inputs_declare_a_text_type():
    html = _read("app/templates/_stay_fee_fields.html")
    tags = re.findall(r"<input\b[^>]*>", html)
    assert tags, "stay fee fields template has no inputs"
    for tag in tags:
        assert re.search(r'\stype="[a-z]+"', tag), f"input without type: {tag[:120]}"


def test_stay_fee_css_stops_overflow_and_grid_clipping():
    css = _read("app/static/app2.css")
    assert "body.v2 #stay-fee-settings :is(input, select, textarea){max-width:100%;box-sizing:border-box}" in css
    assert "body.v2 #stay-fee-settings :is(.ui-field, .field, .field-row, .grid > *){min-width:0}" in css


def test_empty_signature_hides_the_box_and_keeps_one_button_css():
    css = _read("app/static/app2.css")
    assert ".signature-locked:has(> [data-signature-preview][hidden]){display:none}" in css
    macro = _read("app/templates/_entity_business_fields.html")
    assert "data-signature-open hidden>{{ t('entity.signature.edit' if preview else 'entity.signature.add') }}" in macro


def test_add_signature_label_exists_in_all_languages():
    en = _read("app/host_i18n.py")
    vi = _read("app/host_vi_i18n.py")
    assert '"entity.signature.add": "Add signature"' in en
    assert '"entity.signature.add": "Thêm chữ ký"' in vi


# --- browser checks ------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    import uvicorn

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


def _cleanup() -> None:
    user = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not user:
        return
    owner_id = user["id"]
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def property_session(base):
    db.init_db()
    _cleanup()
    mark_security_prompt_seen(auth.create_account(f"{USERNAME}@example.test", "0913 stay fee host", username=USERNAME))
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity_id = db.insert(
        "legal_entity",
        {"name": "0913 Operator", "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    data = {
        "internal_name": "0913 Test Flat with a long internal name",
        "addr_obec": "Praha",
        "addr_street": "Synthetic",
        "addr_house_no": "12",
        "addr_zip": "11000",
        "legal_entity_id": str(entity_id),
        "permalink_window_days": "2",
        "permalink_reachback_days": "365",
        "passport_photo_policy": "off",
        "active": "on",
    }
    created = client.post("/apartments", data=data, follow_redirects=False)
    assert created.status_code == 303, created.text
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1", (owner_id,)
    )["id"]
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert token
    try:
        yield base, apartment_id, token
    finally:
        _cleanup()


def _open_fee_page(browser_context, base, apartment_id):
    page = browser_context.new_page()
    page.goto(f"{base}/apartments/{apartment_id}?lang=en")
    page.wait_for_selector("#stay-fee-settings", state="attached", timeout=30000)
    page.evaluate("document.querySelector('#sec-fee') && (document.querySelector('#sec-fee').open = true)")
    page.wait_for_timeout(150)
    return page


@pytest.mark.parametrize("width", WIDTHS)
def test_stay_fee_form_stays_inside_its_card(property_session, width):
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    base, apartment_id, token = property_session
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:  # pragma: no cover - environment without Chromium
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": token, "url": base + "/"}])
        page = _open_fee_page(context, base, apartment_id)
        result = page.evaluate(
            """() => {
              const card = document.querySelector('#stay-fee-settings').getBoundingClientRect();
              const bad = [];
              document.querySelectorAll('#stay-fee-settings input, #stay-fee-settings select, #stay-fee-settings textarea')
                .forEach(el => {
                  if (el.type === 'hidden' || el.offsetParent === null) return;
                  const r = el.getBoundingClientRect();
                  if (r.right > card.right + 1 || r.left < card.left - 1) bad.push(el.id || el.name || el.outerHTML.slice(0, 80));
                });
              const root = document.documentElement;
              return { bad, pageOverflow: root.scrollWidth - root.clientWidth };
            }"""
        )
        if SHOTS_DIR:
            out = Path(SHOTS_DIR) / "0913"
            out.mkdir(parents=True, exist_ok=True)
            page.locator("#stay-fee-settings").screenshot(path=str(out / f"stay-fee-{width}.png"))
        context.close()
        browser.close()
    assert result["bad"] == [], f"fields past the card edge at {width}px: {result['bad']}"
    assert result["pageOverflow"] <= 1, f"horizontal page scroll at {width}px"


def test_empty_signature_is_one_add_button(property_session):
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    base, apartment_id, token = property_session
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": token, "url": base + "/"}])
        page = _open_fee_page(context, base, apartment_id)
        block = page.locator("#stay-fee-settings [data-host-signature]")
        assert block.count() == 1
        assert block.locator(".signature-locked").is_hidden()
        # The "?" help tip is a separate control; the signature actions are one button.
        visible_buttons = block.locator(".action-group button:visible")
        assert visible_buttons.count() == 1
        assert visible_buttons.first.inner_text().strip() == "Add signature"
        context.close()
        browser.close()
