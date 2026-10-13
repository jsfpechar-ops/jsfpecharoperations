"""Browser coverage for the shared contextual ? help tip (0093 foundation)."""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

TIP = "#permalink_window_days-help"
BTN = "[aria-controls='permalink_window_days-help']"
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0093-evidence"


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"help-tip-{secrets.token_hex(4)}"
    owner_id = auth.create_account(
        f"{username}@example.test", "Help Tip", role="host", username=username
    )
    apartment_id = db.insert("apartment", {
        "internal_name": "Sample Property",
        "owner_user_id": owner_id,
        "addr_obec": "Praha",
        "addr_house_no": "10",
        "addr_zip": "11000",
        "permalink_token": f"help{secrets.token_hex(4)}",
        "permalink_pin": "123456",
        "active": 1,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "apartment": apartment_id}
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def base(host):
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
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _context(browser, host, base, width, **kwargs):
    context = browser.new_context(viewport={"width": width, "height": 800}, **kwargs)
    cookie = host["client"].cookies.get(auth.SESSION_COOKIE)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    return context


def _open_page(context, base, host, lang):
    page = context.new_page()
    page.goto(f"{base}/apartments/{host['apartment']}?view=settings&section=guests&lang={lang}")  # 0094
    page.evaluate(
        "(() => { let d = document.querySelector('#permalink_window_days').closest('details');"
        " while (d) { d.open = true; d = d.parentElement.closest('details'); } })()"
    )
    page.locator(BTN).scroll_into_view_if_needed()
    return page


def _inside_viewport(page):
    box = page.locator(TIP).bounding_box()
    width = page.evaluate("document.documentElement.clientWidth")
    return box["x"] >= 0 and box["x"] + box["width"] <= width + 0.5


def _capture(page, name):
    if os.environ.get("UBYHOST_CAPTURE_0093") == "1":
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{name}.png"))


def _active_controls(page):
    return page.evaluate("document.activeElement.getAttribute('aria-controls')")


def test_help_tip_interactions_aria_and_fit(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang, name in (("en", "Help"), ("cs", "Nápověda")):
            context = _context(browser, host, base, 1280)
            page = _open_page(context, base, host, lang)
            button = page.locator(BTN)
            tip = page.locator(TIP)

            # aria wiring and unique ids; the old always-visible hint is gone
            assert button.get_attribute("type") == "button"
            assert button.get_attribute("aria-label") == name
            assert button.get_attribute("aria-expanded") == "false"
            assert tip.get_attribute("role") == "tooltip"
            ids = page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id)")
            assert len(ids) == len(set(ids))
            assert tip.is_hidden()
            assert page.locator("label[for='permalink_window_days']").count() == 1

            # hover opens, leaving closes
            button.hover()
            tip.wait_for(state="visible")
            assert button.get_attribute("aria-expanded") == "true"
            page.mouse.move(5, 5)
            tip.wait_for(state="hidden")
            assert button.get_attribute("aria-expanded") == "false"

            # keyboard focus opens, Esc closes and keeps focus on the trigger
            page.locator("#permalink_window_days").focus()
            page.keyboard.press("Shift+Tab")
            assert _active_controls(page) == "permalink_window_days-help"
            tip.wait_for(state="visible")
            page.keyboard.press("Escape")
            tip.wait_for(state="hidden")
            assert _active_controls(page) == "permalink_window_days-help"

            # click pins the tip open, outside click closes, second click toggles
            button.click()
            tip.wait_for(state="visible")
            page.mouse.move(5, 5)
            page.wait_for_timeout(300)
            assert tip.is_visible()
            assert _inside_viewport(page)
            _capture(page, f"help-1280-{lang}")
            page.mouse.click(5, 5)
            tip.wait_for(state="hidden")
            button.click()
            tip.wait_for(state="visible")
            button.click()
            tip.wait_for(state="hidden")

            # clicking the trigger never submits the form
            posts = []
            page.on("request", lambda r: posts.append(r) if r.method == "POST" else None)
            button.click()
            assert posts == []
            context.close()

            # touch: tap opens, tap outside closes; fits at narrow widths
            for width in (360, 390):
                touch = _context(browser, host, base, width, has_touch=True)
                tpage = _open_page(touch, base, host, lang)
                tpage.locator(BTN).tap()
                tpage.locator(TIP).wait_for(state="visible")
                assert _inside_viewport(tpage), f"tip overflows at {width}"
                assert tpage.evaluate(
                    "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
                )
                _capture(tpage, f"help-{width}-{lang}")
                tpage.touchscreen.tap(width - 4, 4)
                tpage.locator(TIP).wait_for(state="hidden")
                touch.close()
        browser.close()


def test_help_tip_target_size_and_no_js_reachability(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        touch = _context(browser, host, base, 390, has_touch=True)
        page = _open_page(touch, base, host, "en")
        hit = page.locator(BTN).evaluate("""(el) => {
          const inset = Math.abs(parseFloat(getComputedStyle(el, '::after').top));
          const box = el.getBoundingClientRect();
          return [box.width + 2 * inset, box.height + 2 * inset];
        }""")
        assert hit[0] >= 44 and hit[1] >= 44
        touch.close()

        html = host["client"].get(f"/apartments/{host['apartment']}?view=settings&section=guests&lang=en").text
        html = re.sub(r"<details", "<details open", html)
        html = html.replace("<head>", f'<head><base href="{base}/">', 1)
        no_js = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 800})
        page = no_js.new_page()
        page.set_content(html, wait_until="load")
        tip = page.locator(TIP)
        assert tip.count() == 1 and tip.is_hidden()
        page.locator(BTN).focus()
        assert tip.is_visible()
        assert "stay-specific link" in tip.inner_text()
        no_js.close()
        browser.close()


