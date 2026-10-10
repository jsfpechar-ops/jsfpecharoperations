"""Browser coverage for the approved property and operator controls."""
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
from playwright import sync_api

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"property-controls-{secrets.token_hex(4)}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Property Controls", role="host", username=username
    )
    linked_id = db.insert("legal_entity", {
        "name": "Linked Operator",
        "seat": "Praha",
        "ico": "12345678",
        "contact_email": "linked@example.test",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    free_id = db.insert("legal_entity", {
        "name": "Free Operator",
        "seat": "Brno",
        "ico": "87654321",
        "contact_email": "free@example.test",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    apartment_id = db.insert("apartment", {
        "internal_name": "Sample Property",
        "owner_user_id": owner_id,
        "legal_entity_id": linked_id,
        "addr_obec": "Praha",
        "addr_house_no": "10",
        "addr_zip": "11000",
        "permalink_token": f"controls{secrets.token_hex(4)}",
        "permalink_pin": "123456",
        "active": 1,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "username": username, "owner": owner_id,
           "linked": linked_id, "free": free_id, "apartment": apartment_id}
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base(host):
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


def _session_cookie(host):
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie


def _capture_review(page, name):
    if os.environ.get("UBYHOST_CAPTURE_PROPERTY_CONTROLS") == "1":
        target = Path("/workspace/generated_images/host-design-application/properties")
        target.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target / f"{name}.png"), full_page=True)


def test_property_and_operator_controls_render_and_work_in_browser(host, base):
    client = host["client"]
    entities_page = client.get("/entities?lang=en").text
    assert 'action="/entities/' + str(host["linked"]) + '/archive"' not in entities_page
    assert "entity_has_properties" not in entities_page
    linked_post = client.post(f"/entities/{host['linked']}/archive", follow_redirects=False)
    assert linked_post.status_code == 303
    assert db.query_one("SELECT archived_at FROM legal_entity WHERE id = ?", (host["linked"],))["archived_at"] is None

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": 1280, "height": 1000}, has_touch=True)
        context.add_cookies([{
            "name": auth.SESSION_COOKIE,
            "value": _session_cookie(host),
            "url": base + "/",
        }])
        page = context.new_page()
        requests = []
        page.on("request", lambda request: requests.append(request) if request.method == "POST" else None)

        for lang in ("en", "cs"):
            page.goto(f"{base}/apartments/new?lang={lang}")
            _capture_review(page, f"address-1280-{lang}")
            assert page.locator(".req-report").count() == 0
            assert page.locator("#addr_street").get_attribute("name") == "addr_street"
            assert page.locator("#addr_house_no").get_attribute("name") == "addr_house_no"
            labels = page.locator("#address .property-address-grid").first.locator("label")
            assert labels.count() == 3
            first_row = page.locator("#address .property-address-grid").first
            label_input_tops = first_row.evaluate("""(row) => [...row.querySelectorAll('.field')].map((field) => {
              const input = field.querySelector('input');
              const label = field.querySelector('label');
              return { input: Math.round(input.getBoundingClientRect().top),
                       labelBottom: Math.round(label.getBoundingClientRect().bottom) };
            })""")
            assert len({item["input"] for item in label_input_tops}) == 1
            second_row = page.locator("#address .property-address-grid").nth(1)
            second_row_tops = second_row.evaluate("""(row) => [...row.querySelectorAll('input')].map((input) =>
              Math.round(input.getBoundingClientRect().top))""")
            assert len(set(second_row_tops)) == 1

            page.goto(f"{base}/entities?lang={lang}")
            _capture_review(page, f"operators-1280-{lang}")
            rows = page.locator(".entities-page tbody tr")
            assert rows.count() == 2
            for row in rows.all():
                for label in ("Edit", "Invoice settings") if lang == "en" else ("Upravit", "Nastavení faktur"):
                    assert row.get_by_role("link", name=label).count() == 1
                assert row.locator(".row-menu-trigger").is_visible()
                assert row.locator(".row-actions").evaluate(
                    "cell => [...cell.children].every(el => getComputedStyle(el).opacity === '1')"
                )

            linked_row = rows.filter(has_text="Linked Operator")
            linked_row.locator(".row-menu-trigger").click()
            menu = page.locator(".row-menu-panel.is-open")
            linked_delete = menu.get_by_role("menuitem", name="Delete" if lang == "en" else "Smazat")
            assert linked_delete.is_visible()
            assert linked_delete.get_attribute("aria-disabled") == "true"
            explanation = menu.locator(".row-menu-explanation")
            assert explanation.is_visible()
            assert explanation.inner_text().strip()
            assert explanation.get_attribute("id") in linked_delete.get_attribute("aria-describedby")
            before = len(requests)
            linked_delete.focus()
            page.keyboard.press("Enter")
            linked_delete.evaluate("element => element.click()")
            assert len(requests) == before
            page.keyboard.press("Escape")

            free_row = rows.filter(has_text="Free Operator")
            free_row.locator(".row-menu-trigger").click()
            free_delete = page.locator(".row-menu-panel.is-open").get_by_role(
                "menuitem", name="Delete" if lang == "en" else "Smazat"
            )
            assert free_delete.is_visible()
            assert free_delete.get_attribute("aria-disabled") is None

        for width in (360, 390):
            page.set_viewport_size({"width": width, "height": 900})
            for lang in ("en", "cs"):
                page.goto(f"{base}/apartments/new?lang={lang}")
                _capture_review(page, f"address-{width}-{lang}")
                fields = page.locator("#address .property-address-grid").first.locator(".field")
                input_tops = fields.evaluate_all("""(fields) => [...fields].map((field) =>
                  Math.round(field.querySelector('input').getBoundingClientRect().top))""")
                assert input_tops == sorted(input_tops)
                assert page.locator("#address").evaluate("el => el.scrollWidth <= el.clientWidth")
                page.goto(f"{base}/entities?lang={lang}")
                _capture_review(page, f"operators-{width}-{lang}")
                linked_row = page.locator(".entities-page tbody tr").filter(has_text="Linked Operator")
                trigger = linked_row.locator(".row-menu-trigger")
                assert trigger.is_visible()
                assert trigger.evaluate("el => getComputedStyle(el.parentElement).opacity") == "1"
                trigger.tap()
                mobile_menu = page.locator(".row-menu-panel.is-open")
                mobile_delete = mobile_menu.get_by_role("menuitem", name="Delete" if lang == "en" else "Smazat")
                assert mobile_menu.locator(".row-menu-explanation").is_visible()
                assert mobile_delete.get_attribute("aria-disabled") == "true"
                page.keyboard.press("Escape")

        page.set_viewport_size({"width": 1280, "height": 1000})
        page.goto(f"{base}/apartments?lang=en")
        assert page.locator('.host-local-nav a[href="/guest-links"]').is_visible()
        assert page.locator('.host-local-nav a[href="/automation"]').is_visible()
        assert page.locator(".host-tools").count() == 0
        page.goto(f"{base}/apartments/{host['apartment']}?lang=en")
        assert page.locator(".host-tools").count() == 0
        assert page.locator('a[href="#communication"]').count() > 0
        browser.close()