# --- 0093 pass: host-wide check over the converted pages -------------------------------

def _host_pages(host):
    from tests.invoice_stay_helper import make_stay

    owner = host["owner"]
    entity = db.insert("legal_entity", {
        "name": "Help s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    stay = make_stay(owner, entity_id=entity)
    db.insert("apartment", {
        "internal_name": "Archived Sample", "owner_user_id": owner, "active": 0,
        "permalink_token": f"arch{secrets.token_hex(4)}", "archived_at": db.utcnow(),
        "created_at": db.utcnow(),
    })
    pages = [
        ("property-create", "/apartments/new", "#property-create-address-help"),
        ("property-guests", f"/apartments/{host['apartment']}?view=settings&section=guests", None),
        ("stay-detail", f"/reservations/{stay}", "#guest_email-help"),
        ("invoice-builder", f"/invoices/new?reservation_id={stay}&entity={entity}", "#due_date-help"),
        ("entities", f"/entities?edit={entity}", None),
        ("settings", "/settings", None),
        ("archive", "/settings/archived", "#archive-properties-help"),
    ]
    return pages, entity


def _drop_host_pages(host, entity):
    from tests.invoice_stay_helper import drop_stays

    drop_stays(host["owner"])
    db.execute("DELETE FROM apartment WHERE owner_user_id = ? AND internal_name = ?", (host["owner"], "Archived Sample"))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity,))


@pytest.mark.parametrize("width", [360, 390, 1280])
def test_host_wide_help_tips_are_wired_reachable_and_fit(host, base, width):
    pages, entity = _host_pages(host)
    seen = 0
    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            for lang in ("en", "cs"):
                context = _context(browser, host, base, width)
                for name, path, must_have in pages:
                    page = context.new_page()
                    sep = "&" if "?" in path else "?"
                    page.goto(f"{base}{path}{sep}lang={lang}")
                    ids = page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id)")
                    assert len(ids) == len(set(ids)), (name, lang)
                    if must_have:
                        assert page.locator(must_have).count() == 1, (name, lang, must_have)
                    assert page.locator("a.help-link").count() == 0, name
                    _capture(page, f"{name}-{width}-{lang}")
                    buttons = page.locator(".help-tip-btn")
                    for index in range(buttons.count()):
                        button = buttons.nth(index)
                        target = button.get_attribute("aria-controls")
                        assert target and page.locator(f"#{target}.help-tip-body").count() == 1, (name, target)
                        if not button.is_visible():
                            continue  # inside a closed menu or a hidden tab
                        button.scroll_into_view_if_needed()
                        button.focus()
                        tip = page.locator(f"#{target}")
                        tip.wait_for(state="visible")
                        assert page.evaluate("document.activeElement.getAttribute('aria-controls')") == target
                        box = tip.bounding_box()
                        client_width = page.evaluate("document.documentElement.clientWidth")
                        assert box["x"] >= -0.5 and box["x"] + box["width"] <= client_width + 0.5, (name, lang, width, target)
                        page.keyboard.press("Escape")
                        seen += 1
                    page.close()
                context.close()
            browser.close()
    finally:
        _drop_host_pages(host, entity)
    assert seen >= 30


def test_converted_hints_are_tips_not_always_visible_text(host):
    pages, entity = _host_pages(host)
    try:
        html = host["client"].get(pages[2][1] + "?lang=en").text
        for field in ("guest_email", "status"):
            assert f'aria-describedby="{field}-help"' in html
        assert 'class="hint">“Not a guest stay”' not in html
        invoice = host["client"].get(pages[3][1] + "&lang=en").text
        assert 'aria-describedby="due_date-help"' in invoice and 'id="due_date-help"' in invoice
        assert 'class="hint">Empty means' not in invoice
        cs = host["client"].get("/apartments/new?lang=cs").text
        assert 'id="property-create-address-help"' in cs
    finally:
        _drop_host_pages(host, entity)
